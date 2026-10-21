"""Ledger port (BACKEND-SPEC.md section 1). The API and the extraction agent never hold ledger keys; only the
adapter chosen by CP_LEDGER_MODE does, and it is invoked only on transitions requested by an authorized role.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Protocol

SYNTHETIC_MARKER = "SYNTHETIC_DEMO_DATA"


@dataclass(frozen=True)
class LedgerRef:
    topic_id: str
    sequence: int
    consensus_timestamp: str  # empty when the consensus timestamp is not yet known (read it from the mirror node)
    tx_id: str = ""

    def as_dict(self) -> dict[str, Any]:
        out: dict[str, Any] = {"topic_id": self.topic_id, "sequence": self.sequence, "consensus_timestamp": self.consensus_timestamp}
        if self.tx_id:
            out["tx_id"] = self.tx_id
        return out


@dataclass(frozen=True)
class MintResult:
    token_id: str
    tx_id: str
    units: int

    def as_dict(self) -> dict[str, Any]:
        return {"token_id": self.token_id, "tx_id": self.tx_id, "units": self.units}


class LedgerPort(Protocol):
    mode: str

    def anchor(self, event_hash: str, metadata: dict[str, Any]) -> LedgerRef:
        """Publish an audit hash (HCS message). Only the hash and minimal metadata are published."""

    def mint(self, op_key: str, batch_id: str, units: int, memo: str) -> MintResult:
        """Create credit units (HTS mint). One unit = 1 kg CO2e."""

    def transfer(self, op_key: str, token_id: str, from_holder: str, to_holder: str, units: int) -> str:
        """Move units between holders; returns a transaction id."""

    def retire(self, op_key: str, token_id: str, holder: str, units: int, beneficiary_ref: str, reason_code: str) -> str:
        """Retire units for a beneficiary reference; returns a transaction id."""

    def published_hashes(self) -> list[str]:
        """Event hashes read back from the ledger (mirror node), in order, for the independent verifier."""
