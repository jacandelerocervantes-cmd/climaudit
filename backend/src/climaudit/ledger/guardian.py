"""Guardian ledger adapter (verified live against Guardian 3.7.1 on 2026-10-17; see DECISIONS-LEDGER.md D-160 to D-165).

Audit anchoring goes through a Guardian policy built for this project (`backend/guardian/climaudit_audit.policy`):
ClimAudit submits a document to the policy's request form block and reads it back from the documents grid block.
Guardian signs the document as a verifiable credential and publishes it on a Hedera topic, so the consensus
timestamp, topic and message come from the policy itself, and the sequence number from the public mirror node.

    POST /api/v1/accounts/login          {username, password}  -> refreshToken
    POST /api/v1/accounts/access-token   {refreshToken}        -> accessToken
    POST /api/v1/policies/{id}/tag/{form}/blocks  {document}   -> submits the credential
    GET  /api/v1/policies/{id}/tag/{grid}/blocks               -> {data: [stored credentials]}

Credit tokens (mint, transfer, retire) are delegated to a token ledger (the direct Hedera adapter) because the audit
policy does not mint; without one those operations fail closed. Credentials come from environment variables only and
are never logged or placed in error parameters.
"""
from __future__ import annotations

import json
import time
import urllib.error
import urllib.request
from collections.abc import Callable
from dataclasses import dataclass
from typing import Any

from ..errors import ApiError
from .port import LedgerPort, LedgerRef, MintResult

Transport = Callable[[str, str, dict[str, str], bytes | None, float], tuple[int, bytes]]
from .hedera import MIRROR_TESTNET  # noqa: E402 (single source of the default mirror URL)


def urllib_transport(method: str, url: str, headers: dict[str, str], body: bytes | None, timeout: float) -> tuple[int, bytes]:
    if not url.startswith(("https://", "http://")):
        raise ApiError("LEDGER_UNAVAILABLE", {"adapter": "guardian", "reason": "bad_url"})
    request = urllib.request.Request(url, data=body, method=method, headers=headers)  # noqa: S310 (scheme checked above)
    try:
        with urllib.request.urlopen(request, timeout=timeout) as response:  # noqa: S310
            return response.status, response.read()
    except urllib.error.HTTPError as exc:
        return exc.code, exc.read()
    except (urllib.error.URLError, TimeoutError, OSError) as exc:
        raise ApiError("LEDGER_UNAVAILABLE", {"adapter": "guardian", "reason": "guardian_unreachable", "error": type(exc).__name__}) from exc


@dataclass(frozen=True)
class GuardianConfig:
    base_url: str
    username: str
    password: str
    policy_id: str
    form_tag: str = "form"
    grid_tag: str = "grid"
    mirror_url: str = MIRROR_TESTNET
    timeout: float = 30.0
    poll_attempts: int = 20
    poll_interval: float = 1.5


def _unavailable(reason: str, **extra: Any) -> ApiError:
    return ApiError("LEDGER_UNAVAILABLE", {"adapter": "guardian", "reason": reason, **extra})


class GuardianAdapter:
    mode = "guardian"

    def __init__(self, config: GuardianConfig, transport: Transport = urllib_transport, tokens: LedgerPort | None = None, sleep: Callable[[float], None] = time.sleep):
        self._c, self._send, self._tokens, self._sleep = config, transport, tokens, sleep
        self._refresh: str | None = None
        self._access: str | None = None

    # ------------------------------------------------------------------ http
    def _request(self, method: str, url: str, body: dict[str, Any] | None, token: str | None, missing_ok: bool = False) -> Any:
        headers = {"Accept": "application/json"}
        if body is not None:
            headers["Content-Type"] = "application/json"
        if token:
            headers["Authorization"] = f"Bearer {token}"
        data = json.dumps(body, separators=(",", ":")).encode("utf-8") if body is not None else None
        status, raw = self._send(method, url, headers, data, self._c.timeout)
        if status in (401, 403):
            raise _unavailable("guardian_auth_failed", status=status)
        if status >= 500 or status == 429:
            raise _unavailable("guardian_server_error", status=status)
        if status == 404 and missing_ok:
            return {}
        if status >= 400:
            raise ApiError("LEDGER_REJECTED", {"adapter": "guardian", "status": status})
        try:
            return json.loads(raw.decode("utf-8")) if raw else {}
        except (ValueError, UnicodeDecodeError) as exc:
            raise ApiError("LEDGER_REJECTED", {"adapter": "guardian", "reason": "response_not_json"}) from exc

    def _call(self, method: str, path: str, body: dict[str, Any] | None = None, token: str | None = None) -> Any:
        return self._request(method, self._c.base_url.rstrip("/") + path, body, token)

    def _login(self) -> None:
        data = self._call("POST", "/api/v1/accounts/login", {"username": self._c.username, "password": self._c.password})
        token = data.get("refreshToken") if isinstance(data, dict) else None
        if not isinstance(token, str) or not token:
            raise _unavailable("guardian_login_failed")
        self._refresh, self._access = token, None

    def _bearer(self) -> str:
        if self._access:
            return self._access
        if not self._refresh:
            self._login()
        data = self._call("POST", "/api/v1/accounts/access-token", {"refreshToken": self._refresh})
        token = data.get("accessToken") if isinstance(data, dict) else None
        if not isinstance(token, str) or not token:
            raise _unavailable("guardian_access_token_failed")
        self._access = token
        return token

    def _block(self, method: str, tag: str, body: dict[str, Any] | None = None) -> dict[str, Any]:
        path = f"/api/v1/policies/{self._c.policy_id}/tag/{tag}/blocks"
        try:
            data = self._call(method, path, body, self._bearer())
        except ApiError as exc:
            if exc.code != "LEDGER_UNAVAILABLE" or exc.params.get("reason") != "guardian_auth_failed":
                raise
            self._access = self._refresh = None  # expired or revoked: log in once more, then retry once
            data = self._call(method, path, body, self._bearer())
        if not isinstance(data, dict):
            raise ApiError("LEDGER_REJECTED", {"adapter": "guardian", "reason": "unexpected_response"})
        return data

    # ------------------------------------------------------------------ audit trail
    def _rows(self) -> list[dict[str, Any]]:
        """Stored credentials of the audit policy in consensus order, each reduced to the fields ClimAudit needs."""
        data = self._block("GET", self._c.grid_tag).get("data")
        if not isinstance(data, list):
            raise ApiError("LEDGER_REJECTED", {"adapter": "guardian", "reason": "unexpected_response", "missing_field": "data"})
        rows: list[dict[str, Any]] = []
        for item in data:
            try:
                subject = item["document"]["credentialSubject"][0]
                rows.append({"hash": str(subject["eventHash"]), "topic_id": str(item["topicId"]), "message_id": str(item["messageId"])})
            except (KeyError, IndexError, TypeError):
                rows.append({"hash": "", "topic_id": "", "message_id": str(item.get("messageId", "")) if isinstance(item, dict) else ""})
        rows.sort(key=lambda r: tuple(int(p) if p.isdigit() else 0 for p in r["message_id"].split(".")))
        return rows

    def _find(self, event_hash: str) -> dict[str, Any] | None:
        return next((r for r in self._rows() if r["hash"] == event_hash and r["message_id"]), None)

    def _consensus_details(self, topic_id: str, consensus_timestamp: str) -> tuple[int, str]:
        """Sequence number and transaction id of a topic message, from the public mirror node."""
        url = f"{self._c.mirror_url.rstrip('/')}/api/v1/topics/{topic_id}/messages?timestamp=eq:{consensus_timestamp}"
        for _ in range(self._c.poll_attempts):
            messages = self._request("GET", url, None, None, missing_ok=True).get("messages") or []
            if messages:
                msg = messages[0]
                tx = (msg.get("chunk_info") or {}).get("initial_transaction_id") or {}
                tx_id = f"{tx.get('account_id', '')}@{tx.get('transaction_valid_start', '')}" if tx else ""
                return int(msg["sequence_number"]), tx_id
            self._sleep(self._c.poll_interval)
        raise _unavailable("mirror_message_not_found", topic_id=topic_id)

    def anchor(self, event_hash: str, metadata: dict[str, Any]) -> LedgerRef:
        row = self._find(event_hash)  # idempotent: a retry after a timeout finds the credential already stored
        if row is None:
            document = {"eventHash": event_hash, "eventType": str(metadata.get("type", "")), "batchId": str(metadata.get("batch_id", "")), "seq": int(metadata.get("seq", 0))}
            self._block("POST", self._c.form_tag, {"document": document})
            for _ in range(self._c.poll_attempts):
                row = self._find(event_hash)
                if row is not None:
                    break
                self._sleep(self._c.poll_interval)
            if row is None:
                raise _unavailable("credential_not_visible_after_submit")
        sequence, tx_id = self._consensus_details(row["topic_id"], row["message_id"])
        return LedgerRef(row["topic_id"], sequence, row["message_id"], tx_id)

    def published_hashes(self) -> list[str]:
        return [r["hash"] for r in self._rows()]

    # ------------------------------------------------------------------ credit tokens (delegated)
    def _token_ledger(self) -> LedgerPort:
        if self._tokens is None:
            raise _unavailable("token_ledger_not_configured")
        return self._tokens

    def mint(self, op_key: str, batch_id: str, units: int, memo: str) -> MintResult:
        return self._token_ledger().mint(op_key, batch_id, units, memo)

    def transfer(self, op_key: str, token_id: str, from_holder: str, to_holder: str, units: int) -> str:
        return self._token_ledger().transfer(op_key, token_id, from_holder, to_holder, units)

    def retire(self, op_key: str, token_id: str, holder: str, units: int, beneficiary_ref: str, reason_code: str) -> str:
        return self._token_ledger().retire(op_key, token_id, holder, units, beneficiary_ref, reason_code)
