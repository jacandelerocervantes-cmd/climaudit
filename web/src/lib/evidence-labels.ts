import { msg } from "@/lib/i18n-core";

/** Plain names for every evidence kind of the backend (`evidence.KINDS`); a test checks that none is missing. */
export const KIND_LABELS: Record<string, string> = {
  dry_mass_biochar: msg("Biochar mass, dry basis"),
  wet_mass_biochar: msg("Biochar mass, wet basis"),
  moisture_pct: msg("Moisture"),
  moisture_basis: msg("Moisture basis"),
  organic_carbon_fraction: msg("Organic carbon fraction"),
  h_corg_molar: msg("H to organic carbon ratio"),
  pyrolysis_temp_c: msg("Pyrolysis temperature"),
  soil_temp_c: msg("Soil temperature"),
  log_series_value: msg("Production log value"),
  feedstock_category: msg("Feedstock category"),
  feedstock_class: msg("Feedstock class"),
  feedstock_origin_country: msg("Feedstock origin country"),
  project_country: msg("Project country"),
  feedstock_fate_evidence: msg("Evidence of the feedstock's alternative fate"),
  production_date: msg("Production date"),
  application_date: msg("Application date"),
  transport_declaration: msg("Transport declaration"),
  application_type: msg("Application type"),
  land_type: msg("Land type"),
  application_method: msg("Application method"),
  lab_report: msg("Laboratory report"),
  lab_accredited: msg("Laboratory accredited"),
  additive_pct: msg("Additive share"),
  additive_lab_ok: msg("Additive laboratory check"),
  carbon_pct_dry: msg("Carbon content, dry basis"),
  product_lifetime_evidence: msg("Evidence of product lifetime"),
  health_safety_program: msg("Health and safety program"),
  process_type: msg("Process type"),
  kiln_type: msg("Kiln type"),
  ch4_factor_t_per_t: msg("Methane emission factor"),
  gwp_ch4: msg("Methane global warming potential"),
  production_log_mass: msg("Mass in the production log"),
  freight_invoice_mass: msg("Mass in the freight invoice"),
  facility_total_dry_mass: msg("Facility total dry mass for the year"),
  pe_pretreat_electricity_tco2e: msg("Pre-treatment electricity emissions"),
  pe_pretreat_fuel_tco2e: msg("Pre-treatment fuel emissions"),
  pe_auxiliary_electricity_tco2e: msg("Auxiliary electricity emissions"),
  pe_auxiliary_fuel_tco2e: msg("Auxiliary fuel emissions"),
  pe_processing_tco2e: msg("Processing emissions"),
  transport_mode: msg("Transport mode"),
  transport_leg_kind: msg("Transport leg kind"),
  transport_distance_km_return: msg("Return-trip distance"),
  transport_freight_t: msg("Freight mass"),
  vehicle_class: msg("Vehicle class"),
};

/** How a unit code is written next to a value. Unknown codes are shown as they are. */
export const UNIT_SYMBOLS: Record<string, string> = {
  t: "t",
  percent: "%",
  celsius: "°C",
  km: "km",
  tco2e: "tCO2e",
  t_ch4_per_t: "t CH4/t",
  fraction: "",
  ratio: "",
};

export function unitSymbol(unit: string): string {
  return unit in UNIT_SYMBOLS ? (UNIT_SYMBOLS[unit] as string) : unit;
}

/** `agricultural_residue` becomes `Agricultural residue`. Used for backend codes shown as data, not translated. */
export function humanize(code: string): string {
  const spaced = code.replace(/_/g, " ");
  return spaced.charAt(0).toUpperCase() + spaced.slice(1);
}
