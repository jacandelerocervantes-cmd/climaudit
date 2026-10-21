"""Evidence items and the closed list of evidence kinds (BACKEND-SPEC.md section 5)."""
from __future__ import annotations

import re
from dataclasses import dataclass
from datetime import date
from decimal import Decimal, InvalidOperation
from typing import Any

from pydantic import BaseModel, ConfigDict, Field

from .errors import ApiError

PROVENANCES = ("measured", "modeled", "synthetic")
CONFIRMATIONS = ("pending_confirmation", "confirmed", "rejected")
_DATE_RE = re.compile(r"^\d{4}-\d{2}-\d{2}$")


@dataclass(frozen=True)
class KindSpec:
    value_type: str  # decimal | int | date | enum | bool | text | ref
    units: tuple[str, ...] = ()
    enum: tuple[str, ...] = ()
    multi: bool = False  # may appear several times, distinguished by `group`
    scope: str = "batch"  # batch | facility_year


def _k(value_type: str, units: tuple[str, ...] = (), enum: tuple[str, ...] = (), multi: bool = False, scope: str = "batch") -> KindSpec:
    return KindSpec(value_type, units, enum, multi, scope)


FEEDSTOCK_CATEGORIES = (
    "agricultural_residue",
    "food_processing_residue",
    "forestry_wood_residue",
    "recycling_economy",
    "aquaculture_waste",
    "animal_manure",
    "high_carbon_fly_ash",
    "purpose_grown",
    "other",
)
LAND_TYPES = ("cropland", "grassland", "urban_soil", "forest", "wetland", "other")

KINDS: dict[str, KindSpec] = {
    "dry_mass_biochar": _k("decimal", ("t",)),
    "wet_mass_biochar": _k("decimal", ("t",)),
    "moisture_pct": _k("decimal", ("percent",)),
    "moisture_basis": _k("enum", enum=("dry", "wet")),
    "organic_carbon_fraction": _k("decimal", ("fraction", "percent")),
    "h_corg_molar": _k("decimal", ("ratio",)),
    "pyrolysis_temp_c": _k("decimal", ("celsius",)),
    "soil_temp_c": _k("decimal", ("celsius",)),
    "log_series_value": _k("decimal", ("t",), multi=True),
    "feedstock_category": _k("enum", enum=FEEDSTOCK_CATEGORIES),
    "feedstock_class": _k(
        "enum",
        enum=("animal_manure", "wood", "herbaceous", "rice_husks_straw", "nut_shells", "biosolids_paper_sludge"),
    ),
    "feedstock_origin_country": _k("text"),
    "project_country": _k("text"),
    "feedstock_fate_evidence": _k("ref"),
    "production_date": _k("date", multi=True),
    "application_date": _k("date", multi=True),
    "transport_declaration": _k("enum", enum=("legs_provided", "none")),
    "application_type": _k("enum", enum=("soil", "non_soil")),
    "land_type": _k("enum", enum=LAND_TYPES),
    "application_method": _k("enum", enum=("surface_mixed", "subsurface")),
    "lab_report": _k("ref"),
    "lab_accredited": _k("bool"),
    "additive_pct": _k("decimal", ("percent",)),
    "additive_lab_ok": _k("bool"),
    "carbon_pct_dry": _k("decimal", ("percent",)),
    "product_lifetime_evidence": _k("ref"),
    "health_safety_program": _k("ref"),
    "process_type": _k("enum", enum=("pyrolysis", "gasification", "boiler", "torrefaction", "hydrothermal_carbonization")),
    "kiln_type": _k("text"),
    "ch4_factor_t_per_t": _k("decimal", ("t_ch4_per_t",)),
    "gwp_ch4": _k("decimal", ("ratio",)),
    "production_log_mass": _k("decimal", ("t",)),
    "freight_invoice_mass": _k("decimal", ("t",)),
    # facility-year level inputs (tCO2e or tool inputs)
    "facility_total_dry_mass": _k("decimal", ("t",), scope="facility_year"),
    "pe_pretreat_electricity_tco2e": _k("decimal", ("tco2e",), scope="facility_year"),
    "pe_pretreat_fuel_tco2e": _k("decimal", ("tco2e",), scope="facility_year"),
    "pe_auxiliary_electricity_tco2e": _k("decimal", ("tco2e",), scope="facility_year"),
    "pe_auxiliary_fuel_tco2e": _k("decimal", ("tco2e",), scope="facility_year"),
    "pe_processing_tco2e": _k("decimal", ("tco2e",)),
    # multi-instance groups
    "transport_mode": _k("enum", enum=("road", "rail", "ship", "other"), multi=True),
    "transport_leg_kind": _k("enum", enum=("biomass", "biochar"), multi=True),
    "transport_distance_km_return": _k("decimal", ("km",), multi=True),
    "transport_freight_t": _k("decimal", ("t",), multi=True),
    "vehicle_class": _k("enum", enum=("light", "heavy"), multi=True),
}


class EvidenceItem(BaseModel):
    model_config = ConfigDict(extra="forbid")

    item_id: str
    kind: str
    value: str
    unit: str = ""
    group: str | None = None
    measured_at: str | None = None
    source: str = "owner"  # owner | model | verifier
    provenance: str = "synthetic"
    rel_uncertainty: str | None = None
    document_ref: str | None = None
    confirmation: str = "confirmed"
    span: dict[str, Any] | None = Field(default=None, description="document span proposed by the extractor")


MAX_DECIMAL_EXPONENT = 30  # |adjusted exponent| above this is rejected (no 1E+999999 inputs)
MAX_TEXT_LENGTH = 512


def _parse_decimal(value: str, kind: str) -> Decimal:
    if len(value) > 64:
        raise ApiError("VALIDATION_FAILED", {"field": kind, "rule": "too_long"})
    try:
        d = Decimal(value)
    except (InvalidOperation, ValueError) as exc:
        raise ApiError("VALIDATION_FAILED", {"field": kind, "rule": "decimal"}) from exc
    if not d.is_finite():
        raise ApiError("VALIDATION_FAILED", {"field": kind, "rule": "finite"})
    if d != 0 and abs(d.adjusted()) > MAX_DECIMAL_EXPONENT:
        raise ApiError("VALIDATION_FAILED", {"field": kind, "rule": "magnitude"})
    return d


def normalize_item(item: EvidenceItem) -> EvidenceItem:
    """Validate against the closed kind list and normalize units (percent to fraction for FC)."""
    spec = KINDS.get(item.kind)
    if spec is None:
        raise ApiError("VALIDATION_FAILED", {"field": "kind", "rule": "closed_list", "value": item.kind})
    if item.provenance not in PROVENANCES:
        raise ApiError("VALIDATION_FAILED", {"field": "provenance", "rule": "enum"})
    if item.confirmation not in CONFIRMATIONS:
        raise ApiError("VALIDATION_FAILED", {"field": "confirmation", "rule": "enum"})
    if spec.units and item.unit not in spec.units:
        raise ApiError("UNIT_INVALID", {"field": item.kind, "unit": item.unit, "allowed": list(spec.units)})
    if spec.multi and not item.group:
        raise ApiError("VALIDATION_FAILED", {"field": item.kind, "rule": "group_required"})
    value = item.value
    unit = item.unit
    if spec.value_type == "decimal":
        d = _parse_decimal(value, item.kind)
        if item.kind == "organic_carbon_fraction" and unit == "percent":
            d, unit = d / Decimal(100), "fraction"
            value = format(d, "f")
        elif item.kind != "organic_carbon_fraction" and d < 0 and item.kind not in ("pyrolysis_temp_c",):
            raise ApiError("VALIDATION_FAILED", {"field": item.kind, "rule": "non_negative"})
    elif spec.value_type == "int":
        if not re.fullmatch(r"-?\d+", value):
            raise ApiError("VALIDATION_FAILED", {"field": item.kind, "rule": "int"})
    elif spec.value_type == "date":
        if not _DATE_RE.match(value):
            raise ApiError("DATE_AMBIGUOUS", {"field": item.kind, "value": value})
        try:
            date.fromisoformat(value)
        except ValueError as exc:
            raise ApiError("DATE_AMBIGUOUS", {"field": item.kind, "value": value}) from exc
    elif spec.value_type == "enum":
        if value not in spec.enum:
            raise ApiError("VALIDATION_FAILED", {"field": item.kind, "rule": "enum", "allowed": list(spec.enum)})
    elif spec.value_type == "bool":
        if value not in ("true", "false"):
            raise ApiError("VALIDATION_FAILED", {"field": item.kind, "rule": "bool"})
    elif spec.value_type in ("text", "ref"):
        if not value.strip():
            raise ApiError("VALIDATION_FAILED", {"field": item.kind, "rule": "non_empty"})
        if len(value) > MAX_TEXT_LENGTH:
            raise ApiError("VALIDATION_FAILED", {"field": item.kind, "rule": "too_long"})
    if item.rel_uncertainty is not None:
        u = _parse_decimal(item.rel_uncertainty, "rel_uncertainty")
        if u < 0 or u >= 1:
            raise ApiError("VALIDATION_FAILED", {"field": "rel_uncertainty", "rule": "range_0_1"})
    return item.model_copy(update={"value": value, "unit": unit})


class EvidenceView:
    """Read-only accessors over confirmed evidence items for one batch."""

    def __init__(self, items: list[EvidenceItem]):
        self.items = [i for i in items if i.confirmation == "confirmed"]
        self.pending = [i for i in items if i.confirmation == "pending_confirmation"]

    def all(self, kind: str) -> list[EvidenceItem]:
        return [i for i in self.items if i.kind == kind]

    def one(self, kind: str) -> EvidenceItem | None:
        found = self.all(kind)
        return found[0] if found else None

    def has(self, kind: str) -> bool:
        return self.one(kind) is not None

    def dec(self, kind: str) -> Decimal | None:
        item = self.one(kind)
        return Decimal(item.value) if item else None

    def text(self, kind: str) -> str | None:
        item = self.one(kind)
        return item.value if item else None

    def boolean(self, kind: str) -> bool | None:
        item = self.one(kind)
        return None if item is None else item.value == "true"

    def groups(self, *kinds: str) -> dict[str, dict[str, EvidenceItem]]:
        """Group multi-instance items by their `group` label: {group: {kind: item}}."""
        out: dict[str, dict[str, EvidenceItem]] = {}
        for item in self.items:
            if item.kind in kinds and item.group:
                out.setdefault(item.group, {})[item.kind] = item
        return out
