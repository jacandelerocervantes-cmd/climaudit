# SCHEMA — ClimAudit data, states and codes

Backend foundation before writing code (the build contract with routes, roles, closed evidence kinds, profile schema, calculation rules and fixtures is `BACKEND-SPEC.md`). Identifiers, fields and codes are **in English** (the backend is 100% in English; the per-language texts live in the frontend, see `LANGUAGES.md`). Reference methodology: Verra VM0044 v1.2, with its equations, defaults and applicability rules documented in `METHODOLOGY-VM0044.md` (verification status in `VERIFICATIONS.md`). Documentation only.

## 1. Conventions

- **Time:** UTC, ISO 8601 (`2026-10-16T12:00:00Z`). Periods as an interval `[start, end)`.
- **Quantities:** integers, no floats; fractional methodology parameters (for example `PR_de` 0.89, `FC` 0.77) are stored as decimal strings or scaled integers defined in the methodology profile, and never as binary floats in hashed JSON. CO2e in **kilograms** (`kg_co2e`, integer). One credit = 1 t = 1,000 kg; the HTS token uses 3 decimals to represent kg `[decision to confirm]`.
- **Identifiers:** UUID v7 or an equivalent sortable id; never personal data.
- **Mandatory provenance** on all data: `provenance` ∈ `measured | modeled | synthetic`.
- **Parcels:** only a generalized key (`parcel_key`, H3 or geohash of fixed, documented resolution). No fine coordinates in public data or on the chain.
- **Canonical JSON** for everything that is hashed: sorted keys, no spaces, UTF-8, no floats or local dates.
- **Versioning:** `schema_version` in every document; codes are part of the contract and do not change meaning.

## 2. Entities

### Project
| Field | Type | Notes |
|---|---|---|
| `project_id` | id | |
| `owner_account` | Hedera account | Project owner role |
| `methodology` | `{id, version}` | e.g. `VM0044`, `1.2` |
| `country` | ISO 3166-1 alpha-2 | |
| `created_at` | UTC | |
| `provenance` | enum | `synthetic` in the demo |

### Parcel
| Field | Type | Notes |
|---|---|---|
| `parcel_key` | string | Generalized canonical key (identifier of the parcel) |
| `cell_set` | list of H3 cell ids | Parcel footprint as H3 cells at one fixed resolution (for example 9 or 10, to be decided); stored only in the permissioned record, never in public HCS messages |
| `cell_set_hash` | SHA-256 | Hash of the sorted, canonical `cell_set`; the only footprint value published |
| `project_id` | id | |
| `area_m2` | integer | Optional, with uncertainty range |
| `land_use` | enum | Values to be defined with the methodology |

### Batch
| Field | Type | Notes |
|---|---|---|
| `batch_id` | id | |
| `project_id`, `parcel_key` | | Anti double-counting key |
| `period` | `{start, end}` | UTC, `[start, end)` |
| `claimed_kg_co2e` | integer | What the project owner declares |
| `verified_kg_co2e_low` / `_central` / `_high` | integer | Range after verification |
| `state` | enum | See section 3 |
| `evidence_hash` | SHA-256 | Of the package in canonical JSON |
| `report_hash` | SHA-256 | Of the verification report |
| `hcs_refs` | list | `{topic_id, sequence, consensus_timestamp}` |
| `idempotency_key` | (removed) | Replaced by the idempotency table in `BACKEND-SPEC.md` section 9 |
| `created_at`, `updated_at` | UTC | |

### EvidencePackage
| Field | Type | Notes |
|---|---|---|
| `package_id`, `batch_id` | id | |
| `items` | list of `EvidenceItem` | |
| `schema_version` | string | |

`EvidenceItem`: `{item_id, kind, value, unit, measured_at, source, provenance, document_ref}`. `kind` includes biomass mass, biochar mass, carbon content, energy, transport, soil application (the closed list is in `BACKEND-SPEC.md` section 5). `document_ref` is the hash of the original file (the file does not go on the chain).

### Finding
| Field | Type | Notes |
|---|---|---|
| `finding_id`, `batch_id` | id | |
| `code` | stable string | See section 5 |
| `severity` | `critical | high | medium | low | info` | |
| `params` | object | `{field, expected, found, unit, ...}` |
| `source` | `rule | model` | Deterministic rule or AI agent |

### VerificationReport
| Field | Type | Notes |
|---|---|---|
| `report_id`, `batch_id` | id | |
| `calc` | object | Inputs, formula, parameters with source and version, result |
| `uncertainty` | `{low, central, high, method}` | |
| `findings` | list of `finding_id` | |
| `narrative_en` | text | Report in English, verified against the evidence |
| `grounding` | `{passed, discrepancies}` | Result of `grounded-report-check` |
| `recommendation` | `human_review | return | reject` | Never "approve" |

### Credit and Retirement
- `Credit`: `{token_id, serial?, batch_id, kg_co2e, owner_account, issued_at}`.
- `Retirement`: `{retirement_id, token_id, kg_co2e, beneficiary_ref, reason_code, retired_at, hcs_ref}`. `beneficiary_ref` is an identifier, not a name.

### AuditEvent (HCS message)
`{seq, ts, type, batch_id, payload_hash, prev_hash, provenance, hash}`; serialization, hash input and literal test vectors are in `BACKEND-SPEC.md` section 11 (the skill `hcs-hash-anchoring` follows that spec). `provenance` is `synthetic` for every demo event. `type` ∈ `batch_submitted | evidence_attached | report_issued | state_changed | credit_issued | credit_transferred | credit_retired | correction`.

## 3. Batch states

```
DRAFT ──submit──► SUBMITTED ──start_review──► UNDER_REVIEW
                                                │
              ┌───────────────┬─────────────────┼─────────────────┐
              ▼               ▼                 ▼                 ▼
          NEEDS_INFO       REJECTED          VERIFIED          BLOCKED
         (returns to                            │          (factor without source,
          SUBMITTED)                         issue          calculation failure)
                                                ▼
                                             ISSUED ──retire──► PARTIALLY_RETIRED ──► RETIRED
```

| From | To | Who | Condition |
|---|---|---|---|
| DRAFT | SUBMITTED | project owner | Valid schema; no period overlap |
| SUBMITTED | UNDER_REVIEW | system | Evidence anchored in HCS |
| UNDER_REVIEW | VERIFIED | verifier role | Report with `grounding.passed` and no `critical` findings |
| UNDER_REVIEW | NEEDS_INFO | verifier role | Data missing; returns to SUBMITTED |
| UNDER_REVIEW | REJECTED | verifier role | Releases the period for the parcel |
| UNDER_REVIEW | BLOCKED | system | Calculation error or factor without source; returns to UNDER_REVIEW once resolved |
| VERIFIED | ISSUED | registry | Human or role confirmation; mints on HTS |
| ISSUED | PARTIALLY_RETIRED / RETIRED | holder | Sufficient balance |

Rules:
- No transition is executed by the AI. The agent produces findings and a recommendation; the transition requires an authorized role.
- **Anti double-counting:** two batches with the same `parcel_key` cannot have overlapping periods while they are in SUBMITTED, UNDER_REVIEW, NEEDS_INFO, BLOCKED, VERIFIED, ISSUED, PARTIALLY_RETIRED or RETIRED. DRAFT does not hold a period (it is not yet submitted); REJECTED releases.
- A correction never rewrites: a `correction` event is added.
- Every state-changing request carries an `Idempotency-Key` header; semantics in `BACKEND-SPEC.md` section 9. The closed transition table is in `BACKEND-SPEC.md` section 10 and supersedes the table above where they differ.

## 4. Error envelope (API)

```
{
  "error": {
    "code": "BATCH_PERIOD_OVERLAP",
    "params": { "parcel_key": "...", "conflicting_batch_id": "...", "overlap": ["start","end"] },
    "correlation_id": "..."
  }
}
```
The server does not return user-facing phrases. The per-language texts are frontend catalog keys with the same `code`. Technical details and traces go only to the server log, never to the client.

## 5. Code catalog

### 5.1 API errors
| Code | HTTP | Main parameters |
|---|---|---|
| `VALIDATION_FAILED` | 422 | `field`, `rule` |
| `UNIT_INVALID` | 422 | `field`, `unit`, `allowed` |
| `DATE_AMBIGUOUS` | 422 | `field`, `value` |
| `PERIOD_INVALID` | 422 | `start`, `end` |
| `FILE_UNSUPPORTED` | 415 | `media_type` |
| `FILE_CORRUPT` | 422 | `document_ref` |
| `BATCH_NOT_FOUND` | 404 | `batch_id` |
| `BATCH_PERIOD_OVERLAP` | 409 | `parcel_key`, `conflicting_batch_id`, `overlap`, `reason` (`exact_key` or `cell_overlap`) |
| `STATE_TRANSITION_NOT_ALLOWED` | 409 | `from`, `to` |
| `IDEMPOTENCY_CONFLICT` | 409 | `idempotency_key` |
| `ROLE_NOT_AUTHORIZED` | 403 | `required_role` |
| `AUTH_REQUIRED` | 401 | |
| `FACTOR_SOURCE_MISSING` | 422 | `parameter`, `methodology` |
| `CALC_FAILED` | 500 | `step` |
| `REPORT_WITHHELD_UNGROUNDED` | 422 | `discrepancy_count` |
| `LLM_UNAVAILABLE` | 503 | `retry_after` |
| `LEDGER_UNAVAILABLE` | 503 | `retry_after` |
| `LEDGER_REJECTED` | 502 | `status` |
| `GUARDIAN_POLICY_REJECTED` | 409 | `policy`, `rule` |
| `INSUFFICIENT_BALANCE` | 409 | `required`, `available` |
| `RATE_LIMITED` | 429 | `retry_after` |
| `INTERNAL_ERROR` | 500 | |

### 5.2 Findings
| Code | Typical severity | Meaning |
|---|---|---|
| `VALUE_OUT_OF_RANGE` | high | Value outside the plausible range |
| `UNIT_MISMATCH` | high | Unit differs from the expected one |
| `DATE_INCONSISTENT` | medium | Dates outside the period or in an impossible order |
| `PERIOD_OVERLAP_DETECTED` | critical | Exact-key overlap: another batch with the same `dedup_key` has an overlapping period (layer 1 of section 6) |
| `FACTOR_WITHOUT_SOURCE` | critical | Factor without source or version. The same condition raises the API error `FACTOR_SOURCE_MISSING` when it blocks a request; the finding is what the report shows |
| `CALC_MISMATCH` | high | The recalculated calculation differs from the declared one |
| `EVIDENCE_MISSING` | high | An item required by the methodology is missing |
| `EVIDENCE_DUPLICATED` | medium | Same document used in two batches |
| `PROVENANCE_MIXED` | medium | Measured and synthetic data mixed without a mark |
| `PROVENANCE_SYNTHETIC` | info | Batch with synthetic data |
| `UNCERTAINTY_TOO_HIGH` | medium | Uncertainty range greater than allowed |
| `DOCUMENT_HASH_MISMATCH` | critical | The file does not match its hash |
| `INSTRUCTION_IN_DOCUMENT` | high | Text addressed to a model inside a document |
| `NARRATIVE_UNGROUNDED_NUMBER` | high | Figure in the report that is not in the evidence |
| `METHODOLOGY_VERSION_OUTDATED` | medium | Methodology version not current |
| `METHODOLOGY_PARAMETER_UNVERIFIED` | medium | A parameter or limit comes from a profile entry marked `verified: false` |
| `METHODOLOGY_TEXT_AMBIGUOUS` | low | A profile rule rests on source wording that is ambiguous or inconsistent (for example VM0044 H:Corg "≤ 0.7" in the condition versus "less than 0.7" in the parameter table); the profile records the operator chosen |
| `H_CORG_ABOVE_LIMIT` | critical | Molar H/Corg of a batch violates the limit of the selected methodology profile. The profile stores `limit` and `operator` (`le` or `lt`), so VM0044 (≤ 0.7) accepts 0.70 and Isometric CRCF (< 0.5) rejects 0.50 |
| `TRANSPORT_DISTANCE_AT_THRESHOLD` | low | Round-trip distance exactly equal to the 200 km threshold, where the rule says "more than 200 km" |
| `MOISTURE_NOT_DEDUCTED` | high | Wet mass used where dry mass is required; the check converts with the declared `moisture_basis` (dry basis: `Q_dry = Q_wet / (1 + w/100)`; wet basis: `Q_dry = Q_wet * (1 - w/100)`) |
| `MOISTURE_BASIS_UNSPECIFIED` | medium | A moisture percentage was given without `moisture_basis` |
| `FEEDSTOCK_NOT_ELIGIBLE` | high | Feedstock is not purely biogenic waste biomass or fails its Table 1 criteria |
| `FEEDSTOCK_IMPORTED` | high | Feedstock origin country differs from the project country |
| `FACILITY_CLASS_INCONSISTENT` | high | Declared high-technology facility lacks one of the four required conditions |
| `APPLICATION_TOO_LATE` | high | Biochar applied more than one year after production |
| `NON_SOIL_FROM_LOW_TECH` | high | Non-soil application from a low-technology facility |
| `CARBON_FRACTION_BELOW_50_NON_SOIL` | high | Non-soil biochar with less than 50% carbon by dry weight |
| `ADDITIVE_SHARE_ABOVE_LIMIT` | medium | Mineral additives above 10% of mass without a passing laboratory test |
| `TRANSPORT_MODE_NOT_ALLOWED` | medium | Non-road transport rule or road-only rule beyond 200 km violated |
| `MASS_BALANCE_MISMATCH` | high | Production logs, laboratory results and freight/transport records disagree beyond tolerance |
| `TRANSPORT_DISTANCE_IMPLAUSIBLE` | medium | A declared biochar return-trip distance is shorter than twice the great-circle gap between the facility cell and the nearest application cell (advisory, section 20 of BACKEND-SPEC.md) |
| `LAND_COVER_MISMATCH` | medium | The ESA WorldCover class at an application cell is implausible for the declared land type (advisory) |
| `WEATHER_UNSUITABLE_FOR_APPLICATION` | low | An application date had a maximum air temperature below 0 C or at least 50 mm of rain (advisory heuristic) |
| `REGISTRY_PROJECT_NOT_FOUND` | medium | The declared external registry project id is not in the local registry index (advisory) |
| `REGISTRY_METHODOLOGY_MISMATCH` | medium | The registry lists a different methodology than the project's (advisory) |
| `REGISTRY_VINTAGE_ALREADY_ISSUED` | medium | The registry already shows credits issued for this project and vintage: possible double counting, human review (advisory) |
| `REGISTRY_RECORD_FOUND` | info | Context from the registry record (status, totals), with the dataset version |
| `REGISTRY_MANUAL_CHECK` | info | A Verra project: look it up manually in the Verra registry (no bulk data is used) |
| `EXTERNAL_CHECK_UNAVAILABLE` | info | An advisory check could not run (missing data, library or network); the reason is in the parameters |
| `BENFORD_ANOMALY` | low | First-digit distribution of a multi-batch series deviates from Benford's law (screening signal only, never proof of fraud) |
| `HIDDEN_TEXT_IN_DOCUMENT` | high | Zero-contrast, tiny or otherwise hidden text found in an uploaded document before ingestion |
| `PARCEL_CELL_OVERLAP` | critical | Spatial overlap: the H3 cell set of the batch intersects the cell set of another batch with an overlapping period, even when the `dedup_key` differs (layer 2 of section 6). The API returns `BATCH_PERIOD_OVERLAP` with `params.reason = "cell_overlap"` (layer 1 uses `"exact_key"`) |

### 5.3 Retirement reason codes
`reason_code` ∈ `voluntary_offset | corporate_reporting | research | other`. List to be reviewed with the methodology and the standard `[VERIFY]`.

## 6. Anti double-counting key
Two layers:
1. **Exact key:** `dedup_key = SHA-256(canonical({parcel_key, activity: "biochar_application", methodology_id}))`; batches with the same `dedup_key` must not have overlapping `[start, end)` periods.
2. **Spatial overlap:** hashing an exact polygon only detects identical parcels. The permissioned record therefore stores the parcel footprint as a set of H3 cells (fixed resolution) and the guard checks the intersection of cell sets for any two batches with overlapping periods. Only `cell_set_hash`, a coarse regional id and the period go to the public HCS topic; coordinates and cell lists stay in the permissioned record. Jittered or slightly shifted parcels are caught when their cells intersect; the cell resolution sets the tolerance and must be documented.

Declared limits: it protects within this registry, not against other external registries `[VERIFY scope]`; a cross-registry export in the style of the Climate Action Data Trust is a future option and its payload schema is `[VERIFY]`.

## 7. Tests that must exist before implementing
- Hash vectors with canonical JSON and expected hex.
- Total overlap, partial overlap, contiguous, other parcel, rejection that releases, resubmission with the same idempotency key.
- Every allowed transition and every forbidden one.
- One case for each error and finding code.
- Altered number in the report, changed unit and document with an embedded instruction.
- Document with hidden white-on-white text: the sanitizer must flag it and the agent must never see it.
- Planted errors in a synthetic dossier: moisture not deducted, H/Corg above the profile limit, and a production-versus-freight discrepancy; each must raise its finding and halt the calculation.
- Benford screen on a fabricated batch series versus a natural-looking one; narrow-range series must not be over-flagged. Critical value for first digits (8 degrees of freedom): 15.51 at alpha 0.05, 20.09 at alpha 0.01.
- Overlapping H3 cell sets, adjacent cell sets, and shifted parcels with and without intersection.
- Every number shown in the README and video reproduced by a unit test from stated synthetic inputs.

## 8. For your review
- Quantities in kg with 3 decimals on the token versus tonnes with decimals.
- H3 resolution for the cell set (9 or 10) and the tolerance it implies.
- List of evidence `kind` and `land_use` according to VM0044 taken from `METHODOLOGY-VM0044.md` sections 7.1 and 7.2.
- `BLOCKED` is kept as a state that still holds the period; confirm this choice against a flag on UNDER_REVIEW.
