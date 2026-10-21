"""Direct Hedera adapter tests against an in-memory gateway (no network, no credentials).

A live test against Hedera testnet exists in test_hedera_live.py and runs only when CP_LIVE_HEDERA=1 and credentials are set.
"""
from __future__ import annotations

import base64
import json

import pytest
from fastapi.testclient import TestClient

from climaudit.api.app import create_app
from climaudit.config import Settings
from climaudit.errors import ApiError
from climaudit.ledger.adapters import IncompleteDirectConfig, build_ledger
from climaudit.ledger.hedera import (
    HCS_MESSAGE_LIMIT_BYTES,
    MEMO_LIMIT_BYTES,
    DirectHederaAdapter,
    FoundTx,
    SdkGateway,
    message_payload,
)
from climaudit.ledger.port import SYNTHETIC_MARKER
from climaudit.store import Store

from .conftest import KEYS, Client
from .test_api_flow import issued

TOPIC, TOKEN = "0.0.1111", "0.0.2222"


class FakeGateway:
    """Behaves like the Hedera gateway: append-only topic, mints and burns recorded with their memos."""

    def __init__(self):
        self.messages: list[bytes] = []
        self.txs: list[dict] = []
        self.fail_message = False

    def submit_message(self, topic_id, payload):
        if self.fail_message:
            raise ApiError("LEDGER_UNAVAILABLE", {"reason": "sdk_error"})
        assert topic_id == TOPIC and len(payload) <= HCS_MESSAGE_LIMIT_BYTES
        self.messages.append(payload)
        return len(self.messages), f"0.0.9@1.{len(self.messages)}"

    def _record(self, kind, amount, memo):
        assert len(memo.encode("utf-8")) <= MEMO_LIMIT_BYTES
        tx_id = f"0.0.9@2.{len(self.txs) + 1}"
        self.txs.append({"kind": kind, "amount": amount, "memo": memo, "tx_id": tx_id})
        return tx_id

    def mint(self, token_id, amount, memo):
        assert token_id == TOKEN
        return self._record("TOKENMINT", amount, memo)

    def burn(self, token_id, amount, memo):
        assert token_id == TOKEN
        return self._record("TOKENBURN", amount, memo)

    def find_by_memo(self, kind, memo_prefix):
        for tx in self.txs:
            if tx["kind"] == kind and tx["memo"].startswith(memo_prefix):
                return FoundTx(tx["tx_id"], tx["amount"])
        return None

    def list_messages(self, topic_id):
        return list(self.messages)


def adapter():
    gateway = FakeGateway()
    return DirectHederaAdapter(gateway, TOPIC, TOKEN), gateway


def test_anchor_publishes_a_compact_message_with_only_the_hash_and_ids():
    ledger, gateway = adapter()
    ref = ledger.anchor("a" * 64, {"type": "batch_submitted", "batch_id": "b-1", "seq": 7})
    assert (ref.topic_id, ref.sequence, ref.tx_id) == (TOPIC, 1, "0.0.9@1.1")
    body = json.loads(gateway.messages[0])
    assert body == {"v": 1, "h": "a" * 64, "t": "batch_submitted", "b": "b-1", "s": 7}
    assert len(message_payload("a" * 64, {"type": "t", "batch_id": "b", "seq": 1})) < HCS_MESSAGE_LIMIT_BYTES
    assert ledger.published_hashes() == ["a" * 64]


def test_published_hashes_ignore_foreign_messages_without_matching():
    ledger, gateway = adapter()
    ledger.anchor("b" * 64, {"type": "report_issued", "batch_id": "b", "seq": 0})
    gateway.messages.append(b"not json")
    gateway.messages.append(json.dumps({"x": 1}).encode())
    assert ledger.published_hashes() == ["b" * 64, "", ""]


def test_mint_is_idempotent_through_the_memo_and_keeps_the_synthetic_marker():
    ledger, gateway = adapter()
    first = ledger.mint("k" * 64, "b-1", 250000, f"ClimAudit batch b-1 rep-1 {SYNTHETIC_MARKER}")
    again = ledger.mint("k" * 64, "b-1", 250000, f"ClimAudit batch b-1 rep-1 {SYNTHETIC_MARKER}")
    assert first == again and len(gateway.txs) == 1
    assert gateway.txs[0]["memo"].startswith(SYNTHETIC_MARKER) and len(gateway.txs[0]["memo"].encode()) <= MEMO_LIMIT_BYTES
    other = ledger.mint("z" * 64, "b-2", 10, f"x {SYNTHETIC_MARKER}")
    assert other.tx_id != first.tx_id and len(gateway.txs) == 2
    with pytest.raises(ApiError) as err:
        ledger.mint("q" * 64, "b-3", 0, "x")
    assert err.value.code == "LEDGER_REJECTED"


def test_transfer_is_custodial_and_retire_burns_once():
    ledger, gateway = adapter()
    assert ledger.transfer("t" * 64, TOKEN, "owner-1", "buyer-1", 5).startswith("custodial-")
    assert gateway.txs == []  # no token moved on-chain
    tx = ledger.retire("r" * 64, TOKEN, "buyer-1", 400, "ben-1", "voluntary_offset")
    assert ledger.retire("r" * 64, TOKEN, "buyer-1", 400, "ben-1", "voluntary_offset") == tx
    assert [t["kind"] for t in gateway.txs] == ["TOKENBURN"] and gateway.txs[0]["amount"] == 400


def test_gateway_outage_surfaces_as_ledger_unavailable():
    ledger, gateway = adapter()
    gateway.fail_message = True
    with pytest.raises(ApiError) as err:
        ledger.anchor("c" * 64, {"type": "t", "batch_id": "b", "seq": 0})
    assert err.value.code == "LEDGER_UNAVAILABLE"


def test_sdk_gateway_refuses_any_network_but_testnet():
    with pytest.raises(ApiError) as err:
        SdkGateway("0.0.1", "00", None, network="mainnet")
    assert err.value.params["reason"] == "only_testnet_is_allowed"


def test_factory_returns_incomplete_adapter_that_names_missing_variables():
    ledger = build_ledger(Settings(ledger_mode="direct", hedera_operator_id="0.0.1"), lambda: "t")
    assert isinstance(ledger, IncompleteDirectConfig)
    with pytest.raises(ApiError) as err:
        ledger.anchor("h", {})
    assert err.value.params["reason"] == "incomplete_configuration"
    assert set(err.value.params["missing_config"]) == {"hedera_operator_key", "hcs_topic_id", "hts_token_id"}


def test_full_lifecycle_runs_on_the_direct_adapter_and_the_audit_chain_matches_the_topic():
    gateway = FakeGateway()
    ledger = DirectHederaAdapter(gateway, TOPIC, TOKEN)
    store = Store(":memory:")
    clock_n = iter(range(10**6))
    app = create_app(Settings(api_keys=dict(KEYS)), ledger=ledger, store=store, clock=lambda: f"2026-10-16T{next(clock_n) // 3600 % 24:02d}:{next(clock_n) // 60 % 60:02d}:{next(clock_n) % 60:02d}Z")
    client = Client(TestClient(app, raise_server_exceptions=False))
    client.app = app
    _p, _f, batch, _r, credit = issued(client)
    cid, units = credit["credit_id"], credit["units"]
    client.ok("POST", f"/credits/{cid}/transfer", "owner", {"to_holder": "buyer-1", "units": 1000})
    client.ok("POST", f"/credits/{cid}/retire", "holder", {"units": 400, "beneficiary_ref": "ben-1", "reason_code": "voluntary_offset"})
    kinds = [t["kind"] for t in gateway.txs]
    assert kinds == ["TOKENMINT", "TOKENBURN"] and gateway.txs[0]["amount"] == units and gateway.txs[1]["amount"] == 400
    verdict = client.ok("GET", "/audit/verify", "verifier")
    assert verdict["chain_ok"] and verdict["ledger_matches"] and verdict["ledger_count"] == len(gateway.messages)
    assert all(m["tx_id"] for m in client.ok("GET", f"/audit/{batch['batch_id']}", "owner") for m in [m["ledger_ref"]])
    store.close()


def test_mirror_message_decoding_shape():
    # the mirror node returns messages base64-encoded; the helper in SdkGateway.list_messages decodes the same way
    payload = message_payload("d" * 64, {"type": "t", "batch_id": "b", "seq": 3})
    assert json.loads(base64.b64decode(base64.b64encode(payload)))["h"] == "d" * 64
