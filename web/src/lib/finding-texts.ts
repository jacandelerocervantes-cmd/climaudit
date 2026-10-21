import { msg } from "@/lib/i18n-core";

/**
 * Plain-language title and meaning for every finding code of the backend (`findings.CATALOG`). A test checks that every
 * code has an entry. Severity and blocking come from the backend, never from this file.
 */
export const FINDING_TEXTS: Record<string, { title: string; meaning: string }> = {
  DOCUMENT_HASH_MISMATCH: { title: msg("Document does not match its hash"), meaning: msg("A file changed after it was registered, so it cannot be trusted as evidence.") },
  FACTOR_WITHOUT_SOURCE: { title: msg("A factor has no source"), meaning: msg("A number used in the calculation has no source or version, so the calculation cannot rely on it.") },
  H_CORG_ABOVE_LIMIT: { title: msg("H to organic carbon ratio above the limit"), meaning: msg("The molar ratio is above the limit of the methodology, so this biochar is not eligible.") },
  PARCEL_CELL_OVERLAP: { title: msg("Parcel overlaps another batch"), meaning: msg("The parcel shares map cells with another batch in an overlapping period. A parcel can only be credited once.") },
  PERIOD_OVERLAP_DETECTED: { title: msg("Same parcel and period as another batch"), meaning: msg("Another batch has the same parcel key and an overlapping period. This is possible double counting.") },
  APPLICATION_TOO_LATE: { title: msg("Applied too long after production"), meaning: msg("The biochar was applied more than one year after it was produced, which the methodology does not allow.") },
  CALC_MISMATCH: { title: msg("Recalculation differs from the declared figure"), meaning: msg("Recomputing the result gave a different number than the one declared.") },
  CARBON_FRACTION_BELOW_50_NON_SOIL: { title: msg("Carbon content too low for non-soil use"), meaning: msg("Non-soil biochar needs at least 50 percent carbon by dry weight.") },
  EVIDENCE_MISSING: { title: msg("Required evidence is missing"), meaning: msg("The methodology needs an item that has not been provided.") },
  FACILITY_CLASS_INCONSISTENT: { title: msg("Facility class does not match its conditions"), meaning: msg("A facility declared as high technology is missing one of the four required conditions.") },
  FEEDSTOCK_IMPORTED: { title: msg("Feedstock comes from another country"), meaning: msg("The feedstock origin differs from the project country, which this profile does not accept.") },
  FEEDSTOCK_NOT_ELIGIBLE: { title: msg("Feedstock is not eligible"), meaning: msg("The feedstock is not purely biogenic waste biomass or fails an eligibility criterion.") },
  HIDDEN_TEXT_IN_DOCUMENT: { title: msg("Hidden text in a document"), meaning: msg("A document contains text a reader cannot see, such as white or tiny text. It was removed before any model read it.") },
  INSTRUCTION_IN_DOCUMENT: { title: msg("Instruction-like text in a document"), meaning: msg("A document contains text that looks addressed to an AI model. It stays visible and a verifier must review it.") },
  MASS_BALANCE_MISMATCH: { title: msg("Masses do not add up"), meaning: msg("The production log, the laboratory results and the freight records disagree by more than the tolerance.") },
  MOISTURE_NOT_DEDUCTED: { title: msg("Wet mass used where dry mass is required"), meaning: msg("The mass includes moisture, so it must be converted to dry mass before it is used.") },
  NARRATIVE_UNGROUNDED_NUMBER: { title: msg("A number in the report text is not in the evidence"), meaning: msg("The report text mentions a figure that does not match any computed value, so the text was withheld.") },
  NON_SOIL_FROM_LOW_TECH: { title: msg("Non-soil use from a low-technology facility"), meaning: msg("Non-soil applications require a high-technology production facility.") },
  UNIT_MISMATCH: { title: msg("Unexpected unit"), meaning: msg("A value uses a unit different from the one expected.") },
  VALUE_OUT_OF_RANGE: { title: msg("Value outside the plausible range"), meaning: msg("A value is outside the range the methodology or common sense allows.") },
  ADDITIVE_SHARE_ABOVE_LIMIT: { title: msg("Additive share above the limit"), meaning: msg("Mineral additives exceed 10 percent of the mass without a passing laboratory test.") },
  DATE_INCONSISTENT: { title: msg("Dates are inconsistent"), meaning: msg("Some dates fall outside the period or are in an impossible order.") },
  EVIDENCE_DUPLICATED: { title: msg("Same document used in two batches"), meaning: msg("A document with the same content is attached to another batch.") },
  LAND_COVER_MISMATCH: { title: msg("Land cover does not match the declared land type"), meaning: msg("A satellite land cover map shows something implausible at the application location. Advisory, from public data.") },
  METHODOLOGY_PARAMETER_UNVERIFIED: { title: msg("A methodology parameter is not fully verified"), meaning: msg("A value comes from a profile entry that was not independently confirmed against the source.") },
  METHODOLOGY_VERSION_OUTDATED: { title: msg("Methodology version is not current"), meaning: msg("A newer version of the methodology exists.") },
  MOISTURE_BASIS_UNSPECIFIED: { title: msg("Moisture basis not stated"), meaning: msg("A moisture percentage was given without saying whether it is on a wet or dry basis.") },
  PROVENANCE_MIXED: { title: msg("Measured and synthetic data mixed"), meaning: msg("The batch mixes data of different provenance without marking it.") },
  REGISTRY_METHODOLOGY_MISMATCH: { title: msg("Registry lists a different methodology"), meaning: msg("The external registry shows another methodology for this project. Advisory, from public data.") },
  REGISTRY_PROJECT_NOT_FOUND: { title: msg("Project not found in the registry index"), meaning: msg("The declared registry project id is not in the local registry index. Advisory, from public data.") },
  REGISTRY_VINTAGE_ALREADY_ISSUED: { title: msg("Credits already issued for this vintage"), meaning: msg("The registry already shows credits for this project and year. This may be double counting and needs a human decision.") },
  TRANSPORT_DISTANCE_IMPLAUSIBLE: { title: msg("Transport distance is too short for the locations"), meaning: msg("The declared return trip is shorter than the straight-line distance between the facility and the parcel allows. Advisory.") },
  TRANSPORT_MODE_NOT_ALLOWED: { title: msg("Transport mode not allowed"), meaning: msg("The transport mode breaks the rule for this distance.") },
  UNCERTAINTY_TOO_HIGH: { title: msg("Uncertainty is too high"), meaning: msg("The range between the low and high result is wider than allowed.") },
  BENFORD_ANOMALY: { title: msg("Unusual first-digit pattern"), meaning: msg("The first digits of a series of values deviate from the natural pattern. This is a screening signal, never proof of fabrication.") },
  METHODOLOGY_TEXT_AMBIGUOUS: { title: msg("The methodology text is ambiguous here"), meaning: msg("The methodology does not say exactly how to treat this case; the conservative reading was used.") },
  TRANSPORT_DISTANCE_AT_THRESHOLD: { title: msg("Transport distance is exactly at the threshold"), meaning: msg("The methodology does not say whether exactly 200 km counts, so it was counted as the conservative option.") },
  WEATHER_UNSUITABLE_FOR_APPLICATION: { title: msg("Weather on an application date looks unsuitable"), meaning: msg("The recorded weather that day suggests frozen ground or very heavy rain. Advisory heuristic, from public data.") },
  EXTERNAL_CHECK_UNAVAILABLE: { title: msg("A public-data check could not run"), meaning: msg("Data or a network was missing, so that advisory check was skipped. Nothing else changed.") },
  PROVENANCE_SYNTHETIC: { title: msg("Synthetic data"), meaning: msg("This batch uses synthetic demonstration data. It is not a real credit.") },
  REGISTRY_MANUAL_CHECK: { title: msg("Check this project in the registry yourself"), meaning: msg("This registry has no open data here. Look the project up on the registry website.") },
  REGISTRY_RECORD_FOUND: { title: msg("Registry record found"), meaning: msg("Context from the registry record for the declared project, shown for the verifier.") },
};

/** Shown for a code this file does not know yet; the backend severity and flags still apply. */
export const UNKNOWN_FINDING = {
  title: msg("Finding"),
  meaning: msg("No description is available for this finding code."),
};
