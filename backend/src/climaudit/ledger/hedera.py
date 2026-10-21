"""Direct Hedera testnet adapter (fallback mode of BACKEND-SPEC.md Decision 1).

Layout
- `HederaGateway` is the small surface the adapter needs from Hedera. `SdkGateway` implements it with the Hiero
  Python SDK (`hiero-sdk-python`, optional extra `hedera`) for writes and the public mirror node REST API for reads.
  Tests use an in-memory gateway, so nothing here needs credentials to be tested.
- `DirectHederaAdapter` maps the ledger port to Hedera:
    anchor  -> HCS message (a compact JSON with the event hash, never evidence or personal data)
    mint    -> HTS token mint into the treasury account
    retire  -> HTS token burn from the treasury (retirement removes units from supply)
    transfer-> custodial: balances between application holders are bookkeeping in the database, anchored in the
               audit trail; no token moves on-chain (holders do not have Hedera accounts in this prototype)
Testnet only: any other network is refused. Credentials come from environment variables, never from code.
"""
from __future__ import annotations

import base64
import json
import urllib.error
import urllib.parse
import urllib.request
from dataclasses import dataclass
from typing import Any, Protocol

from ..canonical import canonical_bytes
from ..errors import ApiError
from .port import SYNTHETIC_MARKER, LedgerRef, MintResult

MIRROR_TESTNET = "https://testnet.mirrornode.hedera.com"
MEMO_LIMIT_BYTES = 100  # Hedera transaction memo limit
HCS_MESSAGE_LIMIT_BYTES = 1024  # single-message limit; our payload is far below it


@dataclass(frozen=True)
class FoundTx:
    tx_id: str
    amount: int


class HederaGateway(Protocol):
    def submit_message(self, topic_id: str, payload: bytes) -> tuple[int, str]:
        """Publish an HCS message; return (sequence number, transaction id)."""

    def mint(self, token_id: str, amount: int, memo: str) -> str:
        """Mint fungible units into the treasury; return the transaction id."""

    def burn(self, token_id: str, amount: int, memo: str) -> str:
        """Burn units from the treasury; return the transaction id."""

    def find_by_memo(self, kind: str, memo_prefix: str) -> FoundTx | None:
        """Find a successful recent transaction of `kind` ("TOKENMINT" or "TOKENBURN") whose memo starts with the prefix."""

    def list_messages(self, topic_id: str) -> list[bytes]:
        """All message payloads of a topic in consensus order."""


def _memo(op_key: str, caller_memo: str) -> str:
    """Compact transaction memo: the synthetic-data marker (when present) plus a prefix of the operation key."""
    marker = f"{SYNTHETIC_MARKER} " if SYNTHETIC_MARKER in caller_memo else ""
    return f"{marker}{op_key[:16]}"[:MEMO_LIMIT_BYTES]


def message_payload(event_hash: str, metadata: dict[str, Any]) -> bytes:
    payload = {"v": 1, "h": event_hash, "t": str(metadata.get("type", "")), "b": str(metadata.get("batch_id", "")), "s": int(metadata.get("seq", 0))}
    data = canonical_bytes(payload)
    if len(data) > HCS_MESSAGE_LIMIT_BYTES:
        raise ApiError("LEDGER_REJECTED", {"status": "MESSAGE_TOO_LARGE"})
    return data


class DirectHederaAdapter:
    mode = "direct"

    def __init__(self, gateway: HederaGateway, topic_id: str, token_id: str):
        self._gateway, self._topic, self._token = gateway, topic_id, token_id

    def anchor(self, event_hash: str, metadata: dict[str, Any]) -> LedgerRef:
        sequence, tx_id = self._gateway.submit_message(self._topic, message_payload(event_hash, metadata))
        return LedgerRef(self._topic, sequence, "", tx_id)

    def mint(self, op_key: str, batch_id: str, units: int, memo: str) -> MintResult:
        if units <= 0:
            raise ApiError("LEDGER_REJECTED", {"status": "NON_POSITIVE_UNITS"})
        compact = _memo(op_key, memo)
        existing = self._gateway.find_by_memo("TOKENMINT", compact)  # a mint with this operation key may already exist
        if existing is not None:
            return MintResult(self._token, existing.tx_id, existing.amount)
        return MintResult(self._token, self._gateway.mint(self._token, units, compact), units)

    def transfer(self, op_key: str, token_id: str, from_holder: str, to_holder: str, units: int) -> str:
        # Custodial bookkeeping: the units stay in the treasury account on-chain; the transfer is recorded in the audit trail.
        return f"custodial-{op_key[:16]}"

    def retire(self, op_key: str, token_id: str, holder: str, units: int, beneficiary_ref: str, reason_code: str) -> str:
        compact = _memo(op_key, SYNTHETIC_MARKER)
        existing = self._gateway.find_by_memo("TOKENBURN", compact)
        if existing is not None:
            return existing.tx_id
        return self._gateway.burn(self._token, units, compact)

    def published_hashes(self) -> list[str]:
        hashes: list[str] = []
        for raw in self._gateway.list_messages(self._topic):
            try:
                hashes.append(str(json.loads(raw.decode("utf-8"))["h"]))
            except (ValueError, KeyError, UnicodeDecodeError):
                hashes.append("")  # a foreign or malformed message never matches the local chain
        return hashes


# ----------------------------------------------------------------------------- real gateway


def _mirror_get(base: str, path: str, params: dict[str, str] | None = None, timeout: float = 10.0) -> dict[str, Any]:
    url = base.rstrip("/") + path + ("?" + urllib.parse.urlencode(params) if params else "")
    if not url.startswith(("https://", "http://")):
        raise ApiError("LEDGER_UNAVAILABLE", {"reason": "bad_mirror_url"})
    try:
        with urllib.request.urlopen(url, timeout=timeout) as response:  # noqa: S310 (scheme checked above)
            return json.loads(response.read().decode("utf-8"))
    except (urllib.error.URLError, TimeoutError, ValueError) as exc:
        raise ApiError("LEDGER_UNAVAILABLE", {"reason": "mirror_node_unreachable", "error": type(exc).__name__}) from exc


class SdkGateway:
    """Hiero Python SDK for writes, mirror node REST for reads. Needs the optional `hedera` extra and credentials."""

    def __init__(self, operator_id: str, operator_key: str, supply_key: str | None = None, network: str = "testnet", mirror_url: str | None = None):
        if network != "testnet":
            raise ApiError("LEDGER_UNAVAILABLE", {"reason": "only_testnet_is_allowed", "network": network})
        try:
            import hiero_sdk_python as hiero  # noqa: PLC0415 (optional dependency)
        except ImportError as exc:
            raise ApiError("LEDGER_UNAVAILABLE", {"reason": "hiero_sdk_python_not_installed"}) from exc
        self._h = hiero
        self._operator_id = hiero.AccountId.from_string(operator_id)
        self._operator_key = self._parse_key(operator_key)
        self._supply_key = self._parse_key(supply_key) if supply_key else self._operator_key
        self._mirror = (mirror_url or MIRROR_TESTNET).rstrip("/")
        self._client = hiero.Client.for_testnet()
        self._client.set_operator(self._operator_id, self._operator_key)

    def _parse_key(self, text: str) -> Any:
        try:
            return self._h.PrivateKey.from_string_der(text)
        except Exception:  # noqa: BLE001 - fall back to raw hex / other encodings
            return self._h.PrivateKey.from_string(text)

    def _run(self, transaction: Any, *keys: Any) -> Any:
        try:
            frozen = transaction.freeze_with(self._client)
            for key in keys:
                frozen = frozen.sign(key)
            return frozen.execute(self._client, validate_status=True)
        except (self._h.ReceiptStatusError, self._h.PrecheckError) as exc:
            raise ApiError("LEDGER_REJECTED", {"status": type(exc).__name__}) from exc
        except ApiError:
            raise
        except Exception as exc:  # noqa: BLE001 - network and SDK failures are an outage, not a verdict
            raise ApiError("LEDGER_UNAVAILABLE", {"reason": "sdk_error", "error": type(exc).__name__}) from exc

    def submit_message(self, topic_id: str, payload: bytes) -> tuple[int, str]:
        receipt = self._run(
            self._h.TopicMessageSubmitTransaction().set_topic_id(self._h.TopicId.from_string(topic_id)).set_message(payload),
            self._operator_key,
        )
        return int(receipt.topic_sequence_number), str(receipt.transaction_id)

    def mint(self, token_id: str, amount: int, memo: str) -> str:
        receipt = self._run(
            self._h.TokenMintTransaction().set_token_id(self._h.TokenId.from_string(token_id)).set_amount(amount).set_transaction_memo(memo),
            self._operator_key,
            self._supply_key,
        )
        return str(receipt.transaction_id)

    def burn(self, token_id: str, amount: int, memo: str) -> str:
        receipt = self._run(
            self._h.TokenBurnTransaction().set_token_id(self._h.TokenId.from_string(token_id)).set_amount(amount).set_transaction_memo(memo),
            self._operator_key,
            self._supply_key,
        )
        return str(receipt.transaction_id)

    def find_by_memo(self, kind: str, memo_prefix: str) -> FoundTx | None:
        data = _mirror_get(self._mirror, "/api/v1/transactions", {"account.id": str(self._operator_id), "transactiontype": kind, "limit": "100", "order": "desc"})
        for tx in data.get("transactions", []):
            if tx.get("result") != "SUCCESS":
                continue
            memo = base64.b64decode(tx.get("memo_base64") or "").decode("utf-8", "replace")
            if memo.startswith(memo_prefix):
                amount = sum(abs(t["amount"]) for t in tx.get("token_transfers", []) if t.get("account") == str(self._operator_id))
                return FoundTx(str(tx["transaction_id"]), int(amount))
        return None

    def list_messages(self, topic_id: str) -> list[bytes]:
        messages: list[bytes] = []
        path = f"/api/v1/topics/{topic_id}/messages"
        params: dict[str, str] | None = {"limit": "100", "order": "asc"}
        while path:
            data = _mirror_get(self._mirror, path, params)
            messages.extend(base64.b64decode(m["message"]) for m in data.get("messages", []))
            nxt = (data.get("links") or {}).get("next")
            path, params = (nxt, None) if nxt else ("", None)
        return messages
