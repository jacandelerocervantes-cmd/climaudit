"""Read routes for the user interface: identity, config, catalog, role-scoped lists and documents."""
from __future__ import annotations

from climaudit.config import Settings
from climaudit.findings import CATALOG
from climaudit.pdfgen import Run, make_pdf

from .conftest import b64
from .test_api_flow import code, issued, setup_batch, verified_batch


def test_me_config_and_catalog(env):
    client, _service, _ledger, _store = env
    assert client.ok("GET", "/me", "verifier") == {"actor_id": "verifier-1", "role": "verifier"}
    cfg = client.ok("GET", "/config", "owner")
    assert cfg["ledger_mode"] == "fake" and cfg["network"] is None and cfg["hashscan_base"] is None and cfg["provenance_mode"] == "synthetic"
    cat = client.ok("GET", "/catalog", "holder")
    assert {f["code"] for f in cat["findings"]} == set(CATALOG)
    assert {"from": "VERIFIED", "to": "ISSUED", "roles": ["registry"], "reason_required": False} in cat["transitions"]
    assert cat["errors"]["BATCH_PERIOD_OVERLAP"] == 409 and "dry_mass_biochar" in cat["evidence_kinds"]
    assert code(client.call("GET", "/catalog", None)) == "AUTH_REQUIRED"


def test_public_config_reports_the_network_only_for_real_ledgers():
    from climaudit.readmodels import public_config

    assert public_config(Settings(ledger_mode="direct"))["hashscan_base"] == "https://hashscan.io/testnet"
    assert public_config(Settings(ledger_mode="fake"))["hashscan_base"] is None


def test_lists_are_role_scoped(env):
    client, _service, _ledger, _store = env
    _p, _f, batch, report = verified_batch(client)
    bid = batch["batch_id"]
    mine = client.ok("GET", "/batches", "owner")
    assert [b["batch_id"] for b in mine] == [bid] and mine[0]["state"] == "VERIFIED"
    assert mine[0]["report"]["kg_co2e"]["central"] == report["kg_co2e"]["central"] and mine[0]["report"]["issuable_kg"] == report["issuable_kg"]
    assert client.ok("GET", "/batches", "verifier")[0]["batch_id"] == bid  # privileged roles see all
    other = client.call("GET", "/batches", "admin")
    assert other.status_code == 200 and len(other.json()) == 1
    # a second owner sees nothing of the first owner's work
    stranger = client.http.get("/batches", headers={"Authorization": "Bearer k-owner2"})
    assert stranger.status_code == 200 and stranger.json() == []
    assert len(client.ok("GET", "/projects", "owner")) == 1 and client.ok("GET", "/projects", "owner")[0]["facilities"]
    assert client.http.get("/projects", headers={"Authorization": "Bearer k-owner2"}).json() == []
    assert code(client.call("GET", "/batches", "extractor")) == "ROLE_NOT_AUTHORIZED"
    assert code(client.call("GET", "/batches?limit=0", "owner")) == "VALIDATION_FAILED"


def test_credit_lists_follow_balances(env):
    client, _service, _ledger, _store = env
    _p, _f, _b, _r, credit = issued(client)
    cid, units = credit["credit_id"], credit["units"]
    assert client.ok("GET", "/credits", "owner")[0]["balances"] == {"owner-1": units}
    assert client.ok("GET", "/credits", "holder") == []  # the buyer holds nothing yet
    client.ok("POST", f"/credits/{cid}/transfer", "owner", {"to_holder": "buyer-1", "units": 5})
    held = client.ok("GET", "/credits", "holder")
    assert len(held) == 1 and held[0]["balances"] == {"buyer-1": 5}
    assert [b["state"] for b in client.ok("GET", "/batches", "holder")] == ["ISSUED"]


def test_documents_list_and_sanitized_text(env):
    client, _service, _ledger, _store = env
    _p, _f, batch = setup_batch(client)
    bid = batch["batch_id"]
    pdf = make_pdf([[Run("Lab report H/Corg 0.2")]])
    doc = client.ok("POST", f"/batches/{bid}/documents", "owner", {"filename": "lab.pdf", "media_type": "application/pdf", "content_base64": b64(pdf)})
    listed = client.ok("GET", f"/batches/{bid}/documents", "owner")
    assert [d["document_ref"] for d in listed] == [doc["document_ref"]] and listed[0]["sha256"] == doc["sha256"] and listed[0]["findings"] == []
    text = client.ok("GET", f"/documents/{doc['document_ref']}/text", "verifier")
    assert "H/Corg 0.2" in text["text"]
    stranger = client.http.get(f"/batches/{bid}/documents", headers={"Authorization": "Bearer k-owner2"})
    assert stranger.status_code == 403
    assert client.http.get(f"/documents/{doc['document_ref']}/text", headers={"Authorization": "Bearer k-owner2"}).status_code == 403


def test_report_lists_the_overrides_accepted_for_it(env):
    client, service, _ledger, store = env
    _p, _f, batch = setup_batch(client)
    bid = batch["batch_id"]
    client.ok("POST", f"/batches/{bid}/transitions", "owner", {"to": "SUBMITTED"})
    report = client.ok("POST", f"/batches/{bid}/verification", "verifier")
    assert client.ok("GET", f"/batches/{bid}/report", "verifier")["overrides"] == []
    store.execute(
        "INSERT INTO finding_overrides (batch_id, code, report_id, actor_id, reason, created_at) VALUES (?,?,?,?,?,?)",
        (bid, "BENFORD_ANOMALY", report["report_id"], "verifier-1", "checked the logs", "2026-10-18T00:00:00Z"),
    )
    listed = client.ok("GET", f"/batches/{bid}/report", "owner")["overrides"]
    assert listed == [{"code": "BENFORD_ANOMALY", "actor_id": "verifier-1", "reason": "checked the logs", "created_at": "2026-10-18T00:00:00Z"}]


def test_credit_lists_retirements_scoped_like_balances(env):
    client, _service, _ledger, _store = env
    _p, _f, _b, _r, credit = issued(client)
    cid = credit["credit_id"]
    client.ok("POST", f"/credits/{cid}/transfer", "owner", {"to_holder": "buyer-1", "units": 1000})
    client.ok("POST", f"/credits/{cid}/retire", "holder", {"units": 400, "beneficiary_ref": "ben-1", "reason_code": "voluntary_offset"})
    client.ok("POST", f"/credits/{cid}/retire", "owner", {"units": 100, "beneficiary_ref": "ben-2", "reason_code": "research"})
    everything = client.ok("GET", f"/credits/{cid}", "verifier")["retirements"]
    assert sorted((r["holder"], r["units"]) for r in everything) == [("buyer-1", 400), ("owner-1", 100)]
    mine = client.ok("GET", f"/credits/{cid}", "holder")["retirements"]
    assert [(r["holder"], r["units"], r["beneficiary_ref"]) for r in mine] == [("buyer-1", 400, "ben-1")]
    assert all(r["tx_id"] and r["retired_at"] for r in everything)
