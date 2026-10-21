"""CDM TOOL05 v03.0: emissions from electricity consumption (research/sources/cdm-tool05).

Eq. 1-3: PE_EC,y = sum_j EC_j,y * EF_EL,j,y * (1 + TDL_j,y)   (project, baseline and leakage forms)
Scenario A, Option A2 conservative defaults (1.3 / 0.4 / 0.25 tCO2/MWh) and TDL defaults (20% / 3%) come
from the methodology profile. Option A1 (combined margin from TOOL07) is an explicit input.
Option B4 (Eq. 7-8): 11,400 * rated capacity (MW) tCO2/yr for captive plants.
"""
from __future__ import annotations

from decimal import Decimal

from ..profiles import ParamRef, Profile


def electricity_emissions(consumption_mwh: Decimal, ef_t_per_mwh: Decimal, tdl_fraction: Decimal) -> Decimal:
    """Eq. 1 for one source."""
    return consumption_mwh * ef_t_per_mwh * (Decimal(1) + tdl_fraction)


def default_grid_ef(
    profile: Profile,
    source: str,
    project_leakage_mwh: Decimal,
    baseline_mwh: Decimal = Decimal(0),
    hydro_below_50pct: bool = True,
) -> tuple[Decimal, ParamRef]:
    """Option A2 default for Scenario A.

    source is "project", "leakage" or "baseline". The 1.3 value applies to project/leakage sources when
    baseline sources are absent or smaller; the 0.4 / 0.25 values apply to baseline sources, or to project and
    leakage sources when baseline consumption is larger.
    """
    if source not in ("project", "leakage", "baseline"):
        raise ValueError(f"unknown source {source!r}")
    baseline_larger = baseline_mwh > project_leakage_mwh
    use_conservative_high = source in ("project", "leakage") and not baseline_larger
    if use_conservative_high:
        return profile.tool_value("TOOL05", "default_ef_t_per_mwh", "project_or_leakage")
    key = "baseline_low_hydro" if hydro_below_50pct else "baseline_other"
    return profile.tool_value("TOOL05", "default_ef_t_per_mwh", key)


def default_tdl(profile: Profile, source: str, project_leakage_mwh: Decimal, baseline_mwh: Decimal = Decimal(0)) -> tuple[Decimal, ParamRef]:
    """Default transmission and distribution losses (20% for project/leakage, 3% for baseline)."""
    baseline_larger = baseline_mwh > project_leakage_mwh
    if source in ("project", "leakage") and not baseline_larger:
        return profile.tool_value("TOOL05", "tdl_fraction", "project_or_leakage")
    if source == "baseline" and project_leakage_mwh > baseline_mwh:
        return profile.tool_value("TOOL05", "tdl_fraction", "project_or_leakage")
    return profile.tool_value("TOOL05", "tdl_fraction", "baseline")


def captive_plant_emissions(profile: Profile, rated_capacity_mw: Decimal) -> tuple[Decimal, ParamRef]:
    """Option B4: 11,400 tCO2 per MW per year (1.3 tCO2/MWh x 8,760 h, rounded as in the tool)."""
    factor, ref = profile.tool_value("TOOL05", "captive_capacity_tco2_per_mw_year")
    return factor * rated_capacity_mw, ref
