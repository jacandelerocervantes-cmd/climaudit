import { msg, type TFunction } from "@/lib/i18n-core";
import type { ApiFailure } from "@/lib/client/api";

/**
 * Plain-language sentences for every error code of the backend (`errors.HTTP_STATUS`): what happened, then what to do.
 * A test checks that every backend code has an entry here, so a new code cannot ship without a sentence.
 */
export const ERROR_MESSAGES: Record<string, string> = {
  VALIDATION_FAILED: msg("Some values aren't valid. Check the highlighted fields and try again."),
  UNIT_INVALID: msg("That unit isn't allowed for this value. Pick one from the list."),
  DATE_AMBIGUOUS: msg("A date is unclear. Use the format year-month-day."),
  PERIOD_INVALID: msg("The period dates don't work together. Check the start and end."),
  FILE_UNSUPPORTED: msg("That file type isn't supported. Upload a PDF, text, CSV, or JSON file."),
  FILE_CORRUPT: msg("The file couldn't be read. Check it and upload it again."),
  BATCH_NOT_FOUND: msg("That batch doesn't exist, or you can't see it."),
  NOT_FOUND: msg("We couldn't find that."),
  BATCH_PERIOD_OVERLAP: msg("This parcel and period overlap another batch. A parcel can only be credited once."),
  STATE_TRANSITION_NOT_ALLOWED: msg("The batch can't move to that state right now."),
  IDEMPOTENCY_CONFLICT: msg("That request was already sent with different content. Start the action again."),
  IDEMPOTENCY_KEY_REQUIRED: msg("The request is missing its safety key. Reload and try again."),
  ROLE_NOT_AUTHORIZED: msg("Your current role can't do that. Switch role and try again."),
  AUTH_REQUIRED: msg("Choose a role to continue."),
  FACTOR_SOURCE_MISSING: msg("A calculation factor has no source, so the calculation stopped."),
  CALC_FAILED: msg("The calculation couldn't finish. Check the evidence and run it again."),
  REPORT_WITHHELD_UNGROUNDED: msg("The report was held back because a number didn't match the computed figures."),
  LLM_UNAVAILABLE: msg("The assistant isn't available right now. Try again in a moment."),
  LEDGER_UNAVAILABLE: msg("The ledger isn't reachable right now. Try again in a moment; your action won't be repeated."),
  LEDGER_REJECTED: msg("The ledger rejected the operation. Check the batch and try again."),
  GUARDIAN_POLICY_REJECTED: msg("The Guardian policy rejected this step."),
  INSUFFICIENT_BALANCE: msg("There aren't enough credit units for that."),
  RATE_LIMITED: msg("Too many requests. Wait a moment and try again."),
  INTERNAL_ERROR: msg("Something went wrong on our side. Try again."),
  // Raised by the interface itself when the ClimAudit API cannot be reached (not a backend code).
  SNAPSHOT_READ_ONLY: msg("This is a recorded run and cannot be changed. Run the app locally to try the actions."),
  API_UNREACHABLE: msg("ClimAudit's server isn't reachable. Check that it is running, then try again."),
};

/** More specific sentences for validation failures, chosen by the `rule` the backend reports. */
export const RULE_MESSAGES: Record<string, string> = {
  unknown_holder: msg("That recipient isn't a known holder. Check the name and try again."),
  different_non_empty_holder: msg("Choose a recipient other than yourself."),
  too_many_documents: msg("This batch has reached its limit of documents."),
  body_too_large: msg("That upload is too large."),
  required_for_transition: msg("This step needs a written reason."),
  required: msg("A required value is missing."),
  not_overridable: msg("That finding can't be accepted."),
  enum: msg("That value isn't one of the allowed choices."),
};

const GENERIC = msg("Something went wrong. Try again.");

export function errorMessage(failure: ApiFailure, t: TFunction): string {
  const rule = typeof failure.params.rule === "string" ? RULE_MESSAGES[failure.params.rule] : undefined;
  const base = t(failure.code === "VALIDATION_FAILED" && rule ? rule : (ERROR_MESSAGES[failure.code] ?? GENERIC));
  const required = failure.params.required_role;
  if (failure.code === "ROLE_NOT_AUTHORIZED" && Array.isArray(required) && required.length > 0) {
    return `${base} ${t("Needed: {roles}.", { roles: required.join(", ") })}`;
  }
  if (failure.code === "BATCH_PERIOD_OVERLAP" && typeof failure.params.conflicting_batch_id === "string") {
    return `${base} ${t("Conflicting batch: {id}.", { id: failure.params.conflicting_batch_id })}`;
  }
  return base;
}

export const STATE_LABELS: Record<string, string> = {
  DRAFT: msg("Draft"),
  SUBMITTED: msg("Submitted"),
  UNDER_REVIEW: msg("Under review"),
  NEEDS_INFO: msg("Needs info"),
  REJECTED: msg("Rejected"),
  BLOCKED: msg("Blocked"),
  VERIFIED: msg("Verified"),
  ISSUED: msg("Issued"),
  PARTIALLY_RETIRED: msg("Partly retired"),
  RETIRED: msg("Retired"),
};

/** Every state has a glyph and a tone, so a state is never conveyed by colour alone. */
export const STATE_STYLE: Record<string, { glyph: string; tone: "neutral" | "info" | "ok" | "warn" | "bad" }> = {
  DRAFT: { glyph: "○", tone: "neutral" },
  SUBMITTED: { glyph: "◔", tone: "info" },
  UNDER_REVIEW: { glyph: "◑", tone: "info" },
  NEEDS_INFO: { glyph: "?", tone: "warn" },
  REJECTED: { glyph: "✕", tone: "bad" },
  BLOCKED: { glyph: "■", tone: "bad" },
  VERIFIED: { glyph: "✓", tone: "ok" },
  ISSUED: { glyph: "●", tone: "ok" },
  PARTIALLY_RETIRED: { glyph: "◐", tone: "ok" },
  RETIRED: { glyph: "◉", tone: "neutral" },
};

export const PROVENANCE_LABELS: Record<string, string> = {
  measured: msg("Measured"),
  modeled: msg("Modeled"),
  synthetic: msg("Synthetic"),
};

export const ROLE_LABELS: Record<string, string> = {
  owner: msg("Project owner"),
  verifier: msg("Verifier"),
  registry: msg("Registry"),
  holder: msg("Credit holder"),
  admin: msg("Admin"),
};

export const RECOMMENDATION_LABELS: Record<string, string> = {
  human_review: msg("Recommended: send for human review"),
  return: msg("Recommended: return to the owner"),
  reject: msg("Recommended: reject"),
};

export const SEVERITY_LABELS: Record<string, string> = {
  critical: msg("Critical"),
  high: msg("High"),
  medium: msg("Medium"),
  low: msg("Low"),
  info: msg("Info"),
};

export const CONFIRMATION_LABELS: Record<string, string> = {
  confirmed: msg("Confirmed"),
  pending_confirmation: msg("Waiting for confirmation"),
  rejected: msg("Rejected by a person"),
};

export const SOURCE_LABELS: Record<string, string> = {
  owner: msg("Entered by the owner"),
  model: msg("Proposed by the AI assistant"),
  verifier: msg("Entered by the verifier"),
  extractor: msg("Proposed by the AI assistant"),
};

export const APPLICATION_LABELS: Record<string, string> = {
  soil: msg("Soil application"),
  non_soil: msg("Non-soil application"),
};
