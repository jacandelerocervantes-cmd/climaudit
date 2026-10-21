"""End-to-end test of the whole backend on the REAL ledger selected by the environment (Hedera testnet in direct mode).

Skipped unless CP_LIVE_E2E=1. It drives the API through submission, verification, issuance, transfer and retirement,
then checks that the local audit chain matches what the mirror node returns. It writes real testnet transactions.
    CP_LIVE_E2E=1 CP_LEDGER_MODE=direct (+ the CP_HEDERA_* / CP_HCS_* / CP_HTS_* variables) pytest tests/test_e2e_live.py
"""
from __future__ import annotations

import os
import time
from datetime import datetime, timezone

import pytest
from fastapi.testclient import TestClient

from climaudit.api.app import create_app
from climaudit.config import Settings, load_settings
from climaudit.ledger.adapters import build_ledger
from climaudit.store import Store

from .conftest import KEYS, Client
from .test_api_flow import issued

pytestmark = pytest.mark.skipif(os.environ.get("CP_LIVE_E2E") != "1", reason="set CP_LIVE_E2E=1 to run against the configured real ledger")


def now() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def test_full_lifecycle_on_the_configured_real_ledger():
    settings = load_settings()
    assert settings.ledger_mode in ("direct", "guardian"), "configure a real ledger mode"
    ledger = build_ledger(settings, now)
    store = Store(":memory:")
    app = create_app(Settings(api_keys=dict(KEYS)), ledger=ledger, store=store, clock=now)
    client = Client(TestClient(app, raise_server_exceptions=False))
    client.app = app
    _p, _f, batch, _r, credit = issued(client)
    cid = credit["credit_id"]
    client.ok("POST", f"/credits/{cid}/transfer", "owner", {"to_holder": "buyer-1", "units": 1000})
    client.ok("POST", f"/credits/{cid}/retire", "holder", {"units": 400, "beneficiary_ref": "ben-1", "reason_code": "voluntary_offset"})
    verdict = {}
    for _ in range(15):  # the mirror node lags consensus by a few seconds
        verdict = client.ok("GET", "/audit/verify", "verifier")
        if verdict.get("ledger_matches"):
            break
        time.sleep(3)
    assert verdict["chain_ok"] and verdict["ledger_matches"], verdict
    events = client.ok("GET", f"/audit/{batch['batch_id']}", "owner")
    assert events and all(e["ledger_ref"]["tx_id"] for e in events)
    store.close()
