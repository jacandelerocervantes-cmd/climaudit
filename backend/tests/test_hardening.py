"""Hardening after the second independent review: durable issuance intent, streamed body limit, known transfer
recipients, /docs off by default, idempotency purge and a document quota per batch."""
from __future__ import annotations

import itertools

from fastapi.testclient import TestClient

from climaudit.api.app import create_app
from climaudit.config import Settings, load_settings
from climaudit.ledger.fake import FakeLedger
from climaudit.pdfgen import Run, make_pdf
from climaudit.store import Store

from .conftest import KEYS, Client, b64
from .test_api_flow import code, issued, setup_batch, verified_batch


class NonDedupingLedger(FakeLedger):
    """A ledger that cannot recognise a repeated operation key, like a real chain without an idempotency key."""

    def mint(self, op_key, batch_id, units, memo):  # noqa: D102
        return super().mint(f"{op_key}-{len(self.mints)}", batch_id, units, memo)


def build(settings=None, ledger=None, clock=None):
    counter = itertools.count()
    clock = clock or (lambda: f"2026-10-16T{next(counter) // 3600 % 24:02d}:{next(counter) // 60 % 60:02d}:{next(counter) % 60:02d}Z")
    ledger = ledger or FakeLedger(clock)
    store = Store(":memory:")
    app = create_app(settings or Settings(api_keys=dict(KEYS)), ledger=ledger, store=store, clock=clock)
    client = Client(TestClient(app, raise_server_exceptions=False))
    client.app = app
    return client, ledger, store


def test_issuance_intent_survives_a_failed_mint_and_the_retry_mints_once():
    client, ledger, store = build(ledger=NonDedupingLedger(lambda: "t"))
    _p, _f, batch, _r = verified_batch(client)
    bid = batch["batch_id"]
    ledger.fail_next("unavailable", on="mint")
    broken = client.call("POST", f"/batches/{bid}/issue", "registry", key="a")
    assert broken.status_code == 503 and len(ledger.mints) == 0
    row = store.one("SELECT status FROM ledger_ops WHERE batch_id=?", (bid,))
    assert row is not None and row["status"] == "pending"  # the intent was committed before the ledger call
    assert client.call("POST", f"/batches/{bid}/issue", "registry", key="b").status_code == 200
    assert len(ledger.mints) == 1


def test_recorded_mint_survives_a_later_failure_and_the_ledger_is_not_asked_again():
    client, ledger, store = build(ledger=NonDedupingLedger(lambda: "t"))
    _p, _f, batch, _r = verified_batch(client)
    bid = batch["batch_id"]
    ledger.fail_next("unavailable", on="anchor")  # the mint succeeds, the audit anchor right after it fails
    assert client.call("POST", f"/batches/{bid}/issue", "registry", key="a").status_code == 503
    row = store.one("SELECT status, result FROM ledger_ops WHERE batch_id=?", (bid,))
    assert row["status"] == "done" and row["result"]  # the mint result outlived the rolled-back request
    assert store.one("SELECT COUNT(*) AS n FROM credits")["n"] == 0
    assert client.call("POST", f"/batches/{bid}/issue", "registry", key="b").status_code == 200
    assert len(ledger.mints) == 1  # a ledger without idempotency would have minted twice


def test_chunked_bodies_above_the_limit_are_refused_and_small_ones_pass():
    client, _ledger, _store = build(Settings(api_keys=dict(KEYS), max_upload_bytes=1000))
    headers = {"Authorization": "Bearer k-owner", "Idempotency-Key": "big"}

    def chunks(n):
        for _ in range(n):
            yield b'{"country": "MX", "pad": "' + b"x" * 400 + b'"}'

    big = client.http.post("/projects", content=chunks(10), headers=headers)  # no Content-Length: chunked
    assert big.status_code == 413 and big.json()["error"]["params"]["rule"] == "body_too_large"
    ok = client.http.post("/projects", json={"country": "MX"}, headers={**headers, "Idempotency-Key": "small"})
    assert ok.status_code in (200, 201)


def test_transfers_only_go_to_known_holders():
    client, _ledger, _store = build()
    _p, _f, _b, _r, credit = issued(client)
    cid = credit["credit_id"]
    refused = client.call("POST", f"/credits/{cid}/transfer", "owner", {"to_holder": "ghost-holder", "units": 1})
    assert code(refused) == "VALIDATION_FAILED" and refused.json()["error"]["params"]["rule"] == "unknown_holder"
    assert client.call("POST", f"/credits/{cid}/transfer", "owner", {"to_holder": "buyer-1", "units": 1}).status_code == 200
    assert client.call("POST", f"/credits/{cid}/transfer", "owner", {"to_holder": "bad holder!", "units": 1}).status_code == 422


def test_docs_are_off_by_default_and_on_only_for_dev():
    assert Settings().env == "prod" and load_settings({}).env == "prod"
    client, _ledger, _store = build(Settings(api_keys=dict(KEYS)))
    assert client.http.get("/docs").status_code == 404 and client.http.get("/openapi.json").status_code == 404
    dev, _l, _s = build(Settings(api_keys=dict(KEYS), env="dev"))
    assert dev.http.get("/openapi.json").status_code == 200


def test_expired_idempotency_rows_are_purged_by_later_requests():
    now = {"t": "2026-10-16T00:00:00Z"}
    client, _ledger, store = build(clock=lambda: now["t"])
    client.ok("POST", "/projects", "owner", {"country": "MX"})
    assert store.one("SELECT COUNT(*) AS n FROM idempotency")["n"] == 1
    now["t"] = "2026-10-17T01:00:00Z"  # 25 hours later
    client.ok("POST", "/projects", "owner", {"country": "MX"})
    assert store.one("SELECT COUNT(*) AS n FROM idempotency")["n"] == 1  # only the new row is left


def test_document_quota_per_batch():
    client, _ledger, _store = build(Settings(api_keys=dict(KEYS), max_documents_per_batch=2))
    _p, _f, batch = setup_batch(client)
    bid = batch["batch_id"]
    for i in range(2):
        pdf = make_pdf([[Run(f"Lab report {i} H/Corg 0.2")]])
        client.ok("POST", f"/batches/{bid}/documents", "owner", {"filename": f"lab{i}.pdf", "media_type": "application/pdf", "content_base64": b64(pdf)})
    pdf = make_pdf([[Run("Lab report 3 H/Corg 0.2")]])
    third = client.call("POST", f"/batches/{bid}/documents", "owner", {"filename": "lab3.pdf", "media_type": "application/pdf", "content_base64": b64(pdf)})
    assert third.status_code == 422 and third.json()["error"]["params"]["rule"] == "too_many_documents"
