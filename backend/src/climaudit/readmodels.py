"""Read-only views for the user interface: catalog, identity, public configuration, lists and document access.

Everything here reads through the same permission rules as the rest of the API (`Service._can_read` and the credit
balance rules); nothing here writes. Lists are role scoped: an owner sees its own projects and batches, a holder sees
the credits it holds, privileged roles (verifier, registry, admin, system) see everything.
"""
from __future__ import annotations

from typing import Any

from . import states
from .config import ApiKey, Settings
from .errors import HTTP_STATUS, ApiError
from .evidence import KINDS
from .findings import CATALOG
from .service import Service
from .store import loads

PRIVILEGED = ("admin", "system", "verifier", "registry")
MAX_LIST = 500


def catalog() -> dict[str, Any]:
    """Static vocabulary the interface needs to render and translate codes: findings, states, transitions, errors, evidence kinds."""
    return {
        "findings": [
            {"code": code, "severity": r.severity, "blocks_calculation": r.blocks_calculation, "blocks_verified": r.blocks_verified, "overridable": r.overridable}
            for code, r in sorted(CATALOG.items())
        ],
        "states": sorted({s for pair in states.TRANSITIONS for s in pair}),
        "transitions": [
            {"from": a, "to": b, "roles": sorted(roles), "reason_required": (a, b) in states.REASON_REQUIRED}
            for (a, b), roles in sorted(states.TRANSITIONS.items())
        ],
        "permissions": {action: sorted(roles) for action, roles in sorted(states.PERMISSIONS.items())},
        "errors": dict(sorted(HTTP_STATUS.items())),
        "evidence_kinds": {
            kind: {"value_type": s.value_type, "units": list(s.units), "enum": list(s.enum), "multi": s.multi, "scope": s.scope}
            for kind, s in sorted(KINDS.items())
        },
        "terminal_states": sorted(states.TERMINAL),
        "editable_states": sorted(states.EDITABLE_STATES),
    }


def public_config(settings: Settings) -> dict[str, Any]:
    on_chain = settings.ledger_mode in ("direct", "guardian")
    network = settings.hedera_network if on_chain else None
    return {
        "ledger_mode": settings.ledger_mode,
        "network": network,
        "hashscan_base": f"https://hashscan.io/{network}" if network else None,
        "provenance_mode": "synthetic" if settings.force_synthetic else "mixed",
        "external_checks": settings.external_checks,
        "env": settings.env,
    }


def me(actor: ApiKey) -> dict[str, str]:
    return {"actor_id": actor.actor_id, "role": actor.role}


class ReadModels:
    def __init__(self, service: Service):
        self.s = service

    # ------------------------------------------------------------------ helpers
    def _limit(self, limit: int) -> int:
        if limit < 1 or limit > MAX_LIST:
            raise ApiError("VALIDATION_FAILED", {"field": "limit", "rule": f"1_to_{MAX_LIST}"})
        return limit

    def _report_summary(self, batch_id: str) -> dict[str, Any] | None:
        report = self.s._latest_report(batch_id)
        if report is None:
            return None
        return {
            "report_id": report["report_id"], "status": report.get("status"), "recommendation": report.get("recommendation"),
            "kg_co2e": report.get("kg_co2e"), "issuable_kg": report.get("issuable_kg"), "finding_codes": [f["code"] for f in report.get("findings", [])],
        }

    # ------------------------------------------------------------------ lists
    def projects(self, actor: ApiKey, limit: int = 100) -> list[dict[str, Any]]:
        limit = self._limit(limit)
        if actor.role == "extractor":
            raise ApiError("ROLE_NOT_AUTHORIZED", {"action": "list_projects"})
        out = []
        for row in self.s.store.query("SELECT data FROM projects"):
            project = loads(row["data"])
            if actor.role in PRIVILEGED or project.get("owner_actor") == actor.actor_id:
                facilities = [loads(r["data"]) for r in self.s.store.query("SELECT data FROM facilities WHERE project_id=?", (project["project_id"],))]
                out.append({**project, "facilities": [{"facility_id": f["facility_id"], "process": f.get("process"), "declared_class": f.get("declared_class"), "cell": f.get("cell")} for f in facilities]})
        return sorted(out, key=lambda p: p.get("created_at", ""), reverse=True)[:limit]

    def batches(self, actor: ApiKey, limit: int = 100) -> list[dict[str, Any]]:
        limit = self._limit(limit)
        if actor.role == "extractor":
            raise ApiError("ROLE_NOT_AUTHORIZED", {"action": "list_batches"})
        owners = {loads(r["data"])["project_id"]: loads(r["data"]).get("owner_actor") for r in self.s.store.query("SELECT data FROM projects")}
        out = []
        for row in self.s.store.query("SELECT data FROM batches"):
            batch = loads(row["data"])
            visible = actor.role in PRIVILEGED or owners.get(batch["project_id"]) == actor.actor_id or self.s._holds_credit_of(actor, batch["batch_id"])
            if not visible:
                continue
            out.append({
                "batch_id": batch["batch_id"], "project_id": batch["project_id"], "facility_id": batch["facility_id"], "year": batch["year"],
                "biochar_type": batch["biochar_type"], "application_type": batch["application_type"], "state": batch["state"],
                "claimed_kg_co2e": batch.get("claimed_kg_co2e"), "created_at": batch.get("created_at"), "updated_at": batch.get("updated_at"),
                "report": self._report_summary(batch["batch_id"]),
            })
        return sorted(out, key=lambda b: b.get("updated_at") or b.get("created_at") or "", reverse=True)[:limit]

    def credits(self, actor: ApiKey, limit: int = 100) -> list[dict[str, Any]]:
        limit = self._limit(limit)
        if actor.role == "extractor":
            raise ApiError("ROLE_NOT_AUTHORIZED", {"action": "list_credits"})
        out = []
        for row in self.s.store.query("SELECT credit_id FROM credits"):
            try:
                out.append(self.s.get_credit(actor, row["credit_id"]))
            except ApiError as exc:
                if exc.code != "ROLE_NOT_AUTHORIZED":
                    raise
        return out[:limit]

    # ------------------------------------------------------------------ documents
    def documents(self, actor: ApiKey, batch_id: str) -> list[dict[str, Any]]:
        batch = self.s._batch(batch_id)
        self.s._can_read(actor, batch, self.s._project(batch.project_id))
        rows = self.s.store.query("SELECT document_ref, filename, media_type, size, sha256, findings FROM documents WHERE batch_id=? ORDER BY rowid", (batch_id,))
        return [
            {"document_ref": r["document_ref"], "filename": r["filename"], "media_type": r["media_type"], "size": r["size"], "sha256": r["sha256"], "findings": loads(r["findings"])}
            for r in rows
        ]

    def document_text(self, actor: ApiKey, document_ref: str) -> dict[str, str]:
        return {"document_ref": document_ref, "text": self.s.get_visible_text(actor, document_ref)}
