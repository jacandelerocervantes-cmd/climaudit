"""Guardian adapter tests against a scripted Guardian and mirror node (no network).

The same flow was verified live against Guardian 3.7.1 on 2026-10-17 (DECISIONS-LEDGER.md D-160 to D-165).
"""
from __future__ import annotations

import json

import pytest

from climaudit.config import Settings
from climaudit.errors import ApiError
from climaudit.ledger.adapters import build_ledger
from climaudit.ledger.guardian import GuardianAdapter, GuardianConfig
from climaudit.ledger.port import MintResult

CFG = GuardianConfig("http://guardian.test", "sr", "secret-pw", "pol1", mirror_url="http://mirror.test", poll_attempts=3, poll_interval=0)
TOPIC = "0.0.700"


class Server:
    """A scripted Guardian (login, form block, grid block) plus mirror node."""

    def __init__(self):
        self.calls: list[tuple[str, str, dict, dict | None]] = []
        self.rows: list[dict] = []
        self.logins = 0
        self.expire_access_once = False
        self.status = 200
        self.hide_after_submit = False
        self.mirror_ready = True

    def __call__(self, method, url, headers, body, timeout):
        payload = json.loads(body) if body else None
        host, _, path = url.partition(".test")
        path = path
        self.calls.append((method, path, headers, payload))
        if host.endswith("mirror"):
            ts = path.split("eq:")[1]
            if not self.mirror_ready:
                return 200, b'{"messages":[]}'
            n = [r["messageId"] for r in self.rows].index(ts) + 1
            msg = {"sequence_number": n, "chunk_info": {"initial_transaction_id": {"account_id": "0.0.9", "transaction_valid_start": "1.2"}}}
            return 200, json.dumps({"messages": [msg]}).encode()
        if path == "/api/v1/accounts/login":
            self.logins += 1
            return 200, b'{"refreshToken":"R1"}'
        if path == "/api/v1/accounts/access-token":
            return 200, b'{"accessToken":"A1"}'
        if self.expire_access_once:
            self.expire_access_once = False
            return 401, b"{}"
        if self.status != 200:
            return self.status, b"{}"
        if path.endswith("/tag/form/blocks") and method == "POST":
            if not self.hide_after_submit:
                doc = payload["document"]
                self.rows.append({"topicId": TOPIC, "messageId": f"17.{len(self.rows) + 1:09d}", "document": {"credentialSubject": [doc]}})
            return 200, b"{}"
        if path.endswith("/tag/grid/blocks"):
            return 200, json.dumps({"data": list(reversed(self.rows))}).encode()  # newest first, like a real grid
        raise AssertionError(path)


def adapter(server, tokens=None):
    return GuardianAdapter(CFG, server, tokens=tokens, sleep=lambda s: None)


class TokenStub:
    mode = "stub"

    def mint(self, op_key, batch_id, units, memo):
        return MintResult("0.0.8", "tx-m", units)

    def transfer(self, op_key, token_id, from_holder, to_holder, units):
        return "custodial"

    def retire(self, op_key, token_id, holder, units, beneficiary_ref, reason_code):
        return "tx-b"

    def anchor(self, event_hash, metadata):
        raise AssertionError

    def published_hashes(self):
        raise AssertionError


def test_anchor_submits_to_the_form_and_reads_back_ids_from_guardian_and_the_mirror():
    server = Server()
    ref = adapter(server).anchor("a" * 64, {"type": "batch_submitted", "batch_id": "b-1", "seq": 3})
    assert (ref.topic_id, ref.sequence, ref.consensus_timestamp, ref.tx_id) == (TOPIC, 1, "17.000000001", "0.0.9@1.2")
    post = next(c for c in server.calls if c[0] == "POST" and c[1].endswith("/tag/form/blocks"))
    assert post[1] == "/api/v1/policies/pol1/tag/form/blocks" and post[2]["Authorization"] == "Bearer A1"
    assert post[3] == {"document": {"eventHash": "a" * 64, "eventType": "batch_submitted", "batchId": "b-1", "seq": 3}}


def test_anchor_is_idempotent_and_published_hashes_follow_consensus_order():
    server = Server()
    g = adapter(server)
    first = g.anchor("a" * 64, {"type": "t", "batch_id": "b", "seq": 0})
    g.anchor("b" * 64, {"type": "t", "batch_id": "b", "seq": 1})
    assert g.anchor("a" * 64, {"type": "t", "batch_id": "b", "seq": 0}) == first
    assert len(server.rows) == 2  # the retry did not submit a second credential
    assert g.published_hashes() == ["a" * 64, "b" * 64]
    assert server.logins == 1


def test_expired_token_triggers_one_relogin_and_retry():
    server = Server()
    g = adapter(server)
    g.published_hashes()
    server.expire_access_once = True
    assert g.published_hashes() == []
    assert server.logins == 2


def test_credential_that_never_appears_or_a_mirror_that_lags_fails_closed():
    server = Server()
    server.hide_after_submit = True
    with pytest.raises(ApiError) as err:
        adapter(server).anchor("c" * 64, {"type": "t", "batch_id": "b", "seq": 0})
    assert err.value.code == "LEDGER_UNAVAILABLE" and err.value.params["reason"] == "credential_not_visible_after_submit"
    server = Server()
    server.mirror_ready = False
    with pytest.raises(ApiError) as err2:
        adapter(server).anchor("d" * 64, {"type": "t", "batch_id": "b", "seq": 0})
    assert err2.value.params["reason"] == "mirror_message_not_found"
    server.mirror_ready = True  # the retry finds the stored credential and only completes the mirror lookup
    assert adapter(server).anchor("d" * 64, {"type": "t", "batch_id": "b", "seq": 0}).sequence == 1
    assert len(server.rows) == 1


def test_status_codes_map_to_unavailable_or_rejected_and_never_leak_credentials():
    server = Server()
    g = adapter(server)
    server.status = 503
    with pytest.raises(ApiError) as err:
        g.published_hashes()
    assert err.value.code == "LEDGER_UNAVAILABLE"
    server.status = 422
    with pytest.raises(ApiError) as err2:
        g.published_hashes()
    assert err2.value.code == "LEDGER_REJECTED"
    assert "secret-pw" not in json.dumps(err.value.params) + json.dumps(err2.value.params)


def test_login_failure_fails_closed():
    def deny(method, url, headers, body, timeout):
        return 401, b"{}"

    with pytest.raises(ApiError) as err:
        GuardianAdapter(CFG, deny).published_hashes()
    assert err.value.code == "LEDGER_UNAVAILABLE" and err.value.params["reason"] == "guardian_auth_failed"


def test_token_operations_delegate_or_fail_closed():
    g = adapter(Server(), tokens=TokenStub())
    assert g.mint("k", "b", 5, "m").units == 5 and g.retire("k", "t", "h", 1, "b", "r") == "tx-b"
    with pytest.raises(ApiError) as err:
        adapter(Server()).mint("k", "b", 5, "m")
    assert err.value.params["reason"] == "token_ledger_not_configured"


def test_factory_builds_guardian_adapter_when_configured():
    s = Settings(ledger_mode="guardian", guardian_url="http://g", guardian_username="u", guardian_password="p", guardian_policy_id="1")
    ledger = build_ledger(s, lambda: "t")
    assert isinstance(ledger, GuardianAdapter)
    with pytest.raises(ApiError):
        ledger.mint("k", "b", 1, "m")  # no Hedera token configuration, so token operations fail closed
