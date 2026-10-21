"""Calculation tests: VM0044 equations, permanence defaults, CDM tool vectors (METHODOLOGY-VM0044.md sections 6, 8)."""
from __future__ import annotations

from decimal import Decimal

import pytest

from climaudit.calc import tool03, tool05, tool12, vm0044
from climaudit.decimals import D, tonnes_to_kg_int
from climaudit.errors import ApiError
from climaudit.profiles import ProfileRegistry

REG = ProfileRegistry()
VM = REG.get("VM0044@1.2")
WOOLF = REG.get("WOOLF2021@alt")


def base_inputs(**over):
    values = dict(
        facility_class="high",
        dry_mass_t=D("100"),
        facility_total_dry_mass_t=D("100"),
        fc=D("0.80"),
        pr_de=D("0.89"),
        pe_d_tco2e=D("0"),
        pe_c_tco2e=D("0"),
    )
    values.update(over)
    return vm0044.VM0044Inputs(**values)


def test_profiles_load_and_have_expected_ids():
    assert REG.ids() == ["VM0044@1.2", "WOOLF2021@alt"]


@pytest.mark.parametrize(
    "temp,expected",
    [
        ("650", "0.89"),
        ("600.01", "0.89"),
        ("600", "0.80"),
        ("500", "0.80"),
        ("450.01", "0.80"),
        ("450", "0.65"),
        ("350", "0.65"),
    ],
)
def test_vm0044_table3_permanence_by_temperature(temp, expected):
    value, ref = VM.permanence_from_temperature(D(temp))
    assert value == D(expected) and ref.verified and ref.page == 22


def test_permanence_unknown_temperature_default_and_below_table():
    value, ref = VM.permanence_from_temperature(None)
    assert value == D("0.56") and ref.verified
    with pytest.raises(ApiError) as err:
        VM.permanence_from_temperature(D("300"))
    assert err.value.code == "FACTOR_SOURCE_MISSING"


def test_vector_high_tech_over_600():
    result = vm0044.compute(base_inputs())
    assert result.cc_t_c == D("71.2")
    assert tonnes_to_kg_int(result.net_tco2e, "central") == 261067  # 261.0666...
    assert str(result.gross_removal_tco2e.quantize(D("0.0001"))) == "261.0667"


def test_vector_low_tech_unknown_temperature_default():
    result = vm0044.compute(base_inputs(facility_class="low", pr_de=D("0.56"), ch4_factor_t_per_t=D("0"), gwp_ch4=D("1")))
    assert result.cc_t_c == D("44.8")
    assert str(result.net_tco2e.quantize(D("0.0001"))) == "164.2667"


def test_low_tech_conversion_emissions_use_facility_total_and_share():
    # Fe * GWP * M_p,y allocated by M/M_p,y equals Fe * GWP * M (test-only GWP)
    inp = base_inputs(
        facility_class="low", dry_mass_t=D("10"), facility_total_dry_mass_t=D("40"), pr_de=D("0.56"),
        ch4_factor_t_per_t=D("0.049"), gwp_ch4=D("28"),
    )
    result = vm0044.compute(inp)
    assert result.pe_ps_tco2e == D("0.049") * D("28") * D("10")
    assert result.pe_p_tco2e == D("0.049") * D("28") * D("40")


def test_low_tech_requires_ch4_inputs_and_mass_checks():
    with pytest.raises(ApiError) as err:
        vm0044.compute(base_inputs(facility_class="low"))
    assert err.value.code == "FACTOR_SOURCE_MISSING"
    with pytest.raises(ApiError):
        vm0044.compute(base_inputs(dry_mass_t=D("101")))
    with pytest.raises(ApiError):
        vm0044.compute(base_inputs(fc=D("1.2")))


def test_net_subtracts_emission_terms():
    inp = base_inputs(pe_d_tco2e=D("2"), pe_c_tco2e=D("1"), e_p_tco2e=D("0.5"), le_ts_tco2e=D("0.25"), le_tap_tco2e=D("0.25"))
    result = vm0044.compute(inp)
    assert result.net_tco2e == result.gross_removal_tco2e - D("3") - D("0.5") - D("0.5")


def test_bounds_are_ordered_and_conservative():
    inp = base_inputs(pe_d_tco2e=D("2"), le_ts_tco2e=D("1"))
    rel_u = {"dry_mass_t": D("0.02"), "fc": D("0.02"), "pr_de": D("0"), "pe_d_tco2e": D("0.10"), "le_ts_tco2e": D("0.10")}
    low, central, high = vm0044.bounds(inp, rel_u)
    assert low.net_tco2e < central.net_tco2e < high.net_tco2e
    zero = vm0044.bounds(inp, {})
    assert zero[0].net_tco2e == zero[1].net_tco2e == zero[2].net_tco2e


def test_fc_default_table4_and_mixed_rule_value():
    value, ref = VM.fc_default("wood", "pyrolysis")
    assert value == D("0.77") and ref.verified
    assert VM.fc_default("animal_manure", "gasification")[0] == D("0.09")
    with pytest.raises(ApiError):
        VM.fc_default("plastic", "pyrolysis")


def test_h_corg_limit_is_le_07_with_ambiguity_note():
    limit = VM.limit("h_corg_molar", "soil")
    assert limit["operator"] == "le" and limit["value"] == "0.7" and "less than 0.7" in limit["ambiguity"]
    assert VM.limit("h_corg_molar", "non_soil") is None


def test_woolf_alternative_profile_is_separate_and_capped():
    value, ref = WOOLF.permanence_from_hcorg(D("0.16"), D("14.9"))
    assert value == D("1.04") - D("0.64") * D("0.16")
    capped, _ = WOOLF.permanence_from_hcorg(D("0"), D("10"))
    assert capped == D("1")  # 1.10 capped at 1 (our choice)
    with pytest.raises(ApiError):
        VM.permanence_from_hcorg(D("0.16"), D("14.9"))  # VM0044 profile never uses the regression


# ------------------------------------------------------------------- CDM tools
def test_tool12_vectors():
    heavy = tool12.FreightLeg("l1", "biochar", "road", D("100"), D("100"), "heavy")
    light = tool12.FreightLeg("l2", "biochar", "road", D("100"), D("100"), "light")
    assert tool12.leg_emissions(VM, heavy)[0] == D("1.29")
    assert tool12.leg_emissions(VM, light)[0] == D("2.45")


def test_tool12_threshold_counts_exactly_200_km_conservatively():
    below = tool12.FreightLeg("c", "biochar", "road", D("199.99"), D("10"), "heavy")
    at = tool12.FreightLeg("a", "biomass", "road", D("200"), D("10"), "heavy")
    above = tool12.FreightLeg("b", "biomass", "road", D("250"), D("10"), "heavy")
    totals, _refs, notes = tool12.leakage_by_kind(VM, [at, above, below])
    assert totals["biochar"] == 0
    assert totals["biomass"] == (D("200") + D("250")) * D("10") * D("129") / D("1000000")
    assert [n["counted"] for n in notes] == ["true", "true", "false"]


def test_tool05_vectors():
    assert tool05.electricity_emissions(D("100"), D("1.3"), D("0.20")) == D("156")
    ef, _ = tool05.default_grid_ef(VM, "project", D("100"))
    tdl, _ = tool05.default_tdl(VM, "project", D("100"))
    assert (ef, tdl) == (D("1.3"), D("0.20"))
    assert tool05.default_grid_ef(VM, "baseline", D("10"), D("100"), hydro_below_50pct=True)[0] == D("0.4")
    assert tool05.default_grid_ef(VM, "baseline", D("10"), D("100"), hydro_below_50pct=False)[0] == D("0.25")
    assert tool05.default_tdl(VM, "baseline", D("10"), D("100"))[0] == D("0.03")
    assert tool05.captive_plant_emissions(VM, D("0.5"))[0] == D("5700")


def test_tool03_vectors_option_b_and_a():
    option_b = tool03.FuelUse("diesel", D("1000"), "B", ncv=D("0.043"), ef_co2=D("0.0741"))
    assert tool03.co2_coefficient(option_b) == D("0.043") * D("0.0741")  # 0.0031863 placeholders, not tool values
    option_a_mass = tool03.FuelUse("coal", D("10"), "A", carbon_fraction=D("0.6"))
    assert tool03.co2_from_fuels([option_a_mass]) == D("10") * D("0.6") * (D(44) / D(12))
    option_a_volume = tool03.FuelUse("oil", D("5"), "A", carbon_fraction=D("0.85"), density=D("0.9"), quantity_is_volume=True)
    assert tool03.co2_coefficient(option_a_volume) == D("0.85") * D("0.9") * (D(44) / D(12))
    with pytest.raises(ValueError):
        tool03.co2_coefficient(tool03.FuelUse("x", D("1"), "A"))


def test_batch_slices_of_the_allocation_sum_to_equation_3_over_the_facility_year():
    # VM0044 Eq. 3: PE_PS = (P_ED + P_EP + P_EC) * (sum_t sum_k M_t,k,p,y / M_p,y); per-batch slices M_i / M_p,y must add up to it.
    total_facility = D("100")
    masses = [D("10"), D("25"), D("5")]
    pe_d, pe_c = D("2"), D("1")
    slices = [vm0044.compute(base_inputs(dry_mass_t=m, facility_total_dry_mass_t=total_facility, pe_d_tco2e=pe_d, pe_c_tco2e=pe_c)).pe_ps_tco2e for m in masses]
    assert sum(slices) == (pe_d + pe_c) * (sum(masses) / total_facility)
