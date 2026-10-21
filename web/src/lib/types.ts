/**
 * Shapes of the API responses the interface reads. The backend returns several of them as free-form objects, so the
 * generated OpenAPI types are loose; these are the fields the screens rely on, checked against real responses.
 */

export type EvidenceItem = {
  item_id: string;
  kind: string;
  value: string;
  unit: string;
  group: string | null;
  measured_at: string | null;
  /** owner, model (the extraction agent) or verifier. */
  source: string;
  /** measured, modeled or synthetic. */
  provenance: string;
  rel_uncertainty: string | null;
  document_ref: string | null;
  /** confirmed, pending_confirmation or rejected. */
  confirmation: string;
  span: { quote?: string; page?: number } | null;
};

export type Batch = {
  batch_id: string;
  project_id: string;
  facility_id: string;
  year: number;
  biochar_type: string;
  application_type: string;
  profile_id: string;
  parcel_key: string | null;
  cell_set: string[];
  product_batch_id: string | null;
  period_start: string;
  period_end: string;
  claimed_kg_co2e: number | null;
  state: string;
  created_at: string;
  updated_at: string;
  evidence: EvidenceItem[];
};

export type Finding = {
  code: string;
  severity: "critical" | "high" | "medium" | "low" | "info";
  params: Record<string, unknown>;
  source: string;
  blocks_calculation: boolean;
  blocks_verified: boolean;
  overridable: boolean;
};

export type Report = {
  report_id: string;
  evidence_hash: string;
  batch_id: string;
  status: string;
  /** human_review, return or reject. */
  recommendation: string;
  kg_co2e: { low: number; central: number; high: number } | null;
  issuable_kg: number | null;
  findings: Finding[];
  profile_id: string;
  profile_label: string;
  facility_class: string | null;
  blocks_calculation: boolean;
  blocks_verified: boolean;
  pending_items: number;
  narrative_en: string | null;
  grounding: { passed: boolean; numbers_checked: number; discrepancies: unknown[] } | null;
  /** Findings a verifier accepted with a reason, for this report. */
  overrides?: { code: string; actor_id: string; reason: string; created_at: string }[];
  /** The calculation record: steps, inputs, parameters used, transport legs and uncertainty. Free-form on the API. */
  calc?: Record<string, unknown>;
};

export type DocumentRow = {
  document_ref: string;
  filename: string;
  media_type: string;
  size: number;
  sha256: string;
  findings: Finding[];
};

export type Transition = { from: string; to: string; roles: string[]; reason_required: boolean };

export type Catalog = {
  findings: { code: string; severity: string; blocks_calculation: boolean; blocks_verified: boolean; overridable: boolean }[];
  states: string[];
  transitions: Transition[];
  permissions: Record<string, string[]>;
  errors: Record<string, number>;
  evidence_kinds: Record<string, { value_type: string; units: string[]; enum: string[]; multi: boolean; scope: string }>;
  terminal_states: string[];
  editable_states: string[];
};

export type LedgerRef = { topic_id: string; sequence: number; consensus_timestamp: string; tx_id?: string };

export type AuditEvent = {
  seq: number;
  ts: string;
  type: string;
  batch_id: string;
  payload_hash: string;
  prev_hash: string;
  provenance: string;
  hash: string;
  ledger_ref: LedgerRef | null;
};

export type VerifyResult = {
  chain_ok: boolean;
  first_broken_seq: number | null;
  reason: string | null;
  event_count: number;
  ledger_count: number;
  ledger_matches: boolean;
};

export type ProfileDoc = {
  profile_id: string;
  label: string;
  version: string;
  horizon_years: number;
  source?: { document?: string; retrieved?: string; note?: string };
  [key: string]: unknown;
};
