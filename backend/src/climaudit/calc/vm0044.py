"""Verra VM0044 v1.2 calculation (METHODOLOGY-VM0044.md section 2). Pure Decimal functions.

ER_y   = ER_SS + ER_PS - PE_AS - LE                         (Eq. 15)
ER_PS  = CC * 44/12 - PE_PS                                  (Eq. 1)
CC     = M * FC * PR_de                                      (Eq. 2 / Eq. 6)
PE_PS  = (P_ED + P_EP + P_EC) * M / M_p,y                    (Eq. 3 / Eq. 7, verified on the page images; M is the
                                                              batch slice of sum_t sum_k M_t,k,p,y)
PE_P   = 0 (high technology) or Fe * GWP_CH4 * M_p,y         (Eq. 9; evaluated on the facility total so that the
                                                              mass-share allocation yields Fe * GWP * M)
PE_AS  = E_P + E_ap, with E_ap = 0                           (Eq. 11-12)
LE     = LE_as + LE_bd + LE_ts + LE_tap, LE_as = LE_bd = 0   (Eq. 13)

Every value that comes from the methodology is passed in already resolved from a profile (with its ParamRef);
nothing here holds a methodology constant except the exact 44/12 conversion and structural zeros named in the
profile as `e_ap_application_tco2e` and `pe_conversion_high_tech_tco2e`.
"""
from __future__ import annotations

from dataclasses import dataclass, field, replace
from decimal import Decimal

from ..decimals import C_TO_CO2
from ..errors import ApiError


@dataclass(frozen=True)
class VM0044Inputs:
    facility_class: str  # "high" | "low"
    dry_mass_t: Decimal  # M_t,k,p,y
    facility_total_dry_mass_t: Decimal  # M_p,y
    fc: Decimal  # organic carbon fraction (0..1), lab value or low-tech default
    pr_de: Decimal  # permanence factor, resolved from the profile
    pe_d_tco2e: Decimal  # facility-year pre-treatment emissions (Eq. 4 / 8)
    pe_c_tco2e: Decimal  # facility-year auxiliary energy emissions (Eq. 5 / 10)
    pe_p_high_tech_tco2e: Decimal = Decimal(0)  # profile value (0 for high technology)
    ch4_factor_t_per_t: Decimal | None = None  # Fe, low technology
    gwp_ch4: Decimal | None = None  # low technology
    e_p_tco2e: Decimal = Decimal(0)  # processing of biochar (Eq. 12)
    e_ap_tco2e: Decimal = Decimal(0)  # utilization (profile: 0)
    le_ts_tco2e: Decimal = Decimal(0)
    le_tap_tco2e: Decimal = Decimal(0)
    er_ss_tco2e: Decimal = Decimal(0)  # Eq. 14, zero for waste biomass


@dataclass(frozen=True)
class VM0044Result:
    cc_t_c: Decimal
    gross_removal_tco2e: Decimal
    pe_p_tco2e: Decimal
    pe_ps_tco2e: Decimal
    er_ps_tco2e: Decimal
    pe_as_tco2e: Decimal
    le_tco2e: Decimal
    er_ss_tco2e: Decimal
    net_tco2e: Decimal
    steps: list[dict[str, str]] = field(default_factory=list)


def compute(inp: VM0044Inputs) -> VM0044Result:
    if inp.facility_total_dry_mass_t <= 0 or inp.dry_mass_t < 0:
        raise ApiError("CALC_FAILED", {"step": "mass_must_be_positive"})
    if inp.dry_mass_t > inp.facility_total_dry_mass_t:
        raise ApiError("VALIDATION_FAILED", {"field": "dry_mass_t", "rule": "not_above_facility_total"})
    if not (Decimal(0) <= inp.fc <= Decimal(1)):
        raise ApiError("VALIDATION_FAILED", {"field": "fc", "rule": "fraction_0_1"})
    if not (Decimal(0) <= inp.pr_de <= Decimal(1)):
        raise ApiError("VALIDATION_FAILED", {"field": "pr_de", "rule": "fraction_0_1"})

    steps: list[dict[str, str]] = []

    def step(name: str, value: Decimal, formula: str) -> Decimal:
        steps.append({"name": name, "value": format(value, "f"), "formula": formula})
        return value

    cc = step("CC", inp.dry_mass_t * inp.fc * inp.pr_de, "M * FC * PR_de")
    gross = step("gross_removal_tco2e", cc * C_TO_CO2, "CC * 44/12")

    if inp.facility_class == "high":
        pe_p = step("PE_P", inp.pe_p_high_tech_tco2e, "high technology: profile value")
    else:
        if inp.ch4_factor_t_per_t is None or inp.gwp_ch4 is None:
            raise ApiError("FACTOR_SOURCE_MISSING", {"parameter": "ch4_factor_or_gwp", "methodology": "VM0044"})
        pe_p = step("PE_P", inp.ch4_factor_t_per_t * inp.gwp_ch4 * inp.facility_total_dry_mass_t, "Fe * GWP_CH4 * M_p,y (Eq. 9, facility total)")

    share = inp.dry_mass_t / inp.facility_total_dry_mass_t
    pe_ps = step("PE_PS", (inp.pe_d_tco2e + pe_p + inp.pe_c_tco2e) * share, "(PE_D + PE_P + PE_C) * M / M_p,y")
    er_ps = step("ER_PS", gross - pe_ps, "CC * 44/12 - PE_PS")
    pe_as = step("PE_AS", inp.e_p_tco2e + inp.e_ap_tco2e, "E_P + E_ap")
    le = step("LE", inp.le_ts_tco2e + inp.le_tap_tco2e, "LE_ts + LE_tap (LE_as = LE_bd = 0)")
    net = step("ER_y", inp.er_ss_tco2e + er_ps - pe_as - le, "ER_SS + ER_PS - PE_AS - LE")
    return VM0044Result(
        cc_t_c=cc,
        gross_removal_tco2e=gross,
        pe_p_tco2e=pe_p,
        pe_ps_tco2e=pe_ps,
        er_ps_tco2e=er_ps,
        pe_as_tco2e=pe_as,
        le_tco2e=le,
        er_ss_tco2e=inp.er_ss_tco2e,
        net_tco2e=net,
        steps=steps,
    )


# --------------------------------------------------------------------------- uncertainty (Decision 4)
# Positive effect on removals: more mass, more carbon, more permanence. Negative: any emission term.
_REMOVAL_FIELDS = ("dry_mass_t", "fc", "pr_de")
_EMISSION_FIELDS = (
    "pe_d_tco2e", "pe_c_tco2e", "pe_p_high_tech_tco2e", "e_p_tco2e", "e_ap_tco2e", "le_ts_tco2e", "le_tap_tco2e",
    "ch4_factor_t_per_t", "gwp_ch4",
)


def shifted(inp: VM0044Inputs, rel_u: dict[str, Decimal], direction: str) -> VM0044Inputs:
    """Move every input to its adverse (direction="low") or favorable ("high") bound.

    Removal-increasing inputs are multiplied by (1 - u) for low and (1 + u) for high, with the fraction fields
    capped at 1; emission terms are multiplied by (1 + u) for low and (1 - u) for high. Mass and facility total
    move together so the allocation share does not change.
    """
    if direction not in ("low", "high"):
        raise ValueError("direction must be 'low' or 'high'")
    sign_removal = Decimal(-1) if direction == "low" else Decimal(1)
    changes: dict[str, Decimal] = {}
    for name in _REMOVAL_FIELDS:
        u = rel_u.get(name, Decimal(0))
        value = getattr(inp, name) * (Decimal(1) + sign_removal * u)
        if name in ("fc", "pr_de"):
            value = min(max(value, Decimal(0)), Decimal(1))
        changes[name] = value
    changes["facility_total_dry_mass_t"] = inp.facility_total_dry_mass_t * (Decimal(1) + sign_removal * rel_u.get("dry_mass_t", Decimal(0)))
    for name in _EMISSION_FIELDS:
        current = getattr(inp, name)
        if current is None:
            continue
        u = rel_u.get(name, Decimal(0))
        changes[name] = current * (Decimal(1) - sign_removal * u)
    return replace(inp, **changes)


def bounds(inp: VM0044Inputs, rel_u: dict[str, Decimal]) -> tuple[VM0044Result, VM0044Result, VM0044Result]:
    """Return (low, central, high) results. The interval is conservative and not a probability statement."""
    central = compute(inp)
    adverse = compute(shifted(inp, rel_u, "low"))
    favorable = compute(shifted(inp, rel_u, "high"))
    # For a negative net the "adverse" corner can be the larger number, so order the corners explicitly.
    low, high = (adverse, favorable) if adverse.net_tco2e <= favorable.net_tco2e else (favorable, adverse)
    if central.net_tco2e < low.net_tco2e:
        low = central
    if central.net_tco2e > high.net_tco2e:
        high = central
    return low, central, high
