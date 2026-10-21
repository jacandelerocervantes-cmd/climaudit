"""Closed state machine (BACKEND-SPEC.md section 10) and role permissions (section 2)."""
from __future__ import annotations

from .errors import ApiError

TERMINAL = frozenset({"REJECTED", "RETIRED"})

# (from, to) -> roles allowed to request the transition
TRANSITIONS: dict[tuple[str, str], frozenset[str]] = {
    ("DRAFT", "SUBMITTED"): frozenset({"owner", "admin"}),
    ("SUBMITTED", "UNDER_REVIEW"): frozenset({"system", "admin"}),
    ("UNDER_REVIEW", "NEEDS_INFO"): frozenset({"verifier", "admin"}),
    ("NEEDS_INFO", "SUBMITTED"): frozenset({"owner", "admin"}),
    ("UNDER_REVIEW", "REJECTED"): frozenset({"verifier", "admin"}),
    ("UNDER_REVIEW", "BLOCKED"): frozenset({"system", "admin"}),
    ("BLOCKED", "UNDER_REVIEW"): frozenset({"system", "admin"}),
    ("UNDER_REVIEW", "VERIFIED"): frozenset({"verifier"}),
    ("VERIFIED", "NEEDS_INFO"): frozenset({"verifier", "admin"}),
    ("VERIFIED", "REJECTED"): frozenset({"verifier", "admin"}),
    ("VERIFIED", "ISSUED"): frozenset({"registry"}),
    ("ISSUED", "PARTIALLY_RETIRED"): frozenset({"holder", "owner"}),
    ("ISSUED", "RETIRED"): frozenset({"holder", "owner"}),
    ("PARTIALLY_RETIRED", "RETIRED"): frozenset({"holder", "owner"}),
}

REASON_REQUIRED = frozenset({("UNDER_REVIEW", "NEEDS_INFO"), ("UNDER_REVIEW", "REJECTED"), ("VERIFIED", "NEEDS_INFO"), ("VERIFIED", "REJECTED")})
EDITABLE_STATES = frozenset({"DRAFT", "NEEDS_INFO"})

# Route-level permission matrix (section 2): action -> roles
PERMISSIONS: dict[str, frozenset[str]] = {
    "project.create": frozenset({"owner", "admin"}),
    "facility.create": frozenset({"owner", "admin"}),
    "batch.create": frozenset({"owner", "admin"}),
    "batch.edit": frozenset({"owner", "admin"}),
    "document.upload": frozenset({"owner", "verifier", "admin"}),
    "evidence.add": frozenset({"owner", "extractor", "admin"}),
    "evidence.confirm": frozenset({"owner", "verifier", "admin"}),
    "verification.run": frozenset({"verifier", "system", "admin"}),
    "credit.transfer": frozenset({"holder", "owner"}),
    "credit.retire": frozenset({"holder", "owner"}),
    "read.any": frozenset({"verifier", "registry", "admin", "system"}),
}


def check_permission(action: str, role: str) -> None:
    if role not in PERMISSIONS.get(action, frozenset()):
        raise ApiError("ROLE_NOT_AUTHORIZED", {"required_role": sorted(PERMISSIONS.get(action, frozenset())), "action": action})


def check_transition(current: str, target: str, role: str, reason: str | None) -> None:
    allowed = TRANSITIONS.get((current, target))
    if allowed is None:
        raise ApiError("STATE_TRANSITION_NOT_ALLOWED", {"from": current, "to": target})
    if role not in allowed:
        raise ApiError("ROLE_NOT_AUTHORIZED", {"required_role": sorted(allowed), "action": f"{current}->{target}"})
    if (current, target) in REASON_REQUIRED and not (reason and reason.strip()):
        raise ApiError("VALIDATION_FAILED", {"field": "reason", "rule": "required_for_transition"})
