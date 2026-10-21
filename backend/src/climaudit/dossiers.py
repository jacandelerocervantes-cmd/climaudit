"""Synthetic dossier builder shared by tests and the fixture generator.

Every item is labeled `synthetic`. Relative uncertainties given on "laboratory" items are explicit demo values,
not measurements. Nothing here describes a real project.
"""
from __future__ import annotations

from copy import deepcopy
from typing import Any

from . import h3util
from .evidence import EvidenceItem
from .models import BatchRecord, Facility

# Structurally valid H3 resolution-9 cells for synthetic parcels (not real locations).
CELLS_A = [h3util.compose(9, 20, [0, 1, 2, 3, 4, 5, 6, 0, 1]), h3util.compose(9, 20, [0, 1, 2, 3, 4, 5, 6, 0, 2])]
CELLS_B = [h3util.compose(9, 20, [0, 1, 2, 3, 4, 5, 6, 0, 2]), h3util.compose(9, 20, [0, 1, 2, 3, 4, 5, 6, 0, 3])]  # overlaps A in one cell
CELLS_C = [h3util.compose(9, 44, [1, 1, 1, 1, 1, 1, 1, 1, 1])]  # disjoint from A and B

_counter = {"n": 0}


def item(kind: str, value: str, unit: str = "", group: str | None = None, rel_uncertainty: str | None = None, provenance: str = "synthetic", document_ref: str | None = None) -> EvidenceItem:
    _counter["n"] += 1
    return EvidenceItem(
        item_id=f"it-{_counter['n']}",
        kind=kind,
        value=value,
        unit=unit,
        group=group,
        provenance=provenance,
        rel_uncertainty=rel_uncertainty,
        document_ref=document_ref,
        source="owner",
        confirmation="confirmed",
    )


def high_tech_facility(**over: Any) -> Facility:
    data: dict[str, Any] = dict(
        facility_id="fac-1",
        project_id="prj-1",
        country="MX",
        process="pyrolysis",
        is_greenfield=True,
        pyrolysis_gas_combusted=True,
        heat_use_pct="80",
        pollution_controls=True,
        temperature_measured=True,
        declared_class="high",
    )
    data.update(over)
    return Facility(**data)


def low_tech_facility(**over: Any) -> Facility:
    data: dict[str, Any] = dict(
        facility_id="fac-2",
        project_id="prj-1",
        country="MX",
        process="pyrolysis",
        is_greenfield=True,
        pyrolysis_gas_combusted=False,
        heat_use_pct="0",
        pollution_controls=False,
        temperature_measured=False,
        kiln_type="flame_curtain",
        declared_class="low",
    )
    data.update(over)
    return Facility(**data)


def base_batch(**over: Any) -> BatchRecord:
    data: dict[str, Any] = dict(
        batch_id="b-001",
        project_id="prj-1",
        facility_id="fac-1",
        year=2026,
        biochar_type="agricultural_residue",
        application_type="soil",
        profile_id="VM0044@1.2",
        parcel_key="PARCEL-A",
        cell_set=list(CELLS_A),
        period_start="2026-03-01",
        period_end="2026-03-02",
        claimed_kg_co2e=300000,
        state="UNDER_REVIEW",
    )
    data.update(over)
    return BatchRecord(**data)


def base_evidence() -> list[EvidenceItem]:
    """Happy high-technology soil dossier: 100 t dry biochar, FC 0.80, 650 C (PR_de 0.89), no emissions."""
    return [
        item("dry_mass_biochar", "100", "t", rel_uncertainty="0.02", document_ref="lab-1"),
        item("organic_carbon_fraction", "80", "percent", rel_uncertainty="0.02", document_ref="lab-1"),
        item("h_corg_molar", "0.2", "ratio", document_ref="lab-1"),
        item("pyrolysis_temp_c", "650", "celsius"),
        item("feedstock_category", "agricultural_residue"),
        item("feedstock_origin_country", "MX"),
        item("feedstock_fate_evidence", "doc-fate-1"),
        item("production_date", "2026-02-01", group="lot-1"),
        item("application_date", "2026-03-01", group="lot-1"),
        item("transport_declaration", "legs_provided"),
        item("land_type", "cropland"),
        item("application_method", "subsurface"),
        item("lab_report", "lab-1"),
        item("lab_accredited", "true"),
        item("health_safety_program", "doc-hs-1"),
        item("transport_leg_kind", "biomass", group="leg-1"),
        item("transport_mode", "road", group="leg-1"),
        item("transport_distance_km_return", "150", "km", group="leg-1"),
        item("transport_freight_t", "120", "t", group="leg-1"),
        item("vehicle_class", "heavy", group="leg-1"),
        item("transport_leg_kind", "biochar", group="leg-2"),
        item("transport_mode", "road", group="leg-2"),
        item("transport_distance_km_return", "100", "km", group="leg-2"),
        item("transport_freight_t", "100", "t", group="leg-2"),
        item("vehicle_class", "heavy", group="leg-2"),
    ]


def base_facility_year() -> list[EvidenceItem]:
    return [
        item("facility_total_dry_mass", "100", "t"),
        item("pe_pretreat_electricity_tco2e", "0", "tco2e"),
        item("pe_pretreat_fuel_tco2e", "0", "tco2e"),
        item("pe_auxiliary_electricity_tco2e", "0", "tco2e"),
        item("pe_auxiliary_fuel_tco2e", "0", "tco2e"),
    ]


def replace_item(items: list[EvidenceItem], kind: str, value: str, unit: str | None = None, group: str | None = None, **extra: Any) -> list[EvidenceItem]:
    """Return a copy of items with the first matching kind (and group) replaced by a new value."""
    out = deepcopy(items)
    for index, existing in enumerate(out):
        if existing.kind == kind and (group is None or existing.group == group):
            data = existing.model_dump()
            data["value"] = value
            if unit is not None:
                data["unit"] = unit
            data.update(extra)
            out[index] = EvidenceItem(**data)
            return out
    raise KeyError(kind)


def without(items: list[EvidenceItem], kind: str, group: str | None = None) -> list[EvidenceItem]:
    return [i for i in items if not (i.kind == kind and (group is None or i.group == group))]


def normalized(items: list[EvidenceItem]) -> list[EvidenceItem]:
    """Validate against the closed kind list and convert units (percent to fraction) as the API does."""
    from .evidence import normalize_item

    return [normalize_item(i) for i in items]
