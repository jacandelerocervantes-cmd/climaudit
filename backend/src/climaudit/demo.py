"""Synthetic demo data shared by the development launcher and the snapshot generator.

`seed_demo` drives the public API through a `call(method, path, role, body)` function (an HTTP client or an in-process
test client), so the data it creates goes through exactly the same rules, state machine and ledger as real input.
All of it is synthetic and labelled so. Nothing here is imported by the API itself.
"""
from __future__ import annotations

import base64
from collections.abc import Callable
from typing import Any

from . import dossiers as d
from .pdfgen import Run, make_pdf

Call = Callable[[str, str, str, "dict[str, Any] | None"], Any]

ROLES = {"owner": "owner-1", "verifier": "verifier-1", "registry": "registry-1", "holder": "buyer-1", "admin": "admin-1"}


def payload(items: list[Any]) -> dict[str, Any]:
    return {"items": [{"kind": i.kind, "value": i.value, "unit": i.unit, "group": i.group, "provenance": i.provenance, "rel_uncertainty": i.rel_uncertainty, "document_ref": i.document_ref} for i in items]}


def seed_demo(call: Call, lifecycle: bool = False) -> dict[str, str]:
    """Create a project, a facility and three batches. With `lifecycle`, the first batch also gets issued, transferred and retired.

    Returns the ids: {"verified": ..., "review": ..., "draft": ...}.
    """
    project = call("POST", "/projects", "owner", {"country": "MX"})
    facility = call("POST", f"/projects/{project['project_id']}/facilities", "owner", {"process": "pyrolysis", "pyrolysis_gas_combusted": True, "heat_use_pct": "80", "pollution_controls": True, "temperature_measured": True, "declared_class": "high"})
    call("PUT", f"/facilities/{facility['facility_id']}/years/2026/evidence", "owner", payload(d.replace_item(d.base_facility_year(), "facility_total_dry_mass", "250", unit="t")))
    base = d.replace_item(d.replace_item(d.base_evidence(), "application_date", "2026-03-01"), "production_date", "2026-02-01")
    evidence = payload(base)
    # One batch carries a biochar leg of exactly 200 km, so its report has an overridable finding to look at.
    evidence_threshold = payload(d.replace_item(base, "transport_distance_km_return", "200", unit="km", group="leg-2"))

    def batch(parcel: str, cells: list[str], claimed: int, items: dict[str, Any] | None = None) -> str:
        created = call("POST", "/batches", "owner", {"facility_id": facility["facility_id"], "year": 2026, "biochar_type": "agricultural_residue", "parcel_key": parcel, "cell_set": cells, "period_start": "2026-01-01", "period_end": "2026-07-01", "claimed_kg_co2e": claimed})
        call("POST", f"/batches/{created['batch_id']}/evidence", "owner", items or evidence)
        pdf = base64.b64encode(make_pdf([[Run(f"Laboratory report for {parcel}: H/Corg 0.2, organic carbon 40 percent")]])).decode()  # distinct per batch
        call("POST", f"/batches/{created['batch_id']}/documents", "owner", {"filename": "lab.pdf", "media_type": "application/pdf", "content_base64": pdf})
        return str(created["batch_id"])

    verified = batch("PARCEL-A", list(d.CELLS_A), 300000)
    call("POST", f"/batches/{verified}/transitions", "owner", {"to": "SUBMITTED"})
    call("POST", f"/batches/{verified}/verification", "verifier", None)
    call("POST", f"/batches/{verified}/transitions", "verifier", {"to": "VERIFIED"})
    review = batch("PARCEL-C", list(d.CELLS_C), 280000, evidence_threshold)
    call("POST", f"/batches/{review}/transitions", "owner", {"to": "SUBMITTED"})
    call("POST", f"/batches/{review}/verification", "verifier", None)
    draft = batch("PARCEL-B-DRAFT", list(d.CELLS_B), 150000)

    if lifecycle:
        credit = call("POST", f"/batches/{verified}/issue", "registry", None)
        call("POST", f"/credits/{credit['credit_id']}/transfer", "owner", {"to_holder": ROLES["holder"], "units": 5000})
        call("POST", f"/credits/{credit['credit_id']}/retire", "holder", {"units": 1200, "beneficiary_ref": "Demo Foods Ltd", "reason_code": "voluntary_offset"})
        call("POST", f"/batches/{review}/findings/override", "verifier", {"code": "TRANSPORT_DISTANCE_AT_THRESHOLD", "reason": "Checked the freight invoice: the leg is 200 km (recorded demo run)."})
    return {"verified": verified, "review": review, "draft": draft}
