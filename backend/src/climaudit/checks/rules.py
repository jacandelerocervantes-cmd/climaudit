"""Deterministic rule checks on the evidence (METHODOLOGY-VM0044.md sections 3 and 7, BACKEND-SPEC.md section 8).

Each check returns findings; none computes credits. Thresholds come from the methodology profile.
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from decimal import Decimal

from ..evidence import KINDS, EvidenceView
from ..findings import Finding, make
from ..models import BatchRecord, Facility
from ..profiles import Profile

# evidence kind -> key of the profile's `plausibility` table
PLAUSIBILITY_KEYS = {
    "organic_carbon_fraction": "organic_carbon_fraction",
    "h_corg_molar": "h_corg_molar",
    "pyrolysis_temp_c": "pyrolysis_temp_c",
    "moisture_pct": "moisture_pct",
    "dry_mass_biochar": "dry_mass_biochar_t",
    "wet_mass_biochar": "wet_mass_biochar_t",
    "gwp_ch4": "gwp_ch4",
    "ch4_factor_t_per_t": "ch4_factor_t_per_t",
    "transport_distance_km_return": "transport_distance_km_return",
    "transport_freight_t": "transport_freight_t",
    "pe_processing_tco2e": "emission_term_tco2e",
}
FACILITY_YEAR_PLAUSIBILITY = {
    "facility_total_dry_mass": "facility_total_dry_mass_t",
    "pe_pretreat_electricity_tco2e": "emission_term_tco2e",
    "pe_pretreat_fuel_tco2e": "emission_term_tco2e",
    "pe_auxiliary_electricity_tco2e": "emission_term_tco2e",
    "pe_auxiliary_fuel_tco2e": "emission_term_tco2e",
}


@dataclass
class CheckContext:
    profile: Profile
    facility: Facility
    batch: BatchRecord
    evidence: EvidenceView
    facility_year: EvidenceView
    project_country: str


def _compare(operator: str, left: Decimal, right: Decimal) -> bool:
    return {"le": left <= right, "lt": left < right, "ge": left >= right, "gt": left > right}[operator]


def _dry_mass_from_wet(wet: Decimal, moisture_pct: Decimal, basis: str) -> Decimal:
    if basis == "dry":
        return wet / (Decimal(1) + moisture_pct / Decimal(100))
    return wet * (Decimal(1) - moisture_pct / Decimal(100))


def one_year_after(start: date) -> date:
    """Calendar year later; 29 February maps to 28 February (the stricter side)."""
    try:
        return start.replace(year=start.year + 1)
    except ValueError:
        return start.replace(year=start.year + 1, day=28)


def lots(ev: EvidenceView) -> dict[str, dict[str, date]]:
    """Production and application dates paired by lot (the `group` label)."""
    out: dict[str, dict[str, date]] = {}
    for kind in ("production_date", "application_date"):
        for item in ev.all(kind):
            out.setdefault(item.group or "", {})[kind] = date.fromisoformat(item.value)
    return out


def required_evidence(ctx: CheckContext) -> list[Finding]:
    ev, fy = ctx.evidence, ctx.facility_year
    missing: list[str] = []
    always = ["dry_mass_biochar", "feedstock_category", "feedstock_origin_country", "lab_report", "health_safety_program", "feedstock_fate_evidence", "transport_declaration"]
    soil_only = ["h_corg_molar", "land_type", "application_method"]
    non_soil = ["carbon_pct_dry", "product_lifetime_evidence"]
    for kind in always + (soil_only if ctx.batch.application_type == "soil" else non_soil):
        if not ev.has(kind):
            missing.append(kind)
    if not ev.all("application_date"):
        missing.append("application_date")
    if not ev.all("production_date"):
        missing.append("production_date")
    derived_high = ctx.facility.meets_high_tech(ctx.profile.rule("high_tech_min_heat_use_pct")[0])
    if derived_high and not ev.has("organic_carbon_fraction"):
        missing.append("organic_carbon_fraction")
    if not derived_high and not ev.has("organic_carbon_fraction") and not ev.has("feedstock_class"):
        missing.append("organic_carbon_fraction_or_feedstock_class")
    if derived_high and not ev.has("pyrolysis_temp_c"):
        missing.append("pyrolysis_temp_c")
    if ctx.profile.permanence_mode == "hcorg_linear":
        for kind in ("h_corg_molar", "soil_temp_c"):
            if not ev.has(kind) and kind not in missing:
                missing.append(kind)
    for kind in ("facility_total_dry_mass", "pe_pretreat_electricity_tco2e", "pe_pretreat_fuel_tco2e", "pe_auxiliary_electricity_tco2e", "pe_auxiliary_fuel_tco2e"):
        if not fy.has(kind):
            missing.append(kind)
    findings = [make("EVIDENCE_MISSING", kind=kind) for kind in missing]
    if ev.has("lab_report") and ev.boolean("lab_accredited") is not True:
        findings.append(make("EVIDENCE_MISSING", kind="lab_accredited", reason="not_accredited_or_not_declared"))
    return findings


def duplicates(ctx: CheckContext) -> list[Finding]:
    """A single-valued kind present more than once is ambiguous; the calculation must not pick one silently."""
    findings: list[Finding] = []
    for view in (ctx.evidence, ctx.facility_year):
        by_kind: dict[str, list] = {}
        for item in view.items:
            if not KINDS[item.kind].multi:
                by_kind.setdefault(item.kind, []).append(item)
        for kind, items in sorted(by_kind.items()):
            if len(items) > 1:
                findings.append(make("CALC_MISMATCH", field=kind, reason="duplicate_single_valued_kind", distinct_values=len({i.value for i in items})))
    return findings


def exclusion_rules(ctx: CheckContext) -> list[Finding]:
    ev, f = ctx.evidence, ctx.facility
    findings: list[Finding] = []
    if not f.is_greenfield:
        findings.append(make("EVIDENCE_MISSING", kind="facility", reason="not_greenfield"))
    process = ev.text("process_type") or f.process
    if process in ("torrefaction", "hydrothermal_carbonization"):
        findings.append(make("EVIDENCE_MISSING", kind="process_type", reason="excluded_process", value=process))
    if ctx.batch.application_type == "soil" and ev.text("land_type") == "wetland":
        findings.append(make("EVIDENCE_MISSING", kind="land_type", reason="wetland_not_eligible"))
    if ev.text("feedstock_category") == "purpose_grown":
        findings.append(make("FEEDSTOCK_NOT_ELIGIBLE", reason="purpose_grown"))
    origin, project_country = ev.text("feedstock_origin_country"), ctx.project_country
    if origin and project_country and origin.upper() != project_country.upper():
        findings.append(make("FEEDSTOCK_IMPORTED", origin=origin, project_country=project_country))
    return findings


def facility_class(ctx: CheckContext) -> tuple[str, list[Finding]]:
    """Derive the facility class from the four conditions; flag a declared high class that fails them."""
    min_heat, _ = ctx.profile.rule("high_tech_min_heat_use_pct")
    derived = "high" if ctx.facility.meets_high_tech(min_heat) else "low"
    findings: list[Finding] = []
    if ctx.facility.declared_class == "high" and derived == "low":
        missing = []
        if not ctx.facility.pyrolysis_gas_combusted:
            missing.append("pyrolysis_gas_combusted")
        if Decimal(ctx.facility.heat_use_pct) < min_heat:
            missing.append("heat_use_pct")
        if not ctx.facility.pollution_controls:
            missing.append("pollution_controls")
        if not ctx.facility.temperature_measured:
            missing.append("temperature_measured")
        findings.append(make("FACILITY_CLASS_INCONSISTENT", declared="high", missing_conditions=missing))
    return derived, findings


def plausibility(ctx: CheckContext) -> list[Finding]:
    findings: list[Finding] = []
    for view, table in ((ctx.evidence, PLAUSIBILITY_KEYS), (ctx.facility_year, FACILITY_YEAR_PLAUSIBILITY)):
        for kind, key in table.items():
            spec = ctx.profile.plausibility(key)
            if spec is None:
                continue
            low, high, ref = spec
            for item in view.all(kind):
                value = Decimal(item.value)
                if value < low or value > high:
                    findings.append(make("VALUE_OUT_OF_RANGE", field=kind, value=item.value, allowed=ref.value))
    claim_spec = ctx.profile.plausibility("claimed_kg_co2e")
    if claim_spec and not (claim_spec[0] <= Decimal(ctx.batch.claimed_kg_co2e) <= claim_spec[1]):
        findings.append(make("VALUE_OUT_OF_RANGE", field="claimed_kg_co2e", value=str(ctx.batch.claimed_kg_co2e), allowed=claim_spec[2].value))
    return findings


def moisture(ctx: CheckContext) -> list[Finding]:
    ev = ctx.evidence
    moisture_pct = ev.dec("moisture_pct")
    if moisture_pct is None:
        return []
    basis = ev.text("moisture_basis")
    if basis is None:
        return [make("MOISTURE_BASIS_UNSPECIFIED", field="moisture_pct")]
    if basis == "wet" and moisture_pct >= 100:
        return [make("VALUE_OUT_OF_RANGE", field="moisture_pct", value=str(moisture_pct), reason="wet_basis_must_be_below_100")]
    wet, dry = ev.dec("wet_mass_biochar"), ev.dec("dry_mass_biochar")
    if wet is None or dry is None:
        return []
    tol_pct, _ = ctx.profile.tolerance("mass_balance_pct")
    expected = _dry_mass_from_wet(wet, moisture_pct, basis)
    gap_to_expected = abs(dry - expected) / expected if expected else Decimal(0)
    gap_to_wet = abs(dry - wet) / wet if wet else Decimal(0)
    tol = tol_pct / Decimal(100)
    if gap_to_expected <= tol:
        return []
    if gap_to_wet <= tol and moisture_pct > tol_pct:
        return [make("MOISTURE_NOT_DEDUCTED", wet_t=str(wet), dry_t=str(dry), moisture_pct=str(moisture_pct), basis=basis)]
    return [make("CALC_MISMATCH", field="dry_mass_biochar", expected=format(expected, "f"), found=str(dry), basis=basis)]


def h_corg(ctx: CheckContext) -> list[Finding]:
    if ctx.batch.application_type != "soil":
        return []
    value = ctx.evidence.dec("h_corg_molar")
    limit = ctx.profile.limit("h_corg_molar", "soil")
    if value is None or limit is None:
        return []
    findings: list[Finding] = []
    bound = Decimal(limit["value"])
    if not _compare(limit["operator"], value, bound):
        findings.append(make("H_CORG_ABOVE_LIMIT", value=str(value), limit=limit["value"], operator=limit["operator"]))
    elif value == bound and limit.get("ambiguity"):
        findings.append(make("METHODOLOGY_TEXT_AMBIGUOUS", field="h_corg_molar", value=str(value), note=limit["ambiguity"]))
    if not limit.get("verified", False):
        findings.append(make("METHODOLOGY_PARAMETER_UNVERIFIED", parameter="limits.h_corg_molar", profile_id=ctx.profile.profile_id))
    return findings


def timing(ctx: CheckContext) -> list[Finding]:
    """One-year rule per lot, lot dates inside the batch period (the period is derived from the application dates)."""
    findings: list[Finding] = []
    start, end = date.fromisoformat(ctx.batch.period_start), date.fromisoformat(ctx.batch.period_end)
    for lot_id, dates in sorted(lots(ctx.evidence).items()):
        produced, applied = dates.get("production_date"), dates.get("application_date")
        if produced is None or applied is None:
            findings.append(make("EVIDENCE_MISSING", kind="production_date" if produced is None else "application_date", lot=lot_id))
            continue
        if applied < produced:
            findings.append(make("DATE_INCONSISTENT", field="application_date", reason="before_production", lot=lot_id))
        elif applied > one_year_after(produced):
            findings.append(make("APPLICATION_TOO_LATE", lot=lot_id, production_date=produced.isoformat(), application_date=applied.isoformat()))
        if not (start <= applied < end):
            findings.append(make("DATE_INCONSISTENT", field="application_date", reason="outside_batch_period", lot=lot_id, period_start=ctx.batch.period_start, period_end=ctx.batch.period_end))
    return findings


def non_soil_and_additives(ctx: CheckContext, derived_class: str) -> list[Finding]:
    ev = ctx.evidence
    findings: list[Finding] = []
    if ctx.batch.application_type == "non_soil":
        if derived_class != "high":
            findings.append(make("NON_SOIL_FROM_LOW_TECH"))
        carbon = ev.dec("carbon_pct_dry")
        minimum, _ = ctx.profile.rule("non_soil_min_carbon_pct")
        if carbon is not None and carbon < minimum:
            findings.append(make("CARBON_FRACTION_BELOW_50_NON_SOIL", carbon_pct_dry=str(carbon), minimum=str(minimum)))
    additive, maximum = ev.dec("additive_pct"), ctx.profile.rule("additive_max_pct")[0]
    if additive is not None and additive > maximum and ev.boolean("additive_lab_ok") is not True:
        findings.append(make("ADDITIVE_SHARE_ABOVE_LIMIT", additive_pct=str(additive), maximum=str(maximum)))
    return findings


def low_tech_methane_inputs(ctx: CheckContext, derived_class: str) -> list[Finding]:
    """GWP and the kiln CH4 factor are owner inputs; they must be documented and the factor cannot undercut the profile default."""
    if derived_class != "low":
        return []
    ev = ctx.evidence
    findings: list[Finding] = []
    gwp, fe = ev.one("gwp_ch4"), ev.one("ch4_factor_t_per_t")
    if gwp is None:
        findings.append(make("EVIDENCE_MISSING", kind="gwp_ch4", reason="required_for_low_technology"))
    elif not gwp.document_ref:
        findings.append(make("EVIDENCE_MISSING", kind="gwp_ch4", reason="document_ref_required"))
    if fe is not None:
        default, _ = ctx.profile.default_value("ch4_factor_unlisted_kiln_t_per_t")
        if not fe.document_ref:
            findings.append(make("EVIDENCE_MISSING", kind="ch4_factor_t_per_t", reason="document_ref_required"))
        elif Decimal(fe.value) < default and not ev.has("kiln_type"):
            findings.append(make("EVIDENCE_MISSING", kind="kiln_type", reason="needed_to_use_a_factor_below_the_default"))
    return findings


def transport(ctx: CheckContext) -> list[Finding]:
    threshold, _ = ctx.profile.rule("transport_threshold_km")
    groups = ctx.evidence.groups("transport_mode", "transport_distance_km_return", "transport_freight_t", "vehicle_class", "transport_leg_kind")
    declaration = ctx.evidence.text("transport_declaration")
    findings: list[Finding] = []
    if declaration == "none" and groups:
        findings.append(make("CALC_MISMATCH", field="transport_declaration", reason="declared_none_but_legs_present"))
    if declaration == "legs_provided" and not groups:
        findings.append(make("EVIDENCE_MISSING", kind="transport_leg", reason="declared_legs_provided_but_none_present"))
    for leg_id, items in sorted(groups.items()):
        distance_item, mode_item = items.get("transport_distance_km_return"), items.get("transport_mode")
        if distance_item is None or mode_item is None or "transport_freight_t" not in items or "transport_leg_kind" not in items:
            findings.append(make("EVIDENCE_MISSING", kind="transport_leg", leg_id=leg_id))
            continue
        distance, mode = Decimal(distance_item.value), mode_item.value
        if distance == threshold:
            findings.append(make("TRANSPORT_DISTANCE_AT_THRESHOLD", leg_id=leg_id, distance_km=str(distance)))
        if distance > threshold and mode not in ("road",):
            findings.append(make("TRANSPORT_MODE_NOT_ALLOWED", leg_id=leg_id, mode=mode, distance_km=str(distance)))
        if mode == "road" and "vehicle_class" not in items and distance >= threshold:
            findings.append(make("EVIDENCE_MISSING", kind="vehicle_class", leg_id=leg_id))
    return findings


def mass_balance(ctx: CheckContext) -> list[Finding]:
    ev = ctx.evidence
    tol_pct, _ = ctx.profile.tolerance("mass_balance_pct")
    tol = tol_pct / Decimal(100)
    dry = ev.dec("dry_mass_biochar")
    findings: list[Finding] = []
    log = ev.dec("production_log_mass")
    if dry is not None and log is not None and dry > 0 and abs(log - dry) / dry > tol:
        findings.append(make("MASS_BALANCE_MISMATCH", origin="production_log", expected_t=str(dry), found_t=str(log)))
    invoice = ev.dec("freight_invoice_mass")
    biochar_freight = sum(
        (Decimal(items["transport_freight_t"].value) for items in ev.groups("transport_freight_t", "transport_leg_kind").values()
         if items.get("transport_leg_kind") and items["transport_leg_kind"].value == "biochar" and "transport_freight_t" in items),
        Decimal(0),
    )
    reference = invoice if invoice is not None else (biochar_freight if biochar_freight > 0 else None)
    if dry is not None and reference is not None and dry > 0 and abs(reference - dry) / dry > tol:
        findings.append(make("MASS_BALANCE_MISMATCH", origin="freight", expected_t=str(dry), found_t=str(reference)))
    return findings


def provenance(ctx: CheckContext) -> list[Finding]:
    kinds = {i.provenance for i in ctx.evidence.items} | {i.provenance for i in ctx.facility_year.items}
    findings: list[Finding] = []
    if "synthetic" in kinds:
        findings.append(make("PROVENANCE_SYNTHETIC"))
    if "synthetic" in kinds and "measured" in kinds:
        findings.append(make("PROVENANCE_MIXED"))
    return findings


def run_all(ctx: CheckContext) -> tuple[str, list[Finding]]:
    derived, findings = facility_class(ctx)
    findings += required_evidence(ctx)
    findings += duplicates(ctx)
    findings += exclusion_rules(ctx)
    findings += plausibility(ctx)
    findings += moisture(ctx)
    findings += h_corg(ctx)
    findings += timing(ctx)
    findings += non_soil_and_additives(ctx, derived)
    findings += low_tech_methane_inputs(ctx, derived)
    findings += transport(ctx)
    findings += mass_balance(ctx)
    findings += provenance(ctx)
    return derived, findings
