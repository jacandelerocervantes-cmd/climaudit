"""Run the whole ClimAudit lifecycle on the configured ledger and print a readable story (for the demo video).

Usage (from the backend folder, with the .venv active and the ledger variables loaded, see README.md):
    python scripts/demo_flow.py            # uses CP_LEDGER_MODE (fake, direct or guardian)

It starts the API in-process with temporary role keys, so no server and no real keys are needed, then walks one
synthetic batch through: submit evidence, verification, human decision, issuance, transfer, retirement and the
audit check. It then submits a second batch on the same parcel to show the double-counting guard. Every ledger
write goes to the ledger selected by CP_LEDGER_MODE; with `direct` or `guardian` these are real Hedera testnet
transactions. All data is synthetic and labelled SYNTHETIC_DEMO_DATA.
"""
from __future__ import annotations

import base64
import os
import sys
import time
import uuid
from datetime import datetime, timezone
from pathlib import Path


def load_dotenv() -> None:
    path = Path(__file__).resolve().parent.parent / ".env"
    if not path.exists():
        return
    for line in path.read_text(encoding="utf-8").splitlines():
        name, _, value = line.strip().partition("=")
        if name and not name.startswith("#") and value.strip() and name.strip() not in os.environ:
            os.environ[name.strip()] = value.strip().strip('"').strip("'")


def now() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def main() -> int:
    load_dotenv()
    from fastapi.testclient import TestClient  # noqa: PLC0415

    from climaudit import dossiers as d  # noqa: PLC0415
    from climaudit.api.app import create_app  # noqa: PLC0415
    from climaudit.config import ApiKey, Settings, load_settings  # noqa: PLC0415
    from climaudit.ledger.adapters import build_ledger  # noqa: PLC0415
    from climaudit.pdfgen import Run, make_pdf  # noqa: PLC0415
    from climaudit.store import Store  # noqa: PLC0415

    env = load_settings()
    keys = {f"demo-{role}-{uuid.uuid4().hex[:8]}": ApiKey(actor, role) for actor, role in (
        ("owner-1", "owner"), ("verifier-1", "verifier"), ("registry-1", "registry"), ("buyer-1", "holder"), ("admin-1", "admin"))}
    key_of = {k.role: name for name, k in keys.items()}
    ledger = build_ledger(env, now)
    app = create_app(Settings(api_keys=keys), ledger=ledger, store=Store(":memory:"), clock=now)
    http = TestClient(app, raise_server_exceptions=False)

    def call(method: str, path: str, role: str, body: dict | None = None) -> dict | list:
        headers = {"Authorization": f"Bearer {key_of[role]}"}
        if method == "POST" or method == "PUT":
            headers["Idempotency-Key"] = uuid.uuid4().hex
        r = http.request(method, path, json=body, headers=headers)
        if r.status_code >= 300:
            print(f"   ERROR {r.status_code}: {r.text[:300]}")
            raise SystemExit(1)
        return r.json()

    def payload(items):
        return {"items": [{"kind": i.kind, "value": i.value, "unit": i.unit, "group": i.group, "provenance": i.provenance, "rel_uncertainty": i.rel_uncertainty, "document_ref": i.document_ref} for i in items]}

    def step(title: str) -> None:
        print(f"\n== {title}")

    print(f"ClimAudit demo | ledger mode: {ledger.mode} | all data synthetic (SYNTHETIC_DEMO_DATA)")

    step("1. Project owner registers a project, a facility and a batch")
    project = call("POST", "/projects", "owner", {"country": "MX"})
    facility = call("POST", f"/projects/{project['project_id']}/facilities", "owner", {"process": "pyrolysis", "pyrolysis_gas_combusted": True, "heat_use_pct": "80", "pollution_controls": True, "temperature_measured": True, "declared_class": "high"})
    call("PUT", f"/facilities/{facility['facility_id']}/years/2026/evidence", "owner", payload(d.base_facility_year()))
    parcel = f"PARCEL-{uuid.uuid4().hex[:6]}"
    batch_body = {"facility_id": facility["facility_id"], "year": 2026, "biochar_type": "agricultural_residue", "parcel_key": parcel, "cell_set": list(d.CELLS_A), "period_start": "2026-01-01", "period_end": "2026-07-01", "claimed_kg_co2e": 300000}
    batch = call("POST", "/batches", "owner", batch_body)
    bid = batch["batch_id"]
    call("POST", f"/batches/{bid}/evidence", "owner", payload(d.replace_item(d.replace_item(d.base_evidence(), "application_date", "2026-03-01"), "production_date", "2026-02-01")))
    pdf = make_pdf([[Run("Laboratory report: H/Corg 0.2, organic carbon 40 percent")]])
    doc = call("POST", f"/batches/{bid}/documents", "owner", {"filename": "lab.pdf", "media_type": "application/pdf", "content_base64": base64.b64encode(pdf).decode()})
    print(f"   batch {bid}; claimed 300000 kg CO2e; document sanitizer findings: {len(doc['findings'])}")

    step("2. Verification: deterministic VM0044 calculation, rules and guards")
    call("POST", f"/batches/{bid}/transitions", "owner", {"to": "SUBMITTED"})
    report = call("POST", f"/batches/{bid}/verification", "verifier")
    kg = report["kg_co2e"]
    print(f"   status {report['status']}; kg CO2e low/central/high = {kg['low']} / {kg['central']} / {kg['high']}; issuable {report['issuable_kg']} kg (lower bound, claim 300000)")
    print(f"   recommendation: {report['recommendation']}; findings: {[f['code'] for f in report['findings']]}")

    step("3. Human verifier decides, registry issues")
    call("POST", f"/batches/{bid}/transitions", "verifier", {"to": "VERIFIED"})
    credit = call("POST", f"/batches/{bid}/issue", "registry")
    cid, units = credit["credit_id"], credit["units"]
    print(f"   issued {units} units (1 unit = 1 kg CO2e); token {credit.get('token_id')}; mint tx {credit.get('mint_tx_id') or credit.get('tx_id')}")

    step("4. Transfer to a buyer and retire")
    call("POST", f"/credits/{cid}/transfer", "owner", {"to_holder": "buyer-1", "units": 1000})
    retired = call("POST", f"/credits/{cid}/retire", "holder", {"units": 400, "beneficiary_ref": "ben-001", "reason_code": "voluntary_offset"})
    print(f"   retired 400 units; remaining {retired['remaining_total_units']}")

    step("5. Audit: hash chain checked against the public ledger")
    events = call("GET", f"/audit/{bid}", "owner")
    verdict = call("GET", "/audit/verify", "verifier")
    local = [e["hash"] for e in events]
    in_order = False
    for _ in range(12):  # the public mirror node lags consensus by a few seconds
        it = iter(ledger.published_hashes())
        in_order = all(any(h == p for p in it) for h in local)  # this run's hashes appear in the ledger, in order
        if in_order:
            break
        time.sleep(3)
    print(f"   {len(events)} events; hash chain intact: {verdict['chain_ok']}; this run's hashes found in the ledger in order: {in_order}")
    for e in events:
        ref = e["ledger_ref"]
        print(f"   - {e['type']:<18} seq {ref['sequence']:<4} topic {ref['topic_id']}  tx {ref.get('tx_id', '')}")
    topic = events[0]["ledger_ref"]["topic_id"]
    if not str(topic).startswith("fake"):
        print(f"   topic:  https://hashscan.io/testnet/topic/{topic}")
    if credit.get("token_id") and not str(credit["token_id"]).startswith("fake"):
        print(f"   token:  https://hashscan.io/testnet/token/{credit['token_id']}")

    step("6. Double counting: a second batch on the same parcel")
    batch2 = call("POST", "/batches", "owner", {**batch_body, "parcel_key": parcel + "-b"})
    call("POST", f"/batches/{batch2['batch_id']}/evidence", "owner", payload(d.replace_item(d.replace_item(d.base_evidence(), "application_date", "2026-03-01"), "production_date", "2026-02-01")))
    r = http.post(f"/batches/{batch2['batch_id']}/transitions", json={"to": "SUBMITTED"}, headers={"Authorization": f"Bearer {key_of['owner']}", "Idempotency-Key": uuid.uuid4().hex})
    error = r.json().get("error", {})
    params = error.get("params", {})
    print(f"   submission refused: HTTP {r.status_code} {error.get('code')} ({params.get('reason')}) with batch {params.get('conflicting_batch_id')}")
    print("\nDone. Nothing here is a real credit: testnet only, synthetic data.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
