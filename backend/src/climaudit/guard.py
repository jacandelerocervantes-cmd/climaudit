"""Anti-double-counting guard, two layers (SCHEMA.md section 6, BACKEND-SPEC.md sections 4 and 8).

Layer 1: batches with the same dedup_key must not have overlapping [start, end) periods.
Layer 2: batches whose H3 cell sets intersect must not have overlapping periods, even with different keys.
Only cell_set_hash, a coarse region and the period are public; the cell list stays in the permissioned record.
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import date

from .canonical import canonical_hash

# States that hold a period (BACKEND-SPEC.md section 8). DRAFT holds nothing; REJECTED releases.
HOLDING_STATES = frozenset(
    {"SUBMITTED", "UNDER_REVIEW", "NEEDS_INFO", "BLOCKED", "VERIFIED", "ISSUED", "PARTIALLY_RETIRED", "RETIRED"}
)


def dedup_key(parcel_key: str, methodology_id: str, activity: str = "biochar_application") -> str:
    return canonical_hash({"parcel_key": parcel_key, "activity": activity, "methodology_id": methodology_id})


def cell_set_hash(cells: list[str]) -> str:
    return canonical_hash({"cell_set": sorted(set(cells))})


def parcel_period_commitment(cells: list[str], methodology_id: str, start: str, end: str) -> str:
    """Public commitment (vector 3 of BACKEND-SPEC.md section 11); start and end are ISO timestamps."""
    return canonical_hash({"cell_set": sorted(set(cells)), "end": end, "methodology_id": methodology_id, "start": start})


@dataclass(frozen=True)
class Claim:
    batch_id: str
    state: str
    dedup_key: str
    cells: frozenset[str]
    start: date  # inclusive
    end: date  # exclusive


@dataclass(frozen=True)
class Conflict:
    batch_id: str
    reason: str  # "exact_key" | "cell_overlap"
    overlap: tuple[str, str]


def periods_overlap(a_start: date, a_end: date, b_start: date, b_end: date) -> bool:
    """[start, end) intervals; contiguous periods (end equals next start) do not overlap."""
    return a_start < b_end and b_start < a_end


def find_conflicts(candidate: Claim, existing: list[Claim]) -> list[Conflict]:
    conflicts: list[Conflict] = []
    for other in existing:
        if other.batch_id == candidate.batch_id or other.state not in HOLDING_STATES:
            continue
        if not periods_overlap(candidate.start, candidate.end, other.start, other.end):
            continue
        window = (max(candidate.start, other.start).isoformat(), min(candidate.end, other.end).isoformat())
        if other.dedup_key == candidate.dedup_key:
            conflicts.append(Conflict(other.batch_id, "exact_key", window))
        elif candidate.cells & other.cells:
            conflicts.append(Conflict(other.batch_id, "cell_overlap", window))
    return conflicts
