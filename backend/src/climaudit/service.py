"""Application service: state machine, evidence handling, verification runs, issuance, audit trail.

The AI is not called from here. Every state change that matters is requested by an authorized role, re-reads the
current state inside its own transaction, appends a hash-chained audit event and is anchored through the ledger port.
Multi-step ledger operations (issuance) hold the store lock for their whole duration and persist their intent first.
"""
from __future__ import annotations

import base64
import uuid
from collections.abc import Callable
from datetime import date, datetime, timedelta, timezone
from decimal import Decimal
from typing import Any

from . import guard, h3util, states
from .canonical import GENESIS_HASH, canonical_hash, sha256_hex
from .checks import sanitizer
from .config import ApiKey
from .errors import ApiError
from .external.checks import ExternalChecks
from .evidence import KINDS, EvidenceItem, EvidenceView, normalize_item
from .extraction.contract import KIND_KEYWORDS, quote_supports_value
from .findings import CATALOG, Finding, make
from .hashchain import make_event, verify_chain
from .ledger.port import SYNTHETIC_MARKER, LedgerPort, MintResult
from .models import BatchRecord, Facility, Project
from .profiles import Profile, ProfileRegistry
from .store import Store, dumps, loads
from .verification import VerificationInput, verify

ALTERNATIVE_PROFILE_ROLES = ("admin", "verifier")
EVIDENCE_CHANGE_STATES = ("UNDER_REVIEW",)


def utc_now() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def new_id(prefix: str) -> str:
    return f"{prefix}-{uuid.uuid4().hex[:12]}"


def _drop_none(value: Any) -> Any:
    """Remove None values recursively so the structure can be hashed canonically (nulls are not allowed)."""
    if isinstance(value, dict):
        return {k: _drop_none(v) for k, v in value.items() if v is not None}
    if isinstance(value, list):
        return [_drop_none(v) for v in value]
    if isinstance(value, Decimal):
        return format(value, "f")
    return value


class Service:
    def __init__(
        self,
        store: Store,
        registry: ProfileRegistry,
        ledger: LedgerPort,
        clock: Callable[[], str] = utc_now,
        ids: Callable[[str], str] = new_id,
        force_synthetic: bool = True,
        max_upload_bytes: int = 10 * 1024 * 1024,
        external: ExternalChecks | None = None,
        known_holders: set[str] | None = None,
        max_documents_per_batch: int = 20,
    ):
        self.store, self.registry, self.ledger, self.clock, self.ids = store, registry, ledger, clock, ids
        self.external = external
        self.known_holders, self.max_documents_per_batch = known_holders, max_documents_per_batch
        self.force_synthetic, self.max_upload_bytes = force_synthetic, max_upload_bytes

    # ------------------------------------------------------------------ loaders
    def _project(self, project_id: str) -> Project:
        row = self.store.one("SELECT data FROM projects WHERE project_id=?", (project_id,))
        if row is None:
            raise ApiError("NOT_FOUND", {"resource": "project", "id": project_id})
        return Project(**loads(row["data"]))

    def _facility(self, facility_id: str) -> Facility:
        row = self.store.one("SELECT data FROM facilities WHERE facility_id=?", (facility_id,))
        if row is None:
            raise ApiError("NOT_FOUND", {"resource": "facility", "id": facility_id})
        return Facility(**loads(row["data"]))

    def _batch(self, batch_id: str) -> BatchRecord:
        row = self.store.one("SELECT data FROM batches WHERE batch_id=?", (batch_id,))
        if row is None:
            raise ApiError("BATCH_NOT_FOUND", {"batch_id": batch_id})
        return BatchRecord(**loads(row["data"]))

    def _profile_of(self, batch: BatchRecord) -> Profile:
        return self.registry.get(batch.profile_id)

    def _save_batch(self, batch: BatchRecord) -> BatchRecord:
        batch = batch.model_copy(update={"updated_at": self.clock()})
        dedup = self._dedup_key(batch)
        with self.store.transaction() as conn:
            conn.execute(
                "INSERT INTO batches (batch_id, project_id, facility_id, state, dedup_key, period_start, period_end, data) VALUES (?,?,?,?,?,?,?,?) "
                "ON CONFLICT(batch_id) DO UPDATE SET state=excluded.state, dedup_key=excluded.dedup_key, period_start=excluded.period_start, "
                "period_end=excluded.period_end, data=excluded.data",
                (batch.batch_id, batch.project_id, batch.facility_id, batch.state, dedup, batch.period_start, batch.period_end, dumps(batch.model_dump())),
            )
        return batch

    def _dedup_key(self, batch: BatchRecord) -> str | None:
        key = batch.parcel_key if batch.application_type == "soil" else batch.product_batch_id
        if not key:
            return None
        return guard.dedup_key(key, self._profile_of(batch).methodology_id)

    def _evidence(self, batch_id: str) -> list[EvidenceItem]:
        rows = self.store.query("SELECT data FROM evidence WHERE batch_id=? ORDER BY rowid", (batch_id,))
        return [EvidenceItem(**loads(r["data"])) for r in rows]

    def _facility_year(self, facility_id: str, year: int) -> list[EvidenceItem]:
        rows = self.store.query("SELECT data FROM facility_year_evidence WHERE facility_id=? AND year=? ORDER BY rowid", (facility_id, year))
        return [EvidenceItem(**loads(r["data"])) for r in rows]

    def _holds_credit_of(self, actor: ApiKey, batch_id: str) -> bool:
        row = self.store.one(
            "SELECT 1 FROM balances b JOIN credits c ON c.credit_id=b.credit_id WHERE c.batch_id=? AND b.holder=?",
            (batch_id, actor.actor_id),
        )
        return row is not None

    def _can_read(self, actor: ApiKey, batch: BatchRecord, project: Project, allow_extractor: bool = False) -> None:
        if actor.role in ("admin", "system", "verifier", "registry"):
            return
        if allow_extractor and actor.role == "extractor":
            return
        if project.owner_actor == actor.actor_id or self._holds_credit_of(actor, batch.batch_id):
            return
        raise ApiError("ROLE_NOT_AUTHORIZED", {"action": "access_other_owner_project"})

    def _own_or_privileged(self, actor: ApiKey, project: Project, allow_extractor: bool = False) -> None:
        if actor.role in ("admin", "system", "verifier", "registry"):
            return
        if allow_extractor and actor.role == "extractor":
            return
        if project.owner_actor != actor.actor_id:
            raise ApiError("ROLE_NOT_AUTHORIZED", {"action": "access_other_owner_project"})

    # ----------------------------------------------------------------- creation
    def create_project(self, actor: ApiKey, body: dict[str, Any]) -> dict[str, Any]:
        states.check_permission("project.create", actor.role)
        profile = self.registry.get(body.get("profile_id", "VM0044@1.2"))
        if profile.alternative and actor.role not in ALTERNATIVE_PROFILE_ROLES:
            raise ApiError("ROLE_NOT_AUTHORIZED", {"action": "use_alternative_profile", "required_role": list(ALTERNATIVE_PROFILE_ROLES)})
        provenance = body.get("provenance", "synthetic")
        if self.force_synthetic and provenance != "synthetic":
            raise ApiError("VALIDATION_FAILED", {"field": "provenance", "rule": "synthetic_only_in_demo_mode"})
        project = Project(
            project_id=self.ids("prj"),
            owner_actor=actor.actor_id,
            methodology_id=profile.methodology_id,
            methodology_version=profile.version,
            profile_id=profile.profile_id,
            country=str(body.get("country", "")).upper(),
            provenance=provenance,
            registry_project_id=(body.get("registry_project_id") or None),
            created_at=self.clock(),
        )
        self.store.execute("INSERT INTO projects (project_id, data) VALUES (?,?)", (project.project_id, dumps(project.model_dump())))
        return project.model_dump()

    def create_facility(self, actor: ApiKey, project_id: str, body: dict[str, Any]) -> dict[str, Any]:
        states.check_permission("facility.create", actor.role)
        project = self._project(project_id)
        self._own_or_privileged(actor, project)
        data = {k: v for k, v in body.items() if k not in ("facility_id", "project_id")}
        data.setdefault("country", project.country)
        if data.get("cell"):
            data["cell"] = h3util.normalize_cells([data["cell"]], allowed_resolutions=(7, 8, 9, 10))[0]
        facility = Facility(facility_id=self.ids("fac"), project_id=project_id, **data)
        profile = self.registry.get(project.profile_id)
        derived = "high" if facility.meets_high_tech(profile.rule("high_tech_min_heat_use_pct")[0]) else "low"
        self.store.execute("INSERT INTO facilities (facility_id, project_id, data) VALUES (?,?,?)", (facility.facility_id, project_id, dumps(facility.model_dump())))
        return {**facility.model_dump(), "derived_class": derived}

    def create_batch(self, actor: ApiKey, body: dict[str, Any]) -> dict[str, Any]:
        states.check_permission("batch.create", actor.role)
        facility = self._facility(body["facility_id"])
        project = self._project(facility.project_id)
        self._own_or_privileged(actor, project)
        data = {k: v for k, v in body.items() if k not in ("batch_id", "state", "project_id", "profile_id", "created_at", "updated_at")}
        batch = BatchRecord(batch_id=self.ids("b"), project_id=project.project_id, profile_id=project.profile_id, state="DRAFT", created_at=self.clock(), **data)
        batch = self._validate_batch(batch)
        self._save_batch(batch)
        return batch.model_dump()

    def _allowed_resolutions(self, profile: Profile) -> tuple[int, ...]:
        try:
            raw = profile.rule_entry("h3_resolutions")["value"]
            return tuple(int(x) for x in str(raw).split(","))
        except ApiError:
            return (9, 10)

    def _validate_batch(self, batch: BatchRecord) -> BatchRecord:
        try:
            start, end = date.fromisoformat(batch.period_start), date.fromisoformat(batch.period_end)
        except ValueError as exc:
            raise ApiError("DATE_AMBIGUOUS", {"field": "period"}) from exc
        if not start < end:
            raise ApiError("PERIOD_INVALID", {"start": batch.period_start, "end": batch.period_end})
        profile = self._profile_of(batch)
        claim_spec = profile.plausibility("claimed_kg_co2e")
        if claim_spec and not (claim_spec[0] <= Decimal(batch.claimed_kg_co2e) <= claim_spec[1]):
            raise ApiError("VALIDATION_FAILED", {"field": "claimed_kg_co2e", "rule": "range", "allowed": claim_spec[2].value})
        if batch.application_type == "soil":
            if not batch.parcel_key:
                raise ApiError("VALIDATION_FAILED", {"field": "parcel_key", "rule": "required_for_soil"})
            max_cells = int(profile.rule_entry("max_cells_per_batch")["value"]) if "max_cells_per_batch" in profile.data.get("rules", {}) else 2000
            cells = h3util.normalize_cells(batch.cell_set, self._allowed_resolutions(profile), max_cells)
            batch = batch.model_copy(update={"cell_set": cells})
        elif not batch.product_batch_id:
            raise ApiError("VALIDATION_FAILED", {"field": "product_batch_id", "rule": "required_for_non_soil"})
        return batch

    def update_batch(self, actor: ApiKey, batch_id: str, body: dict[str, Any]) -> dict[str, Any]:
        states.check_permission("batch.edit", actor.role)
        with self.store.transaction():
            batch = self._batch(batch_id)
            self._own_or_privileged(actor, self._project(batch.project_id))
            if batch.state not in states.EDITABLE_STATES:
                raise ApiError("STATE_TRANSITION_NOT_ALLOWED", {"from": batch.state, "to": "edit"})
            allowed = {"parcel_key", "cell_set", "product_batch_id", "period_start", "period_end", "claimed_kg_co2e", "biochar_type", "year"}
            changes = {k: v for k, v in body.items() if k in allowed}
            updated = self._validate_batch(BatchRecord(**{**batch.model_dump(), **changes}))
            self._save_batch(updated)
            return updated.model_dump()

    # ----------------------------------------------------------------- evidence
    def _require_editable(self, batch: BatchRecord, extra_states: tuple[str, ...] = ()) -> None:
        if batch.state not in states.EDITABLE_STATES and batch.state not in extra_states:
            raise ApiError("STATE_TRANSITION_NOT_ALLOWED", {"from": batch.state, "to": "evidence_change"})

    def _log_evidence_change(self, batch: BatchRecord, actor: ApiKey, what: str, ref: str) -> None:
        """Changes after submission (documents, confirmations) are audited with the actor."""
        if batch.state in EVIDENCE_CHANGE_STATES:
            self._append_event("evidence_attached", batch, canonical_hash({"actor": actor.actor_id, "role": actor.role, "change": what, "ref": ref}))

    def _check_extractor_item(self, batch: BatchRecord, data: dict[str, Any]) -> None:
        """Server-side gate for AI-proposed evidence: the document must belong to the batch and support the value."""
        kind, value = data["kind"], data["value"]
        document_ref = data.get("document_ref")
        quote = (data.get("span") or {}).get("quote")
        if kind not in KIND_KEYWORDS:
            raise ApiError("VALIDATION_FAILED", {"field": "kind", "rule": "kind_not_extractable", "value": kind})
        if not document_ref or not quote:
            raise ApiError("VALIDATION_FAILED", {"field": "document_ref", "rule": "document_and_quote_required_for_extraction"})
        row = self.store.one("SELECT visible_text FROM documents WHERE document_ref=? AND batch_id=?", (document_ref, batch.batch_id))
        if row is None:
            raise ApiError("VALIDATION_FAILED", {"field": "document_ref", "rule": "document_not_in_batch"})
        reason = quote_supports_value(row["visible_text"], kind, value, str(quote))
        if reason:
            raise ApiError("VALIDATION_FAILED", {"field": "span", "rule": reason})

    def add_evidence(self, actor: ApiKey, batch_id: str, items: list[dict[str, Any]]) -> list[dict[str, Any]]:
        states.check_permission("evidence.add", actor.role)
        stored: list[dict[str, Any]] = []
        with self.store.transaction() as conn:
            batch = self._batch(batch_id)
            self._own_or_privileged(actor, self._project(batch.project_id), allow_extractor=True)
            self._require_editable(batch)
            existing_kinds = {i.kind for i in self._evidence(batch_id) if i.confirmation != "rejected"}
            seen_in_request: set[str] = set()
            for raw in items:
                data = dict(raw)
                data["item_id"] = self.ids("it")
                if actor.role == "extractor":
                    data["source"], data["confirmation"] = "model", "pending_confirmation"
                    self._check_extractor_item(batch, data)
                else:
                    data["source"], data["confirmation"] = data.get("source", "owner"), "confirmed"
                item = normalize_item(EvidenceItem(**data))
                single = not KINDS[item.kind].multi
                if single and (item.kind in existing_kinds or item.kind in seen_in_request):
                    raise ApiError("VALIDATION_FAILED", {"field": item.kind, "rule": "duplicate_single_valued_kind"})
                if single:
                    seen_in_request.add(item.kind)
                conn.execute("INSERT INTO evidence (item_id, batch_id, data) VALUES (?,?,?)", (item.item_id, batch_id, dumps(item.model_dump())))
                stored.append(item.model_dump())
        return stored

    def put_facility_year_evidence(self, actor: ApiKey, facility_id: str, year: int, items: list[dict[str, Any]]) -> list[dict[str, Any]]:
        """Replace all facility-year inputs for (facility, year); refused once a batch of that year has been submitted."""
        states.check_permission("evidence.add", actor.role)
        if actor.role == "extractor":
            raise ApiError("ROLE_NOT_AUTHORIZED", {"action": "facility_year_evidence"})
        stored: list[dict[str, Any]] = []
        with self.store.transaction() as conn:
            facility = self._facility(facility_id)
            self._own_or_privileged(actor, self._project(facility.project_id))
            for row in self.store.query("SELECT data FROM batches WHERE facility_id=?", (facility_id,)):
                other = BatchRecord(**loads(row["data"]))
                if other.year == year and other.state not in states.EDITABLE_STATES:
                    raise ApiError("STATE_TRANSITION_NOT_ALLOWED", {"from": other.state, "to": "facility_year_change"})
            seen: set[str] = set()
            normalized: list[EvidenceItem] = []
            for raw in items:
                item = normalize_item(EvidenceItem(**dict(raw, item_id=self.ids("fy"), source=raw.get("source", "owner"), confirmation="confirmed")))
                if KINDS[item.kind].scope != "facility_year":
                    raise ApiError("VALIDATION_FAILED", {"field": item.kind, "rule": "not_a_facility_year_kind"})
                if not KINDS[item.kind].multi and item.kind in seen:
                    raise ApiError("VALIDATION_FAILED", {"field": item.kind, "rule": "duplicate_single_valued_kind"})
                seen.add(item.kind)
                normalized.append(item)
            conn.execute("DELETE FROM facility_year_evidence WHERE facility_id=? AND year=?", (facility_id, year))
            for item in normalized:
                conn.execute("INSERT INTO facility_year_evidence (item_id, facility_id, year, data) VALUES (?,?,?,?)", (item.item_id, facility_id, year, dumps(item.model_dump())))
                stored.append(item.model_dump())
        return stored

    def confirm_evidence(self, actor: ApiKey, batch_id: str, item_id: str, decision: str = "confirmed") -> dict[str, Any]:
        states.check_permission("evidence.confirm", actor.role)
        if decision not in ("confirmed", "rejected"):
            raise ApiError("VALIDATION_FAILED", {"field": "decision", "rule": "enum"})
        with self.store.transaction():
            batch = self._batch(batch_id)
            self._own_or_privileged(actor, self._project(batch.project_id))
            self._require_editable(batch, extra_states=("UNDER_REVIEW",))
            if batch.state == "UNDER_REVIEW" and actor.role not in ("verifier", "admin"):
                raise ApiError("ROLE_NOT_AUTHORIZED", {"action": "confirm_evidence_after_submission", "required_role": ["verifier", "admin"]})
            row = self.store.one("SELECT data FROM evidence WHERE item_id=? AND batch_id=?", (item_id, batch_id))
            if row is None:
                raise ApiError("NOT_FOUND", {"resource": "evidence", "id": item_id})
            item = EvidenceItem(**loads(row["data"])).model_copy(update={"confirmation": decision})
            self.store.execute("UPDATE evidence SET data=? WHERE item_id=?", (dumps(item.model_dump()), item_id))
            self._log_evidence_change(batch, actor, f"item_{decision}", item_id)
            return item.model_dump()

    def upload_document(self, actor: ApiKey, batch_id: str, filename: str, media_type: str, content_b64: str) -> dict[str, Any]:
        states.check_permission("document.upload", actor.role)
        if len(content_b64) > self.max_upload_bytes * 4 // 3 + 8:
            raise ApiError("FILE_CORRUPT", {"reason": "file_too_large", "max_bytes": self.max_upload_bytes})
        try:
            raw = base64.b64decode(content_b64, validate=True)
        except Exception as exc:  # noqa: BLE001
            raise ApiError("FILE_CORRUPT", {"reason": "invalid_base64"}) from exc
        if media_type == "application/pdf":
            doc = sanitizer.sanitize_pdf(raw, self.max_upload_bytes)
        elif media_type in ("text/plain", "text/csv", "application/json"):
            if len(raw) > self.max_upload_bytes:
                raise ApiError("FILE_CORRUPT", {"reason": "file_too_large", "max_bytes": self.max_upload_bytes})
            try:
                doc = sanitizer.sanitize_text(raw.decode("utf-8"), raw)
            except UnicodeDecodeError as exc:
                raise ApiError("FILE_CORRUPT", {"reason": "not_utf8"}) from exc
        else:
            raise ApiError("FILE_UNSUPPORTED", {"media_type": media_type})
        with self.store.transaction():
            batch = self._batch(batch_id)
            self._own_or_privileged(actor, self._project(batch.project_id))
            self._require_editable(batch, extra_states=("UNDER_REVIEW",))
            existing = self.store.one("SELECT COUNT(*) AS n FROM documents WHERE batch_id=?", (batch_id,))["n"]
            if existing >= self.max_documents_per_batch:
                raise ApiError("VALIDATION_FAILED", {"field": "documents", "rule": "too_many_documents", "max": self.max_documents_per_batch})
            ref = self.ids("doc")
            findings = sanitizer.findings_for(doc, ref)
            self.store.execute(
                "INSERT INTO documents (document_ref, batch_id, sha256, filename, media_type, size, content, findings, visible_text) VALUES (?,?,?,?,?,?,?,?,?)",
                (ref, batch_id, doc.sha256, filename[:255], media_type, len(raw), raw, dumps([f.as_dict() for f in findings]), doc.visible_text),
            )
            self._log_evidence_change(batch, actor, "document_uploaded", doc.sha256)
        return {"document_ref": ref, "sha256": doc.sha256, "pages": doc.pages, "findings": [f.as_dict() for f in findings], "visible_text_chars": len(doc.visible_text)}

    def get_visible_text(self, actor: ApiKey, document_ref: str) -> str:
        """The only text an extraction agent may read: sanitized, with hidden segments removed."""
        row = self.store.one("SELECT batch_id, visible_text FROM documents WHERE document_ref=?", (document_ref,))
        if row is None:
            raise ApiError("NOT_FOUND", {"resource": "document", "id": document_ref})
        batch = self._batch(row["batch_id"])
        self._can_read(actor, batch, self._project(batch.project_id), allow_extractor=True)
        return row["visible_text"]

    # --------------------------------------------------------------------- audit
    def _provenance(self, project_id: str) -> str:
        return self._project(project_id).provenance

    def _append_event(self, event_type: str, batch: BatchRecord, payload_hash: str) -> dict[str, Any]:
        with self.store.transaction() as conn:
            last = conn.execute("SELECT seq, hash FROM audit_events ORDER BY seq DESC LIMIT 1").fetchone()
            seq, prev = (0, GENESIS_HASH) if last is None else (last["seq"] + 1, last["hash"])
            event = make_event(seq, self.clock(), event_type, batch.batch_id, payload_hash, prev, self._provenance(batch.project_id))
            ref = self.ledger.anchor(event["hash"], {"type": event_type, "batch_id": batch.batch_id, "seq": seq})
            conn.execute(
                "INSERT INTO audit_events (seq, batch_id, hash, data, ledger_ref) VALUES (?,?,?,?,?)",
                (seq, batch.batch_id, event["hash"], dumps(event), dumps(ref.as_dict())),
            )
            return {**event, "ledger_ref": ref.as_dict()}

    def audit_for(self, actor: ApiKey, batch_id: str) -> list[dict[str, Any]]:
        batch = self._batch(batch_id)
        self._can_read(actor, batch, self._project(batch.project_id))
        rows = self.store.query("SELECT data, ledger_ref FROM audit_events WHERE batch_id=? ORDER BY seq", (batch_id,))
        return [{**loads(r["data"]), "ledger_ref": loads(r["ledger_ref"]) if r["ledger_ref"] else None} for r in rows]

    def audit_verify(self) -> dict[str, Any]:
        rows = self.store.query("SELECT data FROM audit_events ORDER BY seq")
        events = [loads(r["data"]) for r in rows]
        local = verify_chain(events)
        published = self.ledger.published_hashes()  # real adapters raise LEDGER_UNAVAILABLE until configured
        return {
            "chain_ok": local.ok,
            "first_broken_seq": local.first_broken_seq,
            "reason": local.reason,
            "event_count": len(events),
            "ledger_count": len(published),
            "ledger_matches": published == [e["hash"] for e in events],
        }

    # --------------------------------------------------------------- evidence hash
    def _evidence_hash(self, batch: BatchRecord) -> str:
        """Fingerprint of everything a report depends on: evidence, facility-year inputs, documents and batch fields."""
        items = sorted((i.model_dump() for i in self._evidence(batch.batch_id)), key=lambda d: d["item_id"])
        fy = sorted((i.model_dump() for i in self._facility_year(batch.facility_id, batch.year)), key=lambda d: d["item_id"])
        docs = sorted(r["sha256"] for r in self.store.query("SELECT sha256 FROM documents WHERE batch_id=?", (batch.batch_id,)))
        fields = {
            k: getattr(batch, k)
            for k in ("facility_id", "year", "biochar_type", "application_type", "profile_id", "parcel_key", "cell_set", "product_batch_id", "period_start", "period_end", "claimed_kg_co2e")
        }
        return canonical_hash({"batch": _drop_none(fields), "evidence": _drop_none(items), "facility_year": _drop_none(fy), "documents": docs})

    # ------------------------------------------------------------- double counting
    def _claim(self, batch: BatchRecord, state: str | None = None) -> guard.Claim:
        return guard.Claim(
            batch.batch_id,
            state or batch.state,
            self._dedup_key(batch) or "",
            frozenset(batch.cell_set),
            date.fromisoformat(batch.period_start),
            date.fromisoformat(batch.period_end),
        )

    def _conflicts(self, batch: BatchRecord) -> list[guard.Conflict]:
        others = [BatchRecord(**loads(r["data"])) for r in self.store.query("SELECT data FROM batches WHERE batch_id<>?", (batch.batch_id,))]
        existing = [self._claim(o) for o in others if o.state in guard.HOLDING_STATES]
        return guard.find_conflicts(self._claim(batch, state="SUBMITTED"), existing)

    def _facility_mass_finding(self, batch: BatchRecord) -> Finding | None:
        """The dry mass of all period-holding batches of a facility-year must not exceed the facility total."""
        fy = EvidenceView(self._facility_year(batch.facility_id, batch.year))
        total = fy.dec("facility_total_dry_mass")
        if total is None:
            return None
        used = Decimal(0)
        for row in self.store.query("SELECT data FROM batches WHERE facility_id=?", (batch.facility_id,)):
            other = BatchRecord(**loads(row["data"]))
            if other.year != batch.year:
                continue
            counts = other.state in guard.HOLDING_STATES or other.batch_id == batch.batch_id
            if counts:
                used += EvidenceView(self._evidence(other.batch_id)).dec("dry_mass_biochar") or Decimal(0)
        if used > total:
            return make("MASS_BALANCE_MISMATCH", origin="facility_total", expected_t=format(total, "f"), found_t=format(used, "f"))
        return None

    # ---------------------------------------------------------------- transitions
    def _set_state(self, batch: BatchRecord, new_state: str, reason: str | None = None) -> BatchRecord:
        updated = self._save_batch(batch.model_copy(update={"state": new_state}))
        self._append_event("state_changed", updated, canonical_hash({"batch_id": batch.batch_id, "from": batch.state, "to": new_state, "reason": reason or ""}))
        return updated

    def transition(self, actor: ApiKey, batch_id: str, to: str, reason: str | None = None) -> dict[str, Any]:
        with self.store.transaction():
            batch = self._batch(batch_id)  # re-read inside the transaction: the state may have changed since the request began
            self._own_or_privileged(actor, self._project(batch.project_id))
            if to == "ISSUED":
                raise ApiError("STATE_TRANSITION_NOT_ALLOWED", {"from": batch.state, "to": to, "hint": "use_issue_route"})
            if to in ("PARTIALLY_RETIRED", "RETIRED") and batch.state in ("ISSUED", "PARTIALLY_RETIRED"):
                raise ApiError("STATE_TRANSITION_NOT_ALLOWED", {"from": batch.state, "to": to, "hint": "use_retire_route"})
            states.check_transition(batch.state, to, actor.role, reason)
            if (batch.state, to) in (("DRAFT", "SUBMITTED"), ("NEEDS_INFO", "SUBMITTED")):
                return self._submit(batch)
            if (batch.state, to) == ("UNDER_REVIEW", "VERIFIED"):
                self._require_verifiable(batch)
            return self._set_state(batch, to, reason).model_dump()

    def _derive_period(self, batch: BatchRecord) -> BatchRecord:
        """The guard period is the application period, derived from the evidence, never trusted from the client."""
        ev = EvidenceView(self._evidence(batch.batch_id))
        dates = [date.fromisoformat(i.value) for i in ev.all("application_date")]
        if not dates:
            raise ApiError("VALIDATION_FAILED", {"field": "application_date", "rule": "required_before_submission"})
        return batch.model_copy(update={"period_start": min(dates).isoformat(), "period_end": (max(dates) + timedelta(days=1)).isoformat()})

    def _submit(self, batch: BatchRecord) -> dict[str, Any]:
        batch = self._validate_batch(self._derive_period(batch))
        if batch.claimed_kg_co2e <= 0:
            raise ApiError("VALIDATION_FAILED", {"field": "claimed_kg_co2e", "rule": "positive"})
        conflicts = self._conflicts(batch)
        if conflicts:
            first = conflicts[0]
            raise ApiError(
                "BATCH_PERIOD_OVERLAP",
                {"parcel_key": batch.parcel_key or batch.product_batch_id, "conflicting_batch_id": first.batch_id, "overlap": list(first.overlap), "reason": first.reason},
            )
        submitted = self._save_batch(batch.model_copy(update={"state": "SUBMITTED"}))
        self._append_event("batch_submitted", submitted, canonical_hash({"batch": _drop_none(submitted.model_dump(exclude={"updated_at"}))}))
        self._append_event("evidence_attached", submitted, self._evidence_hash(submitted))
        return self._set_state(submitted, "UNDER_REVIEW", "anchored").model_dump()

    def _latest_report(self, batch_id: str) -> dict[str, Any] | None:
        row = self.store.one("SELECT report_id, evidence_hash, data FROM reports WHERE batch_id=? ORDER BY created_at DESC, rowid DESC LIMIT 1", (batch_id,))
        if row is None:
            return None
        return {"report_id": row["report_id"], "evidence_hash": row["evidence_hash"], **loads(row["data"])}

    def _active_overrides(self, batch_id: str, report_id: str) -> set[str]:
        return {r["code"] for r in self.store.query("SELECT code FROM finding_overrides WHERE batch_id=? AND report_id=?", (batch_id, report_id))}

    def _blocking_after_overrides(self, report: dict[str, Any]) -> list[str]:
        overridden = self._active_overrides(report["batch_id"], report["report_id"])
        return [f["code"] for f in report["findings"] if f["blocks_verified"] and not (f["overridable"] and f["code"] in overridden)]

    def _require_verifiable(self, batch: BatchRecord) -> None:
        report = self._latest_report(batch.batch_id)
        if report is None or report["status"] != "complete":
            raise ApiError("STATE_TRANSITION_NOT_ALLOWED", {"from": batch.state, "to": "VERIFIED", "reason": "no_complete_report"})
        if report["evidence_hash"] != self._evidence_hash(batch):
            raise ApiError("STATE_TRANSITION_NOT_ALLOWED", {"from": batch.state, "to": "VERIFIED", "reason": "report_is_stale"})
        blocking = self._blocking_after_overrides(report)
        if blocking or not report["grounding"]["passed"]:
            raise ApiError("STATE_TRANSITION_NOT_ALLOWED", {"from": batch.state, "to": "VERIFIED", "reason": "blocking_findings", "codes": sorted(set(blocking))})
        if any(i.confirmation == "pending_confirmation" for i in self._evidence(batch.batch_id)):
            raise ApiError("STATE_TRANSITION_NOT_ALLOWED", {"from": batch.state, "to": "VERIFIED", "reason": "pending_evidence"})

    def override_finding(self, actor: ApiKey, batch_id: str, code: str, reason: str) -> dict[str, Any]:
        """A verifier accepts an overridable finding of the current report, with a reason, as an audited correction."""
        if actor.role not in ("verifier", "admin"):
            raise ApiError("ROLE_NOT_AUTHORIZED", {"action": "override_finding", "required_role": ["verifier", "admin"]})
        if not reason or not reason.strip():
            raise ApiError("VALIDATION_FAILED", {"field": "reason", "rule": "required"})
        if code not in CATALOG or not CATALOG[code].overridable:
            raise ApiError("VALIDATION_FAILED", {"field": "code", "rule": "not_overridable", "value": code})
        with self.store.transaction():
            batch = self._batch(batch_id)
            if batch.state != "UNDER_REVIEW":
                raise ApiError("STATE_TRANSITION_NOT_ALLOWED", {"from": batch.state, "to": "override"})
            report = self._latest_report(batch_id)
            if report is None or report["evidence_hash"] != self._evidence_hash(batch):
                raise ApiError("STATE_TRANSITION_NOT_ALLOWED", {"from": batch.state, "to": "override", "reason": "no_current_report"})
            if not any(f["code"] == code for f in report["findings"]):
                raise ApiError("NOT_FOUND", {"resource": "finding", "id": code})
            self.store.execute(
                "INSERT INTO finding_overrides (batch_id, code, report_id, actor_id, reason, created_at) VALUES (?,?,?,?,?,?) "
                "ON CONFLICT(batch_id, code) DO UPDATE SET report_id=excluded.report_id, actor_id=excluded.actor_id, reason=excluded.reason, created_at=excluded.created_at",
                (batch_id, code, report["report_id"], actor.actor_id, reason.strip(), self.clock()),
            )
            self._append_event("correction", batch, canonical_hash({"override": code, "report_id": report["report_id"], "actor": actor.actor_id, "reason": reason.strip()}))
            return {"batch_id": batch_id, "code": code, "report_id": report["report_id"], "actor_id": actor.actor_id}

    # --------------------------------------------------------------- verification
    def run_verification(self, actor: ApiKey, batch_id: str) -> dict[str, Any]:
        states.check_permission("verification.run", actor.role)
        external_findings: list[Finding] = []
        if self.external is not None:
            # Public-data checks may take seconds, so they run before the transaction (and its lock) opens. The batch
            # is re-read inside; evidence cannot change while the batch is UNDER_REVIEW.
            pre = self._batch(batch_id)
            if pre.state == "UNDER_REVIEW":
                external_findings = self.external.run(self._project(pre.project_id), self._facility(pre.facility_id), pre, self._evidence(batch_id))
        with self.store.transaction() as conn:
            batch = self._batch(batch_id)
            if batch.state != "UNDER_REVIEW":
                raise ApiError("STATE_TRANSITION_NOT_ALLOWED", {"from": batch.state, "to": "verification"})
            project = self._project(batch.project_id)
            facility = self._facility(batch.facility_id)
            profile = self._profile_of(batch)
            document_findings: list[Finding] = []
            for row in self.store.query("SELECT findings FROM documents WHERE batch_id=?", (batch_id,)):
                for f in loads(row["findings"]):
                    document_findings.append(Finding(code=f["code"], params=f["params"], source=f.get("source", "rule")))
            extra: list[Finding] = []
            for conflict in self._conflicts(batch):
                code = "PERIOD_OVERLAP_DETECTED" if conflict.reason == "exact_key" else "PARCEL_CELL_OVERLAP"
                extra.append(make(code, conflicting_batch_id=conflict.batch_id, reason=conflict.reason))
            for doc in self.store.query("SELECT document_ref FROM documents WHERE batch_id=? AND sha256 IN (SELECT sha256 FROM documents WHERE batch_id<>?)", (batch_id, batch_id)):
                extra.append(make("EVIDENCE_DUPLICATED", document_ref=doc["document_ref"]))
            mass_finding = self._facility_mass_finding(batch)
            if mass_finding is not None:
                extra.append(mass_finding)
            extra += external_findings
            report = verify(
                VerificationInput(
                    profile=profile,
                    facility=facility,
                    batch=batch,
                    evidence=self._evidence(batch_id),
                    facility_year=self._facility_year(batch.facility_id, batch.year),
                    project_country=project.country,
                    document_findings=document_findings,
                    extra_findings=extra,
                )
            )
            report_id = self.ids("rep")
            report["report_id"] = report_id
            evidence_hash = self._evidence_hash(batch)
            conn.execute(
                "INSERT INTO reports (report_id, batch_id, created_at, evidence_hash, data) VALUES (?,?,?,?,?)",
                (report_id, batch_id, self.clock(), evidence_hash, dumps(report)),
            )
            self._append_event("report_issued", batch, canonical_hash(_drop_none(report)))
            if report["status"] == "incomplete" and any(f["code"] == "FACTOR_WITHOUT_SOURCE" for f in report["findings"]):
                self._set_state(batch, "BLOCKED", "factor_without_source")
            return {**report, "evidence_hash": evidence_hash}

    def get_report(self, actor: ApiKey, batch_id: str) -> dict[str, Any]:
        batch = self._batch(batch_id)
        self._can_read(actor, batch, self._project(batch.project_id))
        report = self._latest_report(batch_id)
        if report is None:
            raise ApiError("NOT_FOUND", {"resource": "report", "batch_id": batch_id})
        rows = self.store.query("SELECT code, actor_id, reason, created_at FROM finding_overrides WHERE batch_id=? AND report_id=? ORDER BY created_at", (batch_id, report["report_id"]))
        return {**report, "overrides": [{"code": r["code"], "actor_id": r["actor_id"], "reason": r["reason"], "created_at": r["created_at"]} for r in rows]}

    def get_batch(self, actor: ApiKey, batch_id: str) -> dict[str, Any]:
        batch = self._batch(batch_id)
        self._can_read(actor, batch, self._project(batch.project_id))
        return {**batch.model_dump(), "evidence": [i.model_dump() for i in self._evidence(batch_id)]}

    # ------------------------------------------------------------------- issuance
    def _ledger_op(self, op_key: str) -> dict[str, Any] | None:
        row = self.store.one("SELECT status, result FROM ledger_ops WHERE op_key=?", (op_key,))
        return None if row is None else {"status": row["status"], "result": loads(row["result"]) if row["result"] else None}

    def issue(self, actor: ApiKey, batch_id: str, request_key: str) -> dict[str, Any]:
        """Issue credits for a VERIFIED batch.

        The whole operation runs under the store lock. The mint intent is committed before the ledger call and its
        result right after, under a key that depends only on the batch, so a retry after any failure reuses the
        recorded mint instead of minting again.
        """
        with self.store.lock():
            with self.store.transaction():
                batch = self._batch(batch_id)
                states.check_transition(batch.state, "ISSUED", actor.role, None)
                project = self._project(batch.project_id)
                profile = self._profile_of(batch)
                report = self._latest_report(batch_id)
                if report is None or report["status"] != "complete" or report["evidence_hash"] != self._evidence_hash(batch):
                    raise ApiError("STATE_TRANSITION_NOT_ALLOWED", {"from": batch.state, "to": "ISSUED", "reason": "no_current_complete_report"})
                if self._blocking_after_overrides(report):
                    raise ApiError("STATE_TRANSITION_NOT_ALLOWED", {"from": batch.state, "to": "ISSUED", "reason": "blocking_findings"})
                if self._facility_mass_finding(batch) is not None:
                    raise ApiError("STATE_TRANSITION_NOT_ALLOWED", {"from": batch.state, "to": "ISSUED", "reason": "facility_mass_exceeded"})
                units = min(int(report["issuable_kg"]), batch.claimed_kg_co2e)
                if units <= 0:
                    raise ApiError("INSUFFICIENT_BALANCE", {"required": 1, "available": units})
                ceiling = profile.plausibility("claimed_kg_co2e")
                if ceiling and Decimal(units) > ceiling[1]:
                    raise ApiError("VALIDATION_FAILED", {"field": "units", "rule": "above_ceiling"})
                op_key = sha256_hex(f"{batch_id}|issue".encode("utf-8"))
                known = self._ledger_op(op_key)
                if known is None:
                    self.store.execute(
                        "INSERT INTO ledger_ops (op_key, batch_id, action, status, result, created_at) VALUES (?,?,?,?,?,?)",
                        (op_key, batch_id, "issue", "pending", None, self.clock()),
                    )
                    self.store.checkpoint()  # the intent survives a crash or a rollback of this request
            if known is not None and known["status"] == "done":
                minted = MintResult(**known["result"])
                if minted.units != units:
                    raise ApiError("STATE_TRANSITION_NOT_ALLOWED", {"from": "VERIFIED", "to": "ISSUED", "reason": "mint_recorded_with_different_units", "recorded": minted.units, "current": units})
            else:
                marker = f" {SYNTHETIC_MARKER}" if project.provenance == "synthetic" else ""
                label = " ALTERNATIVE_PERMANENCE_MODEL_NOT_VM0044" if profile.alternative else ""
                minted = self.ledger.mint(op_key, batch_id, units, f"ClimAudit batch {batch_id} {report['report_id']}{label}{marker}")
                self.store.execute("UPDATE ledger_ops SET status='done', result=? WHERE op_key=?", (dumps(minted.as_dict()), op_key))
                self.store.checkpoint()  # the recorded mint survives a later failure, so a retry never asks the ledger again
            with self.store.transaction() as conn:
                batch = self._batch(batch_id)
                if batch.state != "VERIFIED":
                    raise ApiError("STATE_TRANSITION_NOT_ALLOWED", {"from": batch.state, "to": "ISSUED", "reason": "state_changed_after_mint"})
                credit_id = self.ids("cr")
                conn.execute(
                    "INSERT INTO credits (credit_id, batch_id, data) VALUES (?,?,?)",
                    (credit_id, batch_id, dumps({"credit_id": credit_id, "batch_id": batch_id, **minted.as_dict(), "provenance": project.provenance, "alternative_permanence_model": profile.alternative})),
                )
                conn.execute("INSERT INTO balances (credit_id, holder, units) VALUES (?,?,?)", (credit_id, project.owner_actor, minted.units))
                self._append_event("credit_issued", batch, canonical_hash({"credit_id": credit_id, **minted.as_dict()}))
                updated = self._set_state(batch, "ISSUED", "minted")
            return {"credit_id": credit_id, "units": minted.units, "token_id": minted.token_id, "tx_id": minted.tx_id, "batch": updated.model_dump()}

    def _credit(self, credit_id: str) -> dict[str, Any]:
        row = self.store.one("SELECT data FROM credits WHERE credit_id=?", (credit_id,))
        if row is None:
            raise ApiError("NOT_FOUND", {"resource": "credit", "id": credit_id})
        return loads(row["data"])

    def _balance(self, credit_id: str, holder: str) -> int:
        row = self.store.one("SELECT units FROM balances WHERE credit_id=? AND holder=?", (credit_id, holder))
        return int(row["units"]) if row else 0

    def get_credit(self, actor: ApiKey, credit_id: str) -> dict[str, Any]:
        credit = self._credit(credit_id)
        balances = {r["holder"]: r["units"] for r in self.store.query("SELECT holder, units FROM balances WHERE credit_id=?", (credit_id,))}
        privileged = actor.role in ("admin", "system", "verifier", "registry")
        if not privileged and actor.actor_id not in balances:
            raise ApiError("ROLE_NOT_AUTHORIZED", {"action": "read_credit"})
        if not privileged:
            balances = {actor.actor_id: balances[actor.actor_id]}  # a holder sees only its own balance
        retirements = [loads(r["data"]) for r in self.store.query("SELECT data FROM retirements WHERE credit_id=? ORDER BY rowid", (credit_id,))]
        if not privileged:
            retirements = [r for r in retirements if r.get("holder") == actor.actor_id]  # likewise, only its own retirements
        return {**credit, "balances": balances, "retirements": retirements}

    def _debit(self, conn: Any, credit_id: str, holder: str, units: int) -> None:
        """Atomic conditional debit: fails instead of going negative, whatever else runs concurrently."""
        cursor = conn.execute("UPDATE balances SET units=units-? WHERE credit_id=? AND holder=? AND units>=?", (units, credit_id, holder, units))
        if cursor.rowcount != 1:
            raise ApiError("INSUFFICIENT_BALANCE", {"required": units, "available": self._balance(credit_id, holder)})

    @staticmethod
    def _positive_units(units: Any) -> None:
        if not isinstance(units, int) or isinstance(units, bool) or units <= 0 or units > 2**53 - 1:
            raise ApiError("VALIDATION_FAILED", {"field": "units", "rule": "positive_integer_below_2_53"})

    def transfer(self, actor: ApiKey, credit_id: str, to_holder: str, units: int, request_key: str) -> dict[str, Any]:
        states.check_permission("credit.transfer", actor.role)
        self._positive_units(units)
        if not to_holder.strip() or to_holder == actor.actor_id or len(to_holder) > 128:
            raise ApiError("VALIDATION_FAILED", {"field": "to_holder", "rule": "different_non_empty_holder"})
        if self.known_holders is not None and to_holder not in self.known_holders:
            raise ApiError("VALIDATION_FAILED", {"field": "to_holder", "rule": "unknown_holder"})
        with self.store.transaction() as conn:
            credit = self._credit(credit_id)
            batch = self._batch(credit["batch_id"])
            op_key = sha256_hex(f"{credit_id}|transfer|{actor.actor_id}|{request_key}".encode("utf-8"))
            self._debit(conn, credit_id, actor.actor_id, units)
            tx = self.ledger.transfer(op_key, credit["token_id"], actor.actor_id, to_holder, units)
            conn.execute("INSERT INTO balances (credit_id, holder, units) VALUES (?,?,?) ON CONFLICT(credit_id, holder) DO UPDATE SET units=units+excluded.units", (credit_id, to_holder, units))
            self._append_event("credit_transferred", batch, canonical_hash({"credit_id": credit_id, "from": actor.actor_id, "to": to_holder, "units": units, "tx_id": tx}))
        return {"credit_id": credit_id, "from": actor.actor_id, "to": to_holder, "units": units, "tx_id": tx}

    def retire(self, actor: ApiKey, credit_id: str, units: int, beneficiary_ref: str, reason_code: str, request_key: str) -> dict[str, Any]:
        states.check_permission("credit.retire", actor.role)
        if reason_code not in ("voluntary_offset", "corporate_reporting", "research", "other"):
            raise ApiError("VALIDATION_FAILED", {"field": "reason_code", "rule": "enum"})
        if not beneficiary_ref.strip() or len(beneficiary_ref) > 128:
            raise ApiError("VALIDATION_FAILED", {"field": "beneficiary_ref", "rule": "required"})
        self._positive_units(units)
        with self.store.transaction() as conn:
            credit = self._credit(credit_id)
            batch = self._batch(credit["batch_id"])
            op_key = sha256_hex(f"{credit_id}|retire|{actor.actor_id}|{request_key}".encode("utf-8"))
            self._debit(conn, credit_id, actor.actor_id, units)
            tx = self.ledger.retire(op_key, credit["token_id"], actor.actor_id, units, beneficiary_ref, reason_code)
            retirement_id = self.ids("ret")
            conn.execute(
                "INSERT INTO retirements (retirement_id, credit_id, data) VALUES (?,?,?)",
                (retirement_id, credit_id, dumps({"retirement_id": retirement_id, "holder": actor.actor_id, "units": units, "beneficiary_ref": beneficiary_ref, "reason_code": reason_code, "tx_id": tx, "retired_at": self.clock()})),
            )
            remaining = conn.execute("SELECT COALESCE(SUM(units),0) AS total FROM balances WHERE credit_id=?", (credit_id,)).fetchone()["total"]
            self._append_event("credit_retired", batch, canonical_hash({"retirement_id": retirement_id, "credit_id": credit_id, "units": units, "beneficiary_ref": beneficiary_ref, "tx_id": tx}))
            current = self._batch(batch.batch_id)
            target = "RETIRED" if remaining == 0 else "PARTIALLY_RETIRED"
            if current.state != target and (current.state, target) in states.TRANSITIONS:
                self._set_state(current, target, "retirement")
        return {"retirement_id": retirement_id, "credit_id": credit_id, "units": units, "remaining_total_units": int(remaining), "tx_id": tx}
