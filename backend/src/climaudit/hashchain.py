"""Audit event hash chain (BACKEND-SPEC.md section 11). Corrections are new events, never rewrites."""
from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from .canonical import GENESIS_HASH, canonical_hash

EVENT_TYPES = (
    "batch_submitted",
    "evidence_attached",
    "report_issued",
    "state_changed",
    "credit_issued",
    "credit_transferred",
    "credit_retired",
    "correction",
)
PROVENANCES = ("measured", "modeled", "synthetic")

_HASH_FIELDS = ("seq", "ts", "type", "batch_id", "payload_hash", "prev_hash", "provenance")


def event_hash(event: dict[str, Any]) -> str:
    """SHA-256 over the canonical form of the event without its own `hash` field."""
    return canonical_hash({k: event[k] for k in _HASH_FIELDS})


def make_event(
    seq: int, ts: str, type: str, batch_id: str, payload_hash: str, prev_hash: str, provenance: str
) -> dict[str, Any]:
    if type not in EVENT_TYPES:
        raise ValueError(f"unknown event type {type!r}")
    if provenance not in PROVENANCES:
        raise ValueError(f"unknown provenance {provenance!r}")
    event: dict[str, Any] = {
        "seq": seq,
        "ts": ts,
        "type": type,
        "batch_id": batch_id,
        "payload_hash": payload_hash,
        "prev_hash": prev_hash,
        "provenance": provenance,
    }
    event["hash"] = event_hash(event)
    return event


@dataclass(frozen=True)
class ChainResult:
    ok: bool
    first_broken_seq: int | None = None
    reason: str | None = None


def verify_chain(events: list[dict[str, Any]]) -> ChainResult:
    """Walk the chain and return the first broken `seq` (independent verifier logic)."""
    prev = GENESIS_HASH
    for index, event in enumerate(events):
        if event.get("seq") != index:
            return ChainResult(False, index, "seq_gap_or_reorder")
        if event.get("prev_hash") != prev:
            return ChainResult(False, index, "prev_hash_mismatch")
        if event.get("hash") != event_hash(event):
            return ChainResult(False, index, "hash_mismatch")
        prev = event["hash"]
    return ChainResult(True)
