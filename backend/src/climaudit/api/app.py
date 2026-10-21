"""HTTP API (BACKEND-SPEC.md section 3). Bodies are English JSON; errors use the code envelope; the server never
returns user-facing sentences. State-changing routes require `Idempotency-Key`."""
from __future__ import annotations

import hmac
import json
import re
import uuid
from collections.abc import Callable
from datetime import datetime, timedelta, timezone
from typing import Any, Literal

from fastapi import Depends, FastAPI, Header, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from pydantic import BaseModel, ConfigDict, Field, ValidationError, field_validator

from ..canonical import CanonicalError, canonical_hash
from ..config import ApiKey, Settings, load_settings
from ..errors import ApiError
from ..external.checks import ExternalChecks
from ..external.factory import build_external
from ..ledger.adapters import build_ledger
from ..ledger.port import LedgerPort
from ..profiles import ProfileRegistry
from ..readmodels import ReadModels, catalog as build_catalog, me as build_me, public_config
from ..service import Service, _drop_none, utc_now
from ..store import Store, dumps, loads

IDEMPOTENCY_TTL = timedelta(hours=24)
_CORRELATION_RE = re.compile(r"^[A-Za-z0-9._-]{1,64}$")
_PROV = Literal["measured", "modeled", "synthetic"]


class _Body(BaseModel):
    model_config = ConfigDict(extra="forbid")


class ProjectIn(_Body):
    country: str = Field(min_length=2, max_length=2, pattern=r"^[A-Za-z]{2}$")
    profile_id: str = Field(default="VM0044@1.2", max_length=64)
    provenance: _PROV = "synthetic"
    registry_project_id: str | None = Field(default=None, max_length=64, pattern=r"^[A-Za-z0-9._-]+$")


class FacilityIn(_Body):
    process: Literal["pyrolysis", "gasification", "boiler"] = "pyrolysis"
    is_greenfield: bool = True
    pyrolysis_gas_combusted: bool = False
    heat_use_pct: str = Field(default="0", max_length=16)
    pollution_controls: bool = False
    temperature_measured: bool = False
    kiln_type: str | None = Field(default=None, max_length=128)
    declared_class: Literal["high", "low"] = "low"
    country: str | None = Field(default=None, min_length=2, max_length=2)
    cell: str | None = Field(default=None, min_length=15, max_length=15)


class BatchIn(_Body):
    facility_id: str = Field(max_length=64)
    year: int = Field(ge=2000, le=2100)
    biochar_type: str = Field(max_length=64)
    application_type: Literal["soil", "non_soil"] = "soil"
    parcel_key: str | None = Field(default=None, max_length=128)
    cell_set: list[str] = Field(default_factory=list, max_length=2000)
    product_batch_id: str | None = Field(default=None, max_length=128)
    period_start: str = Field(max_length=10)
    period_end: str = Field(max_length=10)
    claimed_kg_co2e: int = Field(default=0, ge=0, le=2**53 - 1)


class BatchPatch(_Body):
    parcel_key: str | None = Field(default=None, max_length=128)
    cell_set: list[str] | None = Field(default=None, max_length=2000)
    product_batch_id: str | None = Field(default=None, max_length=128)
    period_start: str | None = Field(default=None, max_length=10)
    period_end: str | None = Field(default=None, max_length=10)
    claimed_kg_co2e: int | None = Field(default=None, ge=0, le=2**53 - 1)
    biochar_type: str | None = Field(default=None, max_length=64)
    year: int | None = Field(default=None, ge=2000, le=2100)


class EvidenceIn(_Body):
    kind: str = Field(max_length=64)
    value: str = Field(max_length=512)
    unit: str = Field(default="", max_length=32)
    group: str | None = Field(default=None, max_length=64)
    measured_at: str | None = Field(default=None, max_length=32)
    provenance: _PROV = "synthetic"
    rel_uncertainty: str | None = Field(default=None, max_length=16)
    document_ref: str | None = Field(default=None, max_length=64)
    span: dict[str, str | int] | None = None

    @field_validator("span")
    @classmethod
    def _small_span(cls, value: dict[str, str | int] | None) -> dict[str, str | int] | None:
        if value is not None and (len(value) > 16 or any(len(str(k)) > 64 or len(str(v)) > 1024 for k, v in value.items())):
            raise ValueError("span too large")
        return value


class EvidenceList(_Body):
    items: list[EvidenceIn] = Field(max_length=500)


class ConfirmIn(_Body):
    decision: Literal["confirmed", "rejected"] = "confirmed"


class DocumentIn(_Body):
    filename: str = Field(max_length=255)
    media_type: str = Field(max_length=64)
    content_base64: str = Field(max_length=64 * 1024 * 1024)


class TransitionIn(_Body):
    to: str = Field(max_length=32)
    reason: str | None = Field(default=None, max_length=512)


class OverrideIn(_Body):
    code: str = Field(max_length=64)
    reason: str = Field(max_length=512)


class TransferIn(_Body):
    to_holder: str = Field(max_length=128, pattern=r"^[A-Za-z0-9._:@-]+$")
    units: int = Field(ge=1, le=2**53 - 1)


class RetireIn(_Body):
    units: int = Field(ge=1, le=2**53 - 1)
    beneficiary_ref: str = Field(max_length=128)
    reason_code: str = Field(max_length=32)


class BodyLimitMiddleware:
    """Refuse request bodies above a limit, including chunked ones without a Content-Length.

    The body is buffered up to the limit before the application sees it (at most twice the upload limit), then replayed.
    """

    def __init__(self, app, max_bytes: int):  # type: ignore[no-untyped-def]
        self.app, self.max_bytes = app, max_bytes

    async def _refuse(self, send) -> None:  # type: ignore[no-untyped-def]
        body = json.dumps(ApiError("VALIDATION_FAILED", {"rule": "body_too_large"}, status=413).envelope("-")).encode("utf-8")
        await send({"type": "http.response.start", "status": 413, "headers": [(b"content-type", b"application/json"), (b"content-length", str(len(body)).encode())]})
        await send({"type": "http.response.body", "body": body})

    async def __call__(self, scope, receive, send):  # type: ignore[no-untyped-def]
        if scope["type"] != "http":
            return await self.app(scope, receive, send)
        messages: list[dict] = []
        total = 0
        while True:
            message = await receive()
            if message["type"] == "http.disconnect":
                return None
            total += len(message.get("body", b""))
            if total > self.max_bytes:
                return await self._refuse(send)
            messages.append(message)
            if not message.get("more_body", False):
                break
        pending = iter(messages)

        async def replay():  # type: ignore[no-untyped-def]
            try:
                return next(pending)
            except StopIteration:
                return await receive()

        return await self.app(scope, replay, send)


def create_app(settings: Settings | None = None, ledger: LedgerPort | None = None, store: Store | None = None, clock: Callable[[], str] = utc_now, external: ExternalChecks | None = None) -> FastAPI:
    settings = settings or load_settings()
    store = store or Store(settings.db_path)
    registry = ProfileRegistry(settings.profiles_dir)
    ledger = ledger or build_ledger(settings, clock)
    holders = {k.actor_id for k in settings.api_keys.values() if k.role in ("owner", "holder")}
    service = Service(
        store, registry, ledger, clock=clock, force_synthetic=settings.force_synthetic, max_upload_bytes=settings.max_upload_bytes,
        external=external or build_external(settings), known_holders=holders or None, max_documents_per_batch=settings.max_documents_per_batch,
    )
    docs_enabled = settings.env == "dev"
    app = FastAPI(
        title="ClimAudit API",
        version="0.1.0",
        docs_url="/docs" if docs_enabled else None,
        redoc_url=None,
        openapi_url="/openapi.json" if docs_enabled else None,
    )
    app.state.service, app.state.store, app.state.settings, app.state.ledger = service, store, settings, ledger
    app.add_middleware(BodyLimitMiddleware, max_bytes=settings.max_upload_bytes * 2)

    def envelope(request: Request, err: ApiError) -> JSONResponse:
        return JSONResponse(err.envelope(getattr(request.state, "correlation_id", "-")), status_code=err.status)

    @app.exception_handler(ApiError)
    async def _api_error(request: Request, exc: ApiError) -> JSONResponse:
        return envelope(request, exc)

    @app.exception_handler(RequestValidationError)
    async def _validation(request: Request, exc: RequestValidationError) -> JSONResponse:
        fields = sorted({".".join(str(p) for p in e["loc"] if p != "body") for e in exc.errors()})
        return envelope(request, ApiError("VALIDATION_FAILED", {"fields": fields}))

    @app.exception_handler(ValidationError)
    async def _model_validation(request: Request, exc: ValidationError) -> JSONResponse:
        fields = sorted({".".join(str(p) for p in e["loc"]) for e in exc.errors()})
        return envelope(request, ApiError("VALIDATION_FAILED", {"fields": fields}))

    @app.exception_handler(CanonicalError)
    async def _canonical(request: Request, exc: CanonicalError) -> JSONResponse:
        return envelope(request, ApiError("VALIDATION_FAILED", {"rule": "not_canonicalizable"}))

    @app.exception_handler(Exception)
    async def _unexpected(request: Request, exc: Exception) -> JSONResponse:  # server detail stays in logs only
        return envelope(request, ApiError("INTERNAL_ERROR"))

    @app.middleware("http")
    async def _guards(request: Request, call_next):  # type: ignore[no-untyped-def]
        supplied = request.headers.get("X-Correlation-Id", "")
        request.state.correlation_id = supplied if _CORRELATION_RE.match(supplied) else uuid.uuid4().hex
        length = request.headers.get("content-length")
        if length and length.isdigit() and int(length) > settings.max_upload_bytes * 2:
            response = envelope(request, ApiError("VALIDATION_FAILED", {"rule": "body_too_large"}, status=413))
        else:
            response = await call_next(request)
        response.headers["X-Correlation-Id"] = request.state.correlation_id
        return response

    def actor(authorization: str | None = Header(default=None)) -> ApiKey:
        if not authorization or not authorization.lower().startswith("bearer "):
            raise ApiError("AUTH_REQUIRED")
        supplied = authorization.split(" ", 1)[1].strip().encode("utf-8")
        found: ApiKey | None = None
        for key, candidate in settings.api_keys.items():  # compare against every key, in constant time per key
            if hmac.compare_digest(supplied, key.encode("utf-8")):
                found = candidate
        if found is None:
            raise ApiError("AUTH_REQUIRED")
        return found

    def _purge_expired_idempotency() -> None:
        """Remove expired idempotency rows (a bounded batch per request, inside the caller's transaction)."""
        cutoff = (datetime.strptime(clock(), "%Y-%m-%dT%H:%M:%SZ").replace(tzinfo=timezone.utc) - IDEMPOTENCY_TTL).strftime("%Y-%m-%dT%H:%M:%SZ")
        store.execute("DELETE FROM idempotency WHERE rowid IN (SELECT rowid FROM idempotency WHERE created_at < ? LIMIT 200)", (cutoff,))

    def idempotent(request: Request, who: ApiKey, body: Any, key: str | None, fn: Callable[[str], Any], success_status: int = 200) -> JSONResponse:
        """Atomic claim-and-run: lookup, operation and recording happen in one transaction under the store lock."""
        if not key or len(key) > 128:
            raise ApiError("IDEMPOTENCY_KEY_REQUIRED")
        payload = body.model_dump(mode="json") if isinstance(body, BaseModel) else (body or {})
        request_hash = canonical_hash(_drop_none(json.loads(json.dumps(payload, sort_keys=True))))
        method, path = request.method, request.url.path
        with store.transaction():
            _purge_expired_idempotency()
            row = store.one(
                "SELECT request_hash, status, body, created_at FROM idempotency WHERE actor_id=? AND method=? AND path=? AND key=?",
                (who.actor_id, method, path, key),
            )
            if row is not None:
                created = datetime.strptime(row["created_at"], "%Y-%m-%dT%H:%M:%SZ").replace(tzinfo=timezone.utc)
                now = datetime.strptime(clock(), "%Y-%m-%dT%H:%M:%SZ").replace(tzinfo=timezone.utc)
                if now - created > IDEMPOTENCY_TTL:
                    store.execute("DELETE FROM idempotency WHERE actor_id=? AND method=? AND path=? AND key=?", (who.actor_id, method, path, key))
                else:
                    if row["request_hash"] != request_hash:
                        raise ApiError("IDEMPOTENCY_CONFLICT", {"idempotency_key": key})
                    return JSONResponse(loads(row["body"]), status_code=row["status"], headers={"Idempotent-Replay": "true"})
            result = fn(key)
            store.execute(
                "INSERT INTO idempotency (actor_id, method, path, key, request_hash, status, body, created_at) VALUES (?,?,?,?,?,?,?,?)",
                (who.actor_id, method, path, key, request_hash, success_status, dumps(result), clock()),
            )
            return JSONResponse(result, status_code=success_status)

    # ---------------------------------------------------------------- routes
    @app.get("/health")
    def health() -> dict[str, Any]:
        return {"status": "ok"}

    @app.get("/me")
    def whoami(who: ApiKey = Depends(actor)) -> dict[str, str]:
        return build_me(who)

    @app.get("/config")
    def public_configuration(who: ApiKey = Depends(actor)) -> dict[str, Any]:
        return public_config(settings)

    @app.get("/catalog")
    def vocabulary(who: ApiKey = Depends(actor)) -> dict[str, Any]:
        return build_catalog()

    @app.get("/projects")
    def list_projects(limit: int = 100, who: ApiKey = Depends(actor)) -> list[dict[str, Any]]:
        return ReadModels(service).projects(who, limit)

    @app.get("/batches")
    def list_batches(limit: int = 100, who: ApiKey = Depends(actor)) -> list[dict[str, Any]]:
        return ReadModels(service).batches(who, limit)

    @app.get("/credits")
    def list_credits(limit: int = 100, who: ApiKey = Depends(actor)) -> list[dict[str, Any]]:
        return ReadModels(service).credits(who, limit)

    @app.get("/batches/{batch_id}/documents")
    def list_documents(batch_id: str, who: ApiKey = Depends(actor)) -> list[dict[str, Any]]:
        return ReadModels(service).documents(who, batch_id)

    @app.get("/documents/{document_ref}/text")
    def document_text(document_ref: str, who: ApiKey = Depends(actor)) -> dict[str, str]:
        return ReadModels(service).document_text(who, document_ref)

    @app.get("/profiles")
    def profiles(who: ApiKey = Depends(actor)) -> list[str]:
        return registry.ids()

    @app.get("/profiles/{profile_id}")
    def profile(profile_id: str, who: ApiKey = Depends(actor)) -> dict[str, Any]:
        return registry.get(profile_id).data

    @app.post("/projects")
    def create_project(request: Request, body: ProjectIn, who: ApiKey = Depends(actor), idempotency_key: str | None = Header(default=None)):
        return idempotent(request, who, body, idempotency_key, lambda k: service.create_project(who, body.model_dump()), 201)

    @app.post("/projects/{project_id}/facilities")
    def create_facility(project_id: str, request: Request, body: FacilityIn, who: ApiKey = Depends(actor), idempotency_key: str | None = Header(default=None)):
        return idempotent(request, who, body, idempotency_key, lambda k: service.create_facility(who, project_id, body.model_dump(exclude_none=True)), 201)

    @app.put("/facilities/{facility_id}/years/{year}/evidence")
    def facility_year_evidence(facility_id: str, year: int, request: Request, body: EvidenceList, who: ApiKey = Depends(actor), idempotency_key: str | None = Header(default=None)):
        return idempotent(request, who, body, idempotency_key, lambda k: service.put_facility_year_evidence(who, facility_id, year, [i.model_dump() for i in body.items]), 201)

    @app.post("/batches")
    def create_batch(request: Request, body: BatchIn, who: ApiKey = Depends(actor), idempotency_key: str | None = Header(default=None)):
        return idempotent(request, who, body, idempotency_key, lambda k: service.create_batch(who, body.model_dump()), 201)

    @app.put("/batches/{batch_id}")
    def update_batch(batch_id: str, request: Request, body: BatchPatch, who: ApiKey = Depends(actor), idempotency_key: str | None = Header(default=None)):
        return idempotent(request, who, body, idempotency_key, lambda k: service.update_batch(who, batch_id, body.model_dump(exclude_none=True)))

    @app.get("/batches/{batch_id}")
    def get_batch(batch_id: str, who: ApiKey = Depends(actor)) -> dict[str, Any]:
        return service.get_batch(who, batch_id)

    @app.post("/batches/{batch_id}/documents")
    def upload_document(batch_id: str, request: Request, body: DocumentIn, who: ApiKey = Depends(actor), idempotency_key: str | None = Header(default=None)):
        return idempotent(request, who, body, idempotency_key, lambda k: service.upload_document(who, batch_id, body.filename, body.media_type, body.content_base64), 201)

    @app.post("/batches/{batch_id}/evidence")
    def add_evidence(batch_id: str, request: Request, body: EvidenceList, who: ApiKey = Depends(actor), idempotency_key: str | None = Header(default=None)):
        return idempotent(request, who, body, idempotency_key, lambda k: service.add_evidence(who, batch_id, [i.model_dump() for i in body.items]), 201)

    @app.post("/batches/{batch_id}/evidence/{item_id}/confirm")
    def confirm_evidence(batch_id: str, item_id: str, request: Request, body: ConfirmIn, who: ApiKey = Depends(actor), idempotency_key: str | None = Header(default=None)):
        return idempotent(request, who, body, idempotency_key, lambda k: service.confirm_evidence(who, batch_id, item_id, body.decision))

    @app.post("/batches/{batch_id}/transitions")
    def transition(batch_id: str, request: Request, body: TransitionIn, who: ApiKey = Depends(actor), idempotency_key: str | None = Header(default=None)):
        return idempotent(request, who, body, idempotency_key, lambda k: service.transition(who, batch_id, body.to, body.reason))

    @app.post("/batches/{batch_id}/verification")
    def verification(batch_id: str, request: Request, who: ApiKey = Depends(actor), idempotency_key: str | None = Header(default=None)):
        return idempotent(request, who, {}, idempotency_key, lambda k: service.run_verification(who, batch_id), 201)

    @app.post("/batches/{batch_id}/findings/override")
    def override_finding(batch_id: str, request: Request, body: OverrideIn, who: ApiKey = Depends(actor), idempotency_key: str | None = Header(default=None)):
        return idempotent(request, who, body, idempotency_key, lambda k: service.override_finding(who, batch_id, body.code, body.reason))

    @app.get("/batches/{batch_id}/report")
    def report(batch_id: str, who: ApiKey = Depends(actor)) -> dict[str, Any]:
        return service.get_report(who, batch_id)

    @app.get("/batches/{batch_id}/findings")
    def findings(batch_id: str, who: ApiKey = Depends(actor)) -> list[dict[str, Any]]:
        return service.get_report(who, batch_id)["findings"]

    @app.post("/batches/{batch_id}/issue")
    def issue(batch_id: str, request: Request, who: ApiKey = Depends(actor), idempotency_key: str | None = Header(default=None)):
        return idempotent(request, who, {}, idempotency_key, lambda k: service.issue(who, batch_id, k))

    @app.get("/credits/{credit_id}")
    def credit(credit_id: str, who: ApiKey = Depends(actor)) -> dict[str, Any]:
        return service.get_credit(who, credit_id)

    @app.post("/credits/{credit_id}/transfer")
    def transfer(credit_id: str, request: Request, body: TransferIn, who: ApiKey = Depends(actor), idempotency_key: str | None = Header(default=None)):
        return idempotent(request, who, body, idempotency_key, lambda k: service.transfer(who, credit_id, body.to_holder, body.units, k))

    @app.post("/credits/{credit_id}/retire")
    def retire(credit_id: str, request: Request, body: RetireIn, who: ApiKey = Depends(actor), idempotency_key: str | None = Header(default=None)):
        return idempotent(request, who, body, idempotency_key, lambda k: service.retire(who, credit_id, body.units, body.beneficiary_ref, body.reason_code, k))

    @app.get("/audit/verify")
    def audit_verify(who: ApiKey = Depends(actor)) -> dict[str, Any]:
        if who.role not in ("admin", "system", "verifier", "registry"):
            raise ApiError("ROLE_NOT_AUTHORIZED", {"action": "audit_verify"})
        return service.audit_verify()

    @app.get("/audit/{batch_id}")
    def audit(batch_id: str, who: ApiKey = Depends(actor)) -> list[dict[str, Any]]:
        return service.audit_for(who, batch_id)

    return app


def app_factory() -> FastAPI:
    """Entry point for `uvicorn climaudit.api.app:app_factory --factory`; reads CP_* environment variables."""
    return create_app()
