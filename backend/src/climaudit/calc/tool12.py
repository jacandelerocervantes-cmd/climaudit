"""CDM TOOL12 v01.1.0 Option B: freight transport with conservative defaults (research/sources/cdm-tool12).

Eq. 1: PE_TR,m (or LE_TR,m) = sum_f D_f,m * FR_f,m * EF_CO2,f / 10^6   [tCO2]
D is the return-trip distance (km), FR the freight mass (t), EF in g CO2 per t-km (light 245, heavy 129).
The printed factor is 10^-6 (verified on the page image of TOOL12 p. 6), i.e. a divisor of 10^6.
"""
from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal

from ..profiles import ParamRef, Profile


@dataclass(frozen=True)
class FreightLeg:
    leg_id: str
    kind: str  # "biomass" (LE_ts) or "biochar" (LE_tap)
    mode: str  # road | rail | ship | other
    distance_km_return: Decimal
    freight_t: Decimal
    vehicle_class: str | None  # light | heavy (rail uses the heavy default)


def leg_emissions(profile: Profile, leg: FreightLeg) -> tuple[Decimal, list[ParamRef]]:
    vehicle = leg.vehicle_class or "heavy"
    ef, ef_ref = profile.tool_value("TOOL12", "ef_g_per_t_km", vehicle)
    divisor, div_ref = profile.tool_value("TOOL12", "divisor")
    return leg.distance_km_return * leg.freight_t * ef / divisor, [ef_ref, div_ref]


def counts_toward_leakage(profile: Profile, leg: FreightLeg) -> tuple[bool, Decimal, ParamRef]:
    """Transport leakage counts above the profile threshold; the comparison (strict or inclusive) is a profile field.

    The VM0044 text leaves exactly 200 km undefined, so the profile counts it (the conservative side).
    """
    threshold, ref = profile.rule("transport_threshold_km")
    comparison = profile.rule_entry("transport_threshold_km").get("comparison", "strictly_greater")
    counted = leg.distance_km_return >= threshold if comparison == "greater_or_equal" else leg.distance_km_return > threshold
    return counted, threshold, ref


def leakage_by_kind(profile: Profile, legs: list[FreightLeg]) -> tuple[dict[str, Decimal], list[ParamRef], list[dict[str, str]]]:
    """Return {"biomass": LE_ts, "biochar": LE_tap}, the refs used, and per-leg notes."""
    totals = {"biomass": Decimal(0), "biochar": Decimal(0)}
    refs: list[ParamRef] = []
    notes: list[dict[str, str]] = []
    for leg in legs:
        counts, threshold, thr_ref = counts_toward_leakage(profile, leg)
        refs.append(thr_ref)
        if not counts:
            notes.append({"leg_id": leg.leg_id, "counted": "false", "reason": f"distance below the {threshold} km threshold"})
            continue
        emissions, leg_refs = leg_emissions(profile, leg)
        refs.extend(leg_refs)
        totals[leg.kind] += emissions
        notes.append({"leg_id": leg.leg_id, "counted": "true", "tco2": format(emissions, "f")})
    return totals, refs, notes
