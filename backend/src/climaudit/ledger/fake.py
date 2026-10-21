"""In-memory ledger used for tests and local demos. It records what a real adapter would publish.

It is NOT Hedera and says so: every id starts with "fake-". It enforces the synthetic-data marker on mint memos so
a demo token can never be mistaken for a real credit.
"""
from __future__ import annotations

from collections.abc import Callable
from typing import Any

from ..errors import ApiError
from .port import SYNTHETIC_MARKER, LedgerRef, MintResult


class FakeLedger:
    mode = "fake"

    def __init__(self, clock: Callable[[], str], require_marker: bool = True):
        self._clock = clock
        self._require_marker = require_marker
        self.topic_id = "fake-topic-0"
        self.token_id = "fake-token-0"
        self.messages: list[dict[str, Any]] = []
        self.mints: list[dict[str, Any]] = []
        self.transfers: list[dict[str, Any]] = []
        self.retirements: list[dict[str, Any]] = []
        self._seen_ops: dict[str, Any] = {}
        self._fail_next: list[tuple[str, str]] = []
        self._tx = 0

    # ------------------------------------------------------------- test hooks
    def fail_next(self, kind: str = "unavailable", on: str = "any") -> None:
        """Make the next matching call fail. `on` is "any", "anchor", "mint", "transfer" or "retire"."""
        self._fail_next.append((kind, on))

    def _maybe_fail(self, op: str = "any") -> None:
        if self._fail_next and self._fail_next[0][1] in ("any", op):
            kind, _ = self._fail_next.pop(0)
            if kind == "rejected":
                raise ApiError("LEDGER_REJECTED", {"status": "FAKE_REJECTED"})
            raise ApiError("LEDGER_UNAVAILABLE", {"retry_after": 1})

    def _next_tx(self) -> str:
        self._tx += 1
        return f"fake-tx-{self._tx}"

    # ------------------------------------------------------------------ port
    def anchor(self, event_hash: str, metadata: dict[str, Any]) -> LedgerRef:
        self._maybe_fail("anchor")
        ref = LedgerRef(self.topic_id, len(self.messages) + 1, self._clock())
        self.messages.append({"hash": event_hash, "metadata": dict(metadata), "ref": ref.as_dict()})
        return ref

    def mint(self, op_key: str, batch_id: str, units: int, memo: str) -> MintResult:
        if op_key in self._seen_ops:
            return self._seen_ops[op_key]
        self._maybe_fail("mint")
        if self._require_marker and SYNTHETIC_MARKER not in memo:
            raise ApiError("LEDGER_REJECTED", {"status": "MISSING_SYNTHETIC_MARKER"})
        if units <= 0:
            raise ApiError("LEDGER_REJECTED", {"status": "NON_POSITIVE_UNITS"})
        result = MintResult(self.token_id, self._next_tx(), units)
        self.mints.append({"batch_id": batch_id, "units": units, "memo": memo, "op_key": op_key})
        self._seen_ops[op_key] = result
        return result

    def transfer(self, op_key: str, token_id: str, from_holder: str, to_holder: str, units: int) -> str:
        if op_key in self._seen_ops:
            return self._seen_ops[op_key]
        self._maybe_fail("transfer")
        tx = self._next_tx()
        self.transfers.append({"token_id": token_id, "from": from_holder, "to": to_holder, "units": units, "op_key": op_key})
        self._seen_ops[op_key] = tx
        return tx

    def retire(self, op_key: str, token_id: str, holder: str, units: int, beneficiary_ref: str, reason_code: str) -> str:
        if op_key in self._seen_ops:
            return self._seen_ops[op_key]
        self._maybe_fail("retire")
        tx = self._next_tx()
        self.retirements.append({"token_id": token_id, "holder": holder, "units": units, "beneficiary_ref": beneficiary_ref, "reason_code": reason_code, "op_key": op_key})
        self._seen_ops[op_key] = tx
        return tx

    def published_hashes(self) -> list[str]:
        return [m["hash"] for m in self.messages]
