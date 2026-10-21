"""Verification pipeline: rule checks, deterministic VM0044 calculation with bounds, report assembly.

The AI never runs here. The narrative is built from computed figures by a template and passes through the
grounding check; a model-written narrative would have to pass the same check (REPORT_WITHHELD_UNGROUNDED).
"""
from __future__ import annotations

from dataclasses import dataclass, field
from decimal import Decimal
from typing import Any

from . import grounding
from .calc import tool12, vm0044
from .checks import benford, rules
from .decimals import dstr, tonnes_to_kg_int
from .errors import ApiError
from .evidence import EvidenceItem, EvidenceView
from .findings import Finding, blocks_calculation, blocks_verified, make
from .models import BatchRecord, Facility
from .profiles import ParamRef, Profile

_SEVERITY_ORDER = {"critical": 0, "high": 1, "medium": 2, "low": 3, "info": 4}
_REJECT_CODES = {
    "PERIOD_OVERLAP_DETECTED",
    "PARCEL_CELL_OVERLAP",
    "H_CORG_ABOVE_LIMIT",
    "FEEDSTOCK_NOT_ELIGIBLE",
    "FEEDSTOCK_IMPORTED",
    "NON_SOIL_FROM_LOW_TECH",
    "DOCUMENT_HASH_MISMATCH",
}


@dataclass
class VerificationInput:
    profile: Profile
    facility: Facility
    batch: BatchRecord
    evidence: list[EvidenceItem]
    facility_year: list[EvidenceItem]
    project_country: str
    document_findings: list[Finding] = field(default_factory=list)
    extra_findings: list[Finding] = field(default_factory=list)


def _item_u(item: EvidenceItem | None, modeled_u: Decimal) -> tuple[Decimal, bool]:
    """Relative uncertainty of an item and whether the profile's modeled value was used."""
    if item is None:
        return Decimal(0), False
    try:
        if Decimal(item.value) == 0:
            return Decimal(0), False  # a zero term has nothing to discount
    except ArithmeticError:
        pass
    # A reported uncertainty is only believed when a document backs it; a measured value without a document
    # reference is an assertion, so it receives the conservative modeled default.
    if item.rel_uncertainty is not None and item.document_ref:
        return Decimal(item.rel_uncertainty), False
    if item.provenance == "measured" and item.document_ref and item.rel_uncertainty is None:
        return modeled_u, True
    return modeled_u, True


def _group_sum_and_u(items: list[EvidenceItem], modeled_u: Decimal) -> tuple[Decimal, Decimal, bool]:
    total = sum((Decimal(i.value) for i in items), Decimal(0))
    us = [_item_u(i, modeled_u) for i in items]
    return total, max((u for u, _ in us), default=Decimal(0)), any(flag for _, flag in us)


def _sorted(findings: list[Finding]) -> list[Finding]:
    return sorted(findings, key=lambda f: (_SEVERITY_ORDER[f.severity], f.code))


def _recommendation(findings: list[Finding]) -> str:
    if any(f.code in _REJECT_CODES for f in findings):
        return "reject"
    if blocks_calculation(findings) or blocks_verified(findings):
        return "return"
    return "human_review"


def _unverified(refs: list[ParamRef], profile: Profile) -> list[Finding]:
    seen: set[str] = set()
    out: list[Finding] = []
    for ref in refs:
        if not ref.verified and ref.name not in seen:
            seen.add(ref.name)
            out.append(make("METHODOLOGY_PARAMETER_UNVERIFIED", parameter=ref.name, profile_id=profile.profile_id))
    return out


def _legs(view: EvidenceView) -> list[tool12.FreightLeg]:
    legs: list[tool12.FreightLeg] = []
    for leg_id, items in sorted(view.groups("transport_mode", "transport_distance_km_return", "transport_freight_t", "vehicle_class", "transport_leg_kind").items()):
        if not all(k in items for k in ("transport_mode", "transport_distance_km_return", "transport_freight_t", "transport_leg_kind")):
            continue
        legs.append(
            tool12.FreightLeg(
                leg_id=leg_id,
                kind=items["transport_leg_kind"].value,
                mode=items["transport_mode"].value,
                distance_km_return=Decimal(items["transport_distance_km_return"].value),
                freight_t=Decimal(items["transport_freight_t"].value),
                vehicle_class=items["vehicle_class"].value if "vehicle_class" in items else None,
            )
        )
    return legs


def _benford_findings(view: EvidenceView, profile: Profile) -> list[Finding]:
    cfg = profile.data.get("benford") or {}
    if not cfg:
        return []
    critical = Decimal(cfg["chi2_critical_8dof"]["alpha_0.05"])
    out: list[Finding] = []
    series: dict[str, list[Decimal]] = {}
    for item in view.all("log_series_value"):
        series.setdefault(item.group or "default", []).append(Decimal(item.value))
    for name, values in sorted(series.items()):
        result = benford.screen(values, critical, int(cfg["min_series_length"]), int(cfg["min_orders_of_magnitude"]))
        if result.applicable and result.flagged:
            out.append(make("BENFORD_ANOMALY", series=name, n=result.n, chi2=f"{result.chi2:.2f}", critical=str(critical)))
    return out


def verify(inp: VerificationInput) -> dict[str, Any]:
    profile = inp.profile
    ev, fy = EvidenceView(inp.evidence), EvidenceView(inp.facility_year)
    ctx = rules.CheckContext(profile, inp.facility, inp.batch, ev, fy, inp.project_country)
    derived_class, findings = rules.run_all(ctx)
    findings = list(inp.document_findings) + list(inp.extra_findings) + findings
    findings += _benford_findings(ev, profile)
    pending = len(EvidenceView(inp.evidence).pending)

    report: dict[str, Any] = {
        "profile_id": profile.profile_id,
        "batch_id": inp.batch.batch_id,
        "facility_class": derived_class,
        "pending_items": pending,
        "profile_label": profile.label,
        "alternative_permanence_model": profile.alternative,
        "kg_co2e": None,
        "issuable_kg": 0,
    }

    if blocks_calculation(findings):
        return _finish(report, findings, status="incomplete", profile=profile, calc=None, allowed=set())

    modeled_u, modeled_ref = profile.modeled_relative_uncertainty()
    refs: list[ParamRef] = []
    modeled_fields: set[str] = set()

    fe_u = gwp_u = Decimal(0)
    try:
        dry_item = ev.one("dry_mass_biochar")
        m, (m_u, flag) = Decimal(dry_item.value), _item_u(dry_item, modeled_u)
        if flag:
            modeled_fields.add("dry_mass_t")
        mpy = fy.dec("facility_total_dry_mass")

        # organic carbon fraction
        fc_item = ev.one("organic_carbon_fraction")
        process = ev.text("process_type") or inp.facility.process
        if fc_item is not None:
            fc, (fc_u, flag) = Decimal(fc_item.value), _item_u(fc_item, modeled_u)
            if flag:
                modeled_fields.add("fc")
            fc_source = "laboratory"
        else:
            fc, fc_ref = profile.fc_default(ev.text("feedstock_class") or "", "gasification" if process == "gasification" else "pyrolysis")
            refs.append(fc_ref)
            fc_u, fc_source = Decimal(0), "profile_default_table4"

        # permanence
        temp = ev.dec("pyrolysis_temp_c")
        if profile.permanence_mode == "temperature_table":
            pr, pr_ref = profile.permanence_from_temperature(temp)
        else:
            pr, pr_ref = profile.permanence_from_hcorg(ev.dec("h_corg_molar") or Decimal(0), ev.dec("soil_temp_c") or Decimal(0))
        refs.append(pr_ref)

        pe_d, pe_d_u, f1 = _group_sum_and_u([*fy.all("pe_pretreat_electricity_tco2e"), *fy.all("pe_pretreat_fuel_tco2e")], modeled_u)
        pe_c, pe_c_u, f2 = _group_sum_and_u([*fy.all("pe_auxiliary_electricity_tco2e"), *fy.all("pe_auxiliary_fuel_tco2e")], modeled_u)
        e_p_items = ev.all("pe_processing_tco2e")
        e_p, e_p_u, f3 = _group_sum_and_u(e_p_items, modeled_u)
        if f1:
            modeled_fields.add("pe_d_tco2e")
        if f2:
            modeled_fields.add("pe_c_tco2e")
        if f3:
            modeled_fields.add("e_p_tco2e")

        legs = _legs(ev)
        totals, leg_refs, leg_notes = tool12.leakage_by_kind(profile, legs)
        refs.extend(leg_refs)
        leg_items = [i for i in ev.items if i.kind in ("transport_distance_km_return", "transport_freight_t")]
        le_u = max((_item_u(i, modeled_u)[0] for i in leg_items), default=Decimal(0))
        if any(_item_u(i, modeled_u)[1] for i in leg_items):
            modeled_fields.update({"le_ts_tco2e", "le_tap_tco2e"})

        pe_p_high, pe_p_ref = profile.default_value("pe_conversion_high_tech_tco2e")
        e_ap, e_ap_ref = profile.default_value("e_ap_application_tco2e")
        refs.extend([pe_p_ref, e_ap_ref])
        fe = gwp = None
        if derived_class == "low":
            fe_item = ev.dec("ch4_factor_t_per_t")
            if fe_item is None:
                fe, fe_ref = profile.default_value("ch4_factor_unlisted_kiln_t_per_t")
                refs.append(fe_ref)
            else:
                fe = fe_item
            gwp = ev.dec("gwp_ch4")
            fe_u, f_fe = _item_u(ev.one("ch4_factor_t_per_t"), modeled_u)
            gwp_u, f_gwp = _item_u(ev.one("gwp_ch4"), modeled_u)
            if (f_fe and fe_item is not None) or f_gwp:
                modeled_fields.update({"ch4_factor_t_per_t", "gwp_ch4"})

        inputs = vm0044.VM0044Inputs(
            facility_class=derived_class,
            dry_mass_t=m,
            facility_total_dry_mass_t=mpy,
            fc=fc,
            pr_de=pr,
            pe_d_tco2e=pe_d,
            pe_c_tco2e=pe_c,
            pe_p_high_tech_tco2e=pe_p_high,
            ch4_factor_t_per_t=fe,
            gwp_ch4=gwp,
            e_p_tco2e=e_p,
            e_ap_tco2e=e_ap,
            le_ts_tco2e=totals["biomass"],
            le_tap_tco2e=totals["biochar"],
        )
        rel_u = {
            "dry_mass_t": m_u,
            "fc": fc_u,
            "pr_de": Decimal(0),
            "pe_d_tco2e": pe_d_u,
            "pe_c_tco2e": pe_c_u,
            "e_p_tco2e": e_p_u,
            "le_ts_tco2e": le_u,
            "le_tap_tco2e": le_u,
            "ch4_factor_t_per_t": fe_u,
            "gwp_ch4": gwp_u,
        }
        low, central, high = vm0044.bounds(inputs, rel_u)
    except ApiError as err:
        if err.code == "FACTOR_SOURCE_MISSING":
            findings.append(make("FACTOR_WITHOUT_SOURCE", parameter=str(err.params.get("parameter", err.code)), error=err.code))
        elif err.code == "VALIDATION_FAILED":
            findings.append(make("VALUE_OUT_OF_RANGE", field=str(err.params.get("field", "calculation")), rule=str(err.params.get("rule", ""))))
        elif err.code == "CALC_FAILED":
            findings.append(make("CALC_MISMATCH", step=str(err.params.get("step", "calculation"))))
        else:
            raise
        return _finish(report, findings, status="incomplete", profile=profile, calc=None, allowed=set())
    except ArithmeticError as err:  # decimal overflow / invalid operation on absurd magnitudes
        findings.append(make("VALUE_OUT_OF_RANGE", field="calculation", rule=type(err).__name__))
        return _finish(report, findings, status="incomplete", profile=profile, calc=None, allowed=set())

    kg = {
        "low": tonnes_to_kg_int(low.net_tco2e, "low"),
        "central": tonnes_to_kg_int(central.net_tco2e, "central"),
        "high": tonnes_to_kg_int(high.net_tco2e, "high"),
    }
    width_cap, _ = profile.tolerance("uncertainty_width_max_pct")
    if kg["central"] > 0 and (Decimal(kg["high"] - kg["low"]) / Decimal(kg["central"])) * 100 > width_cap:
        findings.append(make("UNCERTAINTY_TOO_HIGH", low=kg["low"], central=kg["central"], high=kg["high"], max_width_pct=str(width_cap)))

    contributions = []
    for name, u in rel_u.items():
        if u > 0:
            single = vm0044.compute(vm0044.shifted(inputs, {name: u}, "low"))
            delta = single.net_tco2e - central.net_tco2e
            if delta != 0 and name in modeled_fields:
                if modeled_ref not in refs:
                    refs.append(modeled_ref)
            contributions.append({"input": name, "relative_uncertainty": dstr(u), "delta_kg_low": tonnes_to_kg_int(delta, "central")})
    findings += _unverified(refs, profile)

    claimed = inp.batch.claimed_kg_co2e
    issuable = max(0, kg["low"])
    if claimed > 0:
        issuable = min(issuable, claimed)
    report["kg_co2e"] = kg
    report["issuable_kg"] = issuable
    calc = {
        "equation_steps": central.steps,
        "inputs": {
            "dry_mass_t": dstr(m),
            "facility_total_dry_mass_t": dstr(mpy),
            "organic_carbon_fraction": dstr(fc),
            "organic_carbon_fraction_source": fc_source,
            "permanence_factor": dstr(pr),
            "pe_d_tco2e": dstr(pe_d),
            "pe_c_tco2e": dstr(pe_c),
            "e_p_tco2e": dstr(e_p),
            "le_ts_tco2e": dstr(totals["biomass"]),
            "le_tap_tco2e": dstr(totals["biochar"]),
        },
        "legs": leg_notes,
        "uncertainty": {
            "method": "all inputs moved to their adverse or favorable bound; conservative interval, not a probability statement",
            "relative_uncertainty_by_input": {k: dstr(v) for k, v in rel_u.items()},
            "contributions": contributions,
        },
        "params_used": [r.as_dict() for r in refs],
    }
    allowed = {str(v) for v in kg.values()} | {str(issuable), str(claimed), profile.version} | set(grounding.extract_numbers(profile.profile_id))
    allowed |= {calc["inputs"][k] for k in calc["inputs"] if k != "organic_carbon_fraction_source"}
    return _finish(report, findings, status="complete", profile=profile, calc=calc, allowed=allowed, kg=kg, issuable=issuable)


def _narrative(report: dict[str, Any], profile: Profile, kg: dict[str, int], issuable: int) -> str:
    return (
        f"Batch {report['batch_id']} was evaluated with profile {profile.profile_id} for a {report['facility_class']}-technology facility. "
        f"The deterministic calculation gives a central estimate of {kg['central']} kg CO2e, with a conservative interval from {kg['low']} to {kg['high']} kg CO2e. "
        f"At most {issuable} kg CO2e would be issuable after verification. "
        "This is a recommendation for human review, not a verification, certification or compliance statement."
    )


def _finish(
    report: dict[str, Any],
    findings: list[Finding],
    status: str,
    profile: Profile,
    calc: dict[str, Any] | None,
    allowed: set[str],
    kg: dict[str, int] | None = None,
    issuable: int = 0,
) -> dict[str, Any]:
    ordered = _sorted(findings)
    narrative = None
    grounded = grounding.GroundingResult(passed=True)
    if status == "complete" and kg is not None:
        narrative = _narrative(report, profile, kg, issuable)
        grounded = grounding.check(narrative, allowed | _batch_id_numbers(report["batch_id"]))
        if not grounded.passed:
            ordered = _sorted([*ordered, make("NARRATIVE_UNGROUNDED_NUMBER", discrepancies=grounded.discrepancies)])
            narrative = None
    report.update(
        {
            "status": status,
            "findings": [f.as_dict() for f in ordered],
            "blocks_calculation": blocks_calculation(ordered),
            "blocks_verified": blocks_verified(ordered),
            "calc": calc,
            "narrative_en": narrative,
            "grounding": {"passed": grounded.passed, "discrepancies": grounded.discrepancies, "numbers_checked": grounded.numbers_checked},
            "recommendation": _recommendation(ordered),
        }
    )
    return report


def _batch_id_numbers(batch_id: str) -> set[str]:
    return set(grounding.extract_numbers(batch_id))
