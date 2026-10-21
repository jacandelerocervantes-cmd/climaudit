"""Finding catalog with fixed severity and blocking semantics (BACKEND-SPEC.md section 8)."""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

SEVERITIES = ("critical", "high", "medium", "low", "info")


@dataclass(frozen=True)
class Rule:
    severity: str
    blocks_calculation: bool
    blocks_verified: bool
    overridable: bool


def _r(severity: str, calc: bool, verified: bool, override: bool) -> Rule:
    return Rule(severity, calc, verified, override)


CATALOG: dict[str, Rule] = {
    # critical
    "PERIOD_OVERLAP_DETECTED": _r("critical", True, True, False),
    "PARCEL_CELL_OVERLAP": _r("critical", True, True, False),
    "FACTOR_WITHOUT_SOURCE": _r("critical", True, True, False),
    "DOCUMENT_HASH_MISMATCH": _r("critical", True, True, False),
    "H_CORG_ABOVE_LIMIT": _r("critical", True, True, False),
    # high, block calculation and verification
    "VALUE_OUT_OF_RANGE": _r("high", True, True, False),
    "UNIT_MISMATCH": _r("high", True, True, False),
    "CALC_MISMATCH": _r("high", True, True, False),
    "EVIDENCE_MISSING": _r("high", True, True, False),
    "MOISTURE_NOT_DEDUCTED": _r("high", True, True, False),
    "MASS_BALANCE_MISMATCH": _r("high", True, True, False),
    # high, block verification only
    "FEEDSTOCK_NOT_ELIGIBLE": _r("high", False, True, False),
    "FEEDSTOCK_IMPORTED": _r("high", False, True, False),
    "FACILITY_CLASS_INCONSISTENT": _r("high", False, True, False),
    "APPLICATION_TOO_LATE": _r("high", False, True, False),
    "NON_SOIL_FROM_LOW_TECH": _r("high", False, True, False),
    "CARBON_FRACTION_BELOW_50_NON_SOIL": _r("high", False, True, False),
    "HIDDEN_TEXT_IN_DOCUMENT": _r("high", False, True, True),
    "INSTRUCTION_IN_DOCUMENT": _r("high", False, True, True),
    "NARRATIVE_UNGROUNDED_NUMBER": _r("high", False, True, False),
    # medium
    "DATE_INCONSISTENT": _r("medium", False, False, True),
    "EVIDENCE_DUPLICATED": _r("medium", False, False, True),
    "PROVENANCE_MIXED": _r("medium", False, False, True),
    "UNCERTAINTY_TOO_HIGH": _r("medium", False, False, True),
    "ADDITIVE_SHARE_ABOVE_LIMIT": _r("medium", False, False, True),
    "TRANSPORT_MODE_NOT_ALLOWED": _r("medium", False, False, True),
    "MOISTURE_BASIS_UNSPECIFIED": _r("medium", False, False, True),
    "METHODOLOGY_PARAMETER_UNVERIFIED": _r("medium", False, False, True),
    "METHODOLOGY_VERSION_OUTDATED": _r("medium", False, False, True),
    "TRANSPORT_DISTANCE_IMPLAUSIBLE": _r("medium", False, False, True),
    "LAND_COVER_MISMATCH": _r("medium", False, False, True),
    "REGISTRY_PROJECT_NOT_FOUND": _r("medium", False, False, True),
    "REGISTRY_METHODOLOGY_MISMATCH": _r("medium", False, False, True),
    "REGISTRY_VINTAGE_ALREADY_ISSUED": _r("medium", False, False, True),
    # low
    "WEATHER_UNSUITABLE_FOR_APPLICATION": _r("low", False, False, True),
    "BENFORD_ANOMALY": _r("low", False, False, True),
    "TRANSPORT_DISTANCE_AT_THRESHOLD": _r("low", False, False, True),
    "METHODOLOGY_TEXT_AMBIGUOUS": _r("low", False, False, True),
    # info
    "PROVENANCE_SYNTHETIC": _r("info", False, False, False),
    "REGISTRY_RECORD_FOUND": _r("info", False, False, False),
    "REGISTRY_MANUAL_CHECK": _r("info", False, False, False),
    "EXTERNAL_CHECK_UNAVAILABLE": _r("info", False, False, False),
}


@dataclass(frozen=True)
class Finding:
    code: str
    params: dict[str, Any] = field(default_factory=dict)
    source: str = "rule"  # rule | model

    @property
    def rule(self) -> Rule:
        return CATALOG[self.code]

    @property
    def severity(self) -> str:
        return self.rule.severity

    def as_dict(self) -> dict[str, Any]:
        rule = self.rule
        return {
            "code": self.code,
            "severity": rule.severity,
            "params": self.params,
            "source": self.source,
            "blocks_calculation": rule.blocks_calculation,
            "blocks_verified": rule.blocks_verified,
            "overridable": rule.overridable,
        }


def make(code: str, source: str = "rule", **params: Any) -> Finding:
    if code not in CATALOG:
        raise KeyError(f"unknown finding code {code!r}")
    return Finding(code=code, params={k: v for k, v in params.items() if v is not None}, source=source)


def blocks_calculation(findings: list[Finding]) -> bool:
    return any(f.rule.blocks_calculation for f in findings)


def blocks_verified(findings: list[Finding]) -> bool:
    return any(f.rule.blocks_verified for f in findings)
