# BACKEND SPEC — ClimAudit (build contract)

Closes the implementability gaps found by the second independent review. Complements `SCHEMA.md` (entities, states, codes), `METHODOLOGY-VM0044.md` (equations and defaults) and `ARCHITECTURE.md`. Where a choice had to be made it is marked **Decision** and listed in section 15 for the user to confirm or change. Documentation only; no code exists yet.

## 1. Components and system of record

| Component | Responsibility | State it owns |
|---|---|---|
| **API service** (FastAPI) | Routes, auth, validation, idempotency, state machine, audit log writer | Relational database (SQLite for the prototype, Postgres-compatible schema): projects, facilities, batches, evidence, findings, reports, idempotency records, role keys |
| **Calculation engine** (pure Python library, no I/O) | VM0044 equations, TOOL03/05/12 calculators, uncertainty bounds, mass-balance and rule checks | none |
| **Extraction agent** (read-only LLM + sanitizer) | Proposes evidence items from uploaded documents with page and character span | none; writes only `pending_confirmation` items through the API as a restricted service user |
| **Ledger port** | `anchor_hash`, `mint`, `retire`, `transfer`, `verify_chain` | Hedera testnet (HCS topic, HTS token) |
| **Frontend** | Later; not specified here | none |

**Decision 1 (system of record):** the API database is the system of record for batches, states and findings. Hedera holds the tamper-evident trail (HCS) and the credit token (HTS). The ledger port has two adapters behind one interface: `GuardianAdapter` (target: the ISSUED transition is executed through the Guardian REST API by the Standard Registry user, and Guardian's policy mints the HTS token) and `DirectHederaAdapter` (fallback: the registry service account mints HTS directly). The extraction agent and every non-registry role hold no ledger key. Guardian REST paths, ports and the VM0044 policy import steps are `[VERIFY]` in the Guardian 3.7.1 documentation before the adapter is written.

**Decision 2 (issued quantity):** a batch issues `verified_kg_co2e_low`, floored to whole kilograms, and never more than `claimed_kg_co2e` or the quantity utilized. One HTS base unit = 1 kg CO2e (token decimals 3 against tonnes); one credit = 1,000 units.

## 2. Roles and authentication

Roles: `owner` (project owner), `verifier`, `registry`, `holder` (credit holder or buyer), `admin` (operations), `system` (internal jobs), `extractor` (restricted service user for the agent).

Prototype authentication: static bearer API keys, one per role instance, kept in environment variables or a secrets file outside the repository; each key maps to `{actor_id, role, hedera_account_id?}`. No secrets in code or docs.

| Route group | owner | verifier | registry | holder | admin | system | extractor |
|---|---|---|---|---|---|---|---|
| create/edit own project, facility, batch (DRAFT) | yes | no | no | no | yes | no | no |
| upload document, attach evidence | yes | yes (add comments) | no | no | yes | no | propose only |
| confirm extracted evidence | yes (own) | yes | no | no | yes | no | no |
| start review, run verification | no | yes | no | no | yes | yes | no |
| NEEDS_INFO, REJECTED, VERIFIED | no | yes | no | no | yes | no | no |
| ISSUE | no | no | yes | no | no | no | no |
| transfer, retire | no | no | no | yes | no | no | no |
| BLOCKED, unblock | no | no | no | no | yes | yes | no |
| read own data / public audit trail | yes | all | all | own | all | all | no |

## 3. API routes

All bodies are JSON in English; errors use the envelope of `SCHEMA.md` section 4. Every state-changing route requires the header `Idempotency-Key` (section 9). Times are UTC ISO 8601.

| Method and path | Role | Purpose | Success | Main error codes |
|---|---|---|---|---|
| `POST /projects` | owner | Create project (methodology id and version) | 201 Project | `VALIDATION_FAILED` |
| `POST /projects/{id}/facilities` | owner | Register facility with the four high-technology conditions | 201 Facility | `VALIDATION_FAILED` |
| `POST /batches` | owner | Create DRAFT batch (facility, biochar type, application type, year, parcel footprint) | 201 Batch | `VALIDATION_FAILED`, `PERIOD_INVALID` |
| `PUT /batches/{id}` | owner | Edit while DRAFT or NEEDS_INFO | 200 Batch | `STATE_TRANSITION_NOT_ALLOWED` |
| `POST /batches/{id}/documents` | owner, verifier | Upload a document (stores bytes and `sha256`; runs sanitizer) | 201 `{document_ref, findings}` | `FILE_UNSUPPORTED`, `FILE_CORRUPT` |
| `POST /batches/{id}/evidence` | owner, extractor | Add evidence items | 201 items | `VALIDATION_FAILED`, `UNIT_INVALID` |
| `POST /batches/{id}/evidence/{item}/confirm` | owner, verifier | Confirm a `pending_confirmation` item | 200 item | `ROLE_NOT_AUTHORIZED` |
| `POST /batches/{id}/transitions` | per matrix | Body `{to, reason}`; performs a state transition | 200 Batch | `STATE_TRANSITION_NOT_ALLOWED`, `BATCH_PERIOD_OVERLAP`, `ROLE_NOT_AUTHORIZED` |
| `POST /batches/{id}/verification` | verifier, system | Run checks and calculation; creates a VerificationReport | 201 Report | `FACTOR_SOURCE_MISSING`, `CALC_FAILED`, `REPORT_WITHHELD_UNGROUNDED` |
| `GET /batches/{id}`, `GET /batches/{id}/report`, `GET /batches/{id}/findings` | per matrix | Read | 200 | `BATCH_NOT_FOUND` |
| `POST /batches/{id}/issue` | registry | ISSUED: mint credit through the ledger port | 200 Credit | `INSUFFICIENT_BALANCE`, `LEDGER_UNAVAILABLE`, `LEDGER_REJECTED`, `GUARDIAN_POLICY_REJECTED` |
| `POST /credits/{id}/transfer` | holder | Transfer units | 200 Credit | `INSUFFICIENT_BALANCE` |
| `POST /credits/{id}/retire` | holder | Retire units for a beneficiary reference | 200 Retirement | `INSUFFICIENT_BALANCE` |
| `GET /audit/{batch_id}` | all | Audit events with HCS references | 200 list | `BATCH_NOT_FOUND` |
| `GET /audit/verify` | all | Recompute the hash chain and compare with the mirror node; returns first broken `seq` | 200 | `LEDGER_UNAVAILABLE` |
| `GET /profiles`, `GET /profiles/{id}/{version}` | all | Methodology profiles | 200 | `BATCH_NOT_FOUND`-style 404 |
| `GET /health` | none | Liveness | 200 | none |

## 4. Entities added

The review found that `Batch` did not map to the equations. Added entities (fields in addition to those in `SCHEMA.md`):

**Facility** — `facility_id`, `project_id`, `country`, `process` (`pyrolysis|gasification|boiler`), `is_greenfield`, the four high-technology booleans (`pyrolysis_gas_combusted`, `heat_use_pct`, `pollution_controls`, `temperature_measured`), `kiln_type?`, `derived_class` (`high|low`, computed: high only if all four conditions hold, `heat_use_pct >= 70`).

**FacilityYear** — `facility_id`, `year`, `total_dry_mass_t` (`M_p,y`), facility-level emission inputs: `PE_DE`, `PE_DF`, `PE_CE`, `PE_CF` in tCO2e (each with provenance and the tool/version used), and for low-technology `Fe` and kiln type.

**Batch (redefined)** = one `(facility, biochar_type t, application_type k, year y)`: `facility_id`, `biochar_type` (feedstock class), `application_type` (`soil|non_soil`), `year`, `dry_mass_t` (`M_t,k,p,y`), `produced_at_first`, `produced_at_last`, `applied_at_first`, `applied_at_last`, `period` (see below), plus the SCHEMA fields. The Eq. 3/7 allocation is `M_t,k,p,y / M_p,y` taken from the Batch and FacilityYear.

**Period semantics (Decision 3):** `period` is the **application period** `[applied_at_first, applied_at_last + 1 day)`, since credits are earned for biochar utilized in the soil. Production dates are separate fields; the one-year rule compares each lot's `applied_at` with its `produced_at`. For **soil** batches `parcel_key` and the H3 `cell_set` are required and the double-counting guard applies. For **non-soil** batches there is no parcel: the prototype keys them by `product_batch_id` (exact-key layer only) and excludes them from the spatial layer; this limit is declared in the README.

## 5. Evidence kinds (closed list)

`value_type`: `decimal` (string), `int`, `date`, `enum`, `bool`, `text`, `ref`. Each item: `{item_id, kind, value, unit, measured_at, source, provenance, document_ref, confirmation}` with `confirmation` in `pending_confirmation|confirmed|rejected` (AI-extracted items start as `pending_confirmation` and cannot feed a calculation until confirmed; owner-entered items start `confirmed`).

| kind | value_type | unit | required when | used by |
|---|---|---|---|---|
| `dry_mass_biochar` | decimal | t | always | Eq. 2, 6, 3, 7, 9 |
| `wet_mass_biochar` | decimal | t | if dry mass derived | moisture check |
| `moisture_pct` | decimal | % | with wet mass | moisture check |
| `moisture_basis` | enum `dry|wet` | | with `moisture_pct` | moisture check |
| `organic_carbon_fraction` | decimal | fraction 0..1 (percent inputs converted on entry) | high-tech, or low-tech with lab | `FC` Eq. 2, 6 |
| `h_corg_molar` | decimal | ratio | soil use, per lot | eligibility |
| `pyrolysis_temp_c` | decimal | °C | high-tech; optional low-tech | `PR_de` class |
| `feedstock_category` | enum (Table 1 categories) | | always | feedstock eligibility |
| `feedstock_origin_country` | text ISO 3166 | | always | import rule |
| `feedstock_fate_evidence` | ref | | always | condition 4(b) |
| `production_date` | date | | per lot | one-year rule |
| `application_date` | date | | per lot | one-year rule, period |
| `application_type` | enum | | always | soil vs non-soil |
| `land_type` | enum (`cropland|grassland|urban_soil|forest|wetland|other`) | | soil | condition 10 |
| `application_method` | enum (`surface_mixed|subsurface`) | | soil | condition 10 |
| `lab_report` | ref | | always | IBI/EBC compliance |
| `lab_accredited` | bool | | with lab report | monitoring QA |
| `additive_pct` | decimal | % dry | if additives | condition 7 |
| `additive_lab_ok` | bool | | if additive_pct > 10 | condition 7 |
| `carbon_pct_dry` | decimal | % | non-soil | 50% rule |
| `product_lifetime_evidence` | ref | | non-soil | condition 12 |
| `electricity_mwh` | decimal | MWh | if grid electricity used | TOOL05 |
| `grid_ef_t_per_mwh` | decimal | tCO2/MWh | with electricity | TOOL05 |
| `tdl_fraction` | decimal | fraction | with electricity | TOOL05 |
| `fuel_quantity` / `fuel_ncv` / `fuel_ef_co2` / `fuel_carbon_fraction` / `fuel_density` | decimal | per tool | if fuel used | TOOL03 |
| `transport_mode` | enum `road|rail|ship|other` | | per leg | leakage |
| `transport_distance_km_return` | decimal | km | per leg | leakage, 200 km rule |
| `transport_freight_t` | decimal | t | per leg | TOOL12 |
| `vehicle_class` | enum `light|heavy` | | road legs | TOOL12 |
| `kiln_type`, `ch4_factor_t_per_t` | text, decimal | | low-tech | Eq. 9 |
| `gwp_ch4` | decimal | | low-tech | Eq. 9 (test-only default in fixtures) |
| `health_safety_program` | ref | | always | condition 3 |

Anything outside this list is rejected with `VALIDATION_FAILED`. Mass is stored in tonnes as a decimal string; kilograms only appear in the final `kg_co2e` integers.

## 6. Methodology profile file

One JSON file per `methodology_id@version`, loaded at startup and validated against this schema. No methodology constant exists in code.

```json
{
  "profile_id": "VM0044@1.2",
  "methodology_id": "VM0044",
  "version": "1.2",
  "horizon_years": 100,
  "source": {"document": "VM44_v1.2_clean.pdf", "retrieved": "2026-10-16"},
  "permanence": {
    "mode": "temperature_table",
    "table": [
      {"min_c": 600, "min_inclusive": false, "value": "0.89", "page": 22, "verified": true},
      {"min_c": 450, "max_c": 600, "value": "0.80", "page": 22, "verified": true},
      {"min_c": 350, "max_c": 450, "value": "0.65", "page": 22, "verified": true}
    ],
    "unknown_temperature_default": {"value": "0.56", "page": 25, "verified": true}
  },
  "limits": [
    {"field": "h_corg_molar", "operator": "le", "value": "0.7", "applies_to": "soil", "page": 13, "verified": true, "note": "parameter table says less than 0.7"}
  ],
  "defaults": {
    "organic_carbon_fraction_low_tech": {"wood_pyrolysis": "0.77", "...": "see METHODOLOGY-VM0044.md section 3"},
    "ch4_factor_traditional_kiln": {"value": "0.049", "unit": "tCH4/t", "verified": true}
  },
  "rules": {
    "max_days_production_to_application": 365,
    "transport_threshold_km": {"value": "200", "comparison": "strictly_greater"},
    "additive_max_pct": "10",
    "non_soil_min_carbon_pct": "50",
    "high_tech_min_heat_use_pct": "70"
  },
  "tools": {
    "TOOL05": {"default_ef": [{"value": "1.3", "when": "project_or_leakage"}, {"value": "0.4", "when": "low_hydro_baseline"}, {"value": "0.25", "when": "other_baseline"}], "tdl": {"project": "0.20", "baseline": "0.03"}},
    "TOOL12": {"ef_g_per_t_km": {"light": "245", "heavy": "129"}, "divisor": "1000000"}
  },
  "uncertainty": {"modeled_relative_uncertainty": {"value": "0.10", "verified": false, "note": "our parameter, not a VM0044 rule"}}
}
```

Each numeric entry carries `verified` and a `page`; a calculation that uses an entry with `verified: false` emits `METHODOLOGY_PARAMETER_UNVERIFIED`. The Woolf-regression profile (`WOOLF2021@alt`) uses `permanence.mode = "hcorg_linear"` with `{horizon, soil_temp_c, c, m}` rows and `F_perm` capped at 1 (our choice); it is selectable only by an explicit `profile_id` and its report is labeled "alternative permanence model, not VM0044".

## 7. Calculation rules

- **Arithmetic:** Python `decimal` with 28 significant digits, no binary floats anywhere in the engine. `44/12` is applied as exact rational via `Decimal(44)/Decimal(12)` once per equation. Rounding happens once, at the final `kg_co2e` integers: central rounded half-even; `low` floored; `high` ceiled.
- **Units:** `FC` internal unit is a fraction (VM0044 writes it in percent; entries in percent are divided by 100 on ingestion).
- **Moisture:** dry mass derives from wet mass with the declared basis (dry basis: `m_dry = m_wet / (1 + w/100)`; wet basis: `m_dry = m_wet * (1 - w/100)`).
- **Uncertainty (Decision 4):** the central value is the deterministic VM0044 result. Bounds are computed by re-running the same equations with each input moved to its adverse bound for `low` (and favorable for `high`): `x*(1 - u)` or `x*(1 + u)` according to the sign of its effect on removals. `u` for an input is its reported relative uncertainty if the evidence has one; for `modeled` inputs it is `modeled_relative_uncertainty` from the profile; for `measured` inputs without a reported uncertainty it is 0 and the report says so; for `synthetic` it is the modeled value. All inputs move at once, so the interval is conservative and **not a probability statement**. The report shows the central value, the bounds, and each contribution as a line item. The placeholder `0.10` is our unvalidated parameter and is shown as such.
- **Facility allocation:** `PE_PS,p,y = (PE_D + PE_P + PE_C) * M_t,k,p,y / M_p,y` where the sum comes from `FacilityYear`; a batch whose `M_p,y` is missing or smaller than its own mass raises `VALIDATION_FAILED`.
- **Transport legs:** `LE_ts` and `LE_tap` count only legs with `transport_distance_km_return` strictly greater than 200; equal to 200 raises `TRANSPORT_DISTANCE_AT_THRESHOLD` and the leg is not counted. TOOL12 Option B: `D * FR * EF / 1,000,000` tCO2 `[VERIFY-IMAGE divisor]`.
- **Transport mode check (Decision 5):** the source condition 6 is contradictory; the prototype raises `TRANSPORT_MODE_NOT_ALLOWED` only when a leg with distance strictly above 200 km uses a non-road mode. This reading is documented in the report.

## 8. Findings: blocking semantics

`blocks_calculation` stops the calculation (the report is created with status `incomplete` and no central value). `blocks_verified` prevents the VERIFIED transition. Verifiers cannot override a finding marked `no`; `admin` cannot either (an override requires a `correction` event by the verifier with a reason, only for the codes marked `yes`).

| Code | Severity (fixed) | blocks_calculation | blocks_verified | overridable by verifier |
|---|---|---|---|---|
| `PERIOD_OVERLAP_DETECTED`, `PARCEL_CELL_OVERLAP` | critical | yes | yes | no |
| `FACTOR_WITHOUT_SOURCE`, `DOCUMENT_HASH_MISMATCH` | critical | yes | yes | no |
| `H_CORG_ABOVE_LIMIT` | critical | yes | yes | no |
| `VALUE_OUT_OF_RANGE`, `UNIT_MISMATCH`, `CALC_MISMATCH`, `EVIDENCE_MISSING` | high | yes | yes | no |
| `MOISTURE_NOT_DEDUCTED`, `MASS_BALANCE_MISMATCH` | high | yes | yes | no |
| `FEEDSTOCK_NOT_ELIGIBLE`, `FEEDSTOCK_IMPORTED`, `FACILITY_CLASS_INCONSISTENT`, `APPLICATION_TOO_LATE`, `NON_SOIL_FROM_LOW_TECH`, `CARBON_FRACTION_BELOW_50_NON_SOIL` | high | no | yes | no |
| `HIDDEN_TEXT_IN_DOCUMENT`, `INSTRUCTION_IN_DOCUMENT` | high | no (text is excluded from the model) | yes until a verifier reviews | yes |
| `NARRATIVE_UNGROUNDED_NUMBER` | high | no | yes (report withheld) | no |
| `DATE_INCONSISTENT`, `EVIDENCE_DUPLICATED`, `PROVENANCE_MIXED`, `UNCERTAINTY_TOO_HIGH`, `ADDITIVE_SHARE_ABOVE_LIMIT`, `TRANSPORT_MODE_NOT_ALLOWED`, `MOISTURE_BASIS_UNSPECIFIED`, `METHODOLOGY_PARAMETER_UNVERIFIED`, `METHODOLOGY_VERSION_OUTDATED` | medium | no | no | yes |
| `BENFORD_ANOMALY`, `TRANSPORT_DISTANCE_AT_THRESHOLD`, `METHODOLOGY_TEXT_AMBIGUOUS` | low | no | no | yes |
| `PROVENANCE_SYNTHETIC` | info | no | no | n/a |

`PERIOD_OVERLAP_DETECTED` and `PARCEL_CELL_OVERLAP` appear at two points: a hard 409 (`BATCH_PERIOD_OVERLAP`) when a batch moves DRAFT to SUBMITTED, and as findings on a re-check at UNDER_REVIEW (for example after a competing batch changed state). Applicability checks without a dedicated code use `EVIDENCE_MISSING` with `params.kind` naming the missing item (wetland land, torrefaction/HTC process, non-greenfield facility, missing health-and-safety program, non-accredited laboratory, missing product-lifetime evidence, issued quantity above utilized). VM0044 section 7 additionality (investment analysis) is **out of scope** for the prototype and stated as such.

## 9. Idempotency

Header `Idempotency-Key` (client-generated UUID, required on state-changing routes). The server stores `(actor_id, method, path, key) -> {request_hash, response_status, response_body, created_at}` for 24 hours. Same key and same `request_hash`: return the stored response with no side effect. Same key and different `request_hash`: `IDEMPOTENCY_CONFLICT` (409). Ledger operations additionally carry a ledger-level key `sha256(batch_id|action|nonce)` stored before the call, so a retry after a timeout cannot double-mint. `Batch.idempotency_key` in `SCHEMA.md` is replaced by this table.

## 10. State machine (closed)

Terminal states: REJECTED, RETIRED. Allowed transitions (all others are `STATE_TRANSITION_NOT_ALLOWED`):

| From | To | Actor | Condition / effect |
|---|---|---|---|
| DRAFT | SUBMITTED | owner | Schema valid; overlap check (409 on conflict); documents anchored on HCS (`batch_submitted`, `evidence_attached`) |
| SUBMITTED | UNDER_REVIEW | system | After anchoring |
| UNDER_REVIEW | NEEDS_INFO | verifier | Reason required |
| NEEDS_INFO | SUBMITTED | owner | Re-runs overlap check and anchoring of changed evidence |
| UNDER_REVIEW | REJECTED | verifier | Reason required; releases the period |
| UNDER_REVIEW | BLOCKED | system or admin | Calculation failure or `FACTOR_WITHOUT_SOURCE`; holds the period |
| BLOCKED | UNDER_REVIEW | system or admin | After the cause is fixed; re-run verification |
| UNDER_REVIEW | VERIFIED | verifier | Latest report has no `blocks_verified` finding and `grounding.passed` |
| VERIFIED | NEEDS_INFO | verifier | Reason required |
| VERIFIED | REJECTED | verifier | Reason required |
| VERIFIED | ISSUED | registry | Mint through the ledger port; quantity per Decision 2 |
| ISSUED | PARTIALLY_RETIRED, RETIRED | holder | Retirement of part or all of the balance |
| PARTIALLY_RETIRED | RETIRED | holder | Remaining balance retired |

Transfers (`credit_transferred`) change the holder of units, not the batch state. DRAFT editing and deletion are allowed for the owner; a submitted batch is never deleted (a `correction` event is added instead). `report_issued` is written when a VerificationReport is created, and `evidence_attached` when evidence changes; neither is a state transition.

## 11. Canonical JSON and hash chain

- **Serialization (Decision 6):** JSON Canonicalization Scheme (RFC 8785) restricted to what the prototype uses: object keys sorted by Unicode code point, no whitespace, UTF-8 output, strings in NFC, numbers only as integers (anything fractional is a decimal string), no `null` (absent keys are omitted), arrays keep their order except where a field is defined as a set (`cell_set` is sorted ascending).
- **AuditEvent:** `{seq, ts, type, batch_id, payload_hash, prev_hash, provenance, hash}`. `hash = SHA-256_hex_lowercase(canonical({seq, ts, type, batch_id, payload_hash, prev_hash, provenance}))` (the `hash` field is excluded from its own input). `payload_hash` is the SHA-256 of the canonical form of the event's payload (for example the evidence package or report). `provenance` is `synthetic|measured|modeled` and equals `synthetic` for every demo event.
- **Genesis:** `prev_hash` is 64 zeros, per audit chain. One HCS topic per environment carries all batches; `seq` is the chain's own counter and the HCS consensus sequence number is stored next to it as `hcs_seq`. Messages carry only the event hash and minimal metadata (HCS message size limit `[VERIFY]`).
- **Public labels:** every HTS token and HCS message for demo data carries `"provenance": "synthetic"` and the string `SYNTHETIC_DEMO_DATA` in the memo/metadata. RULES.md claim 4 uses this marker.

Test vectors (computed with a reference script using sorted keys, compact separators and UTF-8):

1. Event 0 canonical input:
`{"batch_id":"b-001","payload_hash":"aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa","prev_hash":"0000000000000000000000000000000000000000000000000000000000000000","provenance":"synthetic","seq":0,"ts":"2026-10-16T12:00:00Z","type":"batch_submitted"}`
SHA-256: `a16f9526c8b6e3f76cc295a7eb043dfbd3fbd64464e5b87e549afe5fa7fe27b4`

2. Event 1 canonical input (`prev_hash` = hash of event 0, `seq` 1, `ts` `2026-10-16T12:05:00Z`, `type` `report_issued`, other fields as above):
`{"batch_id":"b-001","payload_hash":"aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa","prev_hash":"a16f9526c8b6e3f76cc295a7eb043dfbd3fbd64464e5b87e549afe5fa7fe27b4","provenance":"synthetic","seq":1,"ts":"2026-10-16T12:05:00Z","type":"report_issued"}`
SHA-256: `c496f195dcb6ad036eb6602521ced6c146c35c73280a9ed4f3eec17e51359768`

3. Parcel-period commitment (cell set sorted ascending):
`{"cell_set":["8928308280bffff","8928308280fffff"],"end":"2026-07-01T00:00:00Z","methodology_id":"VM0044","start":"2026-01-01T00:00:00Z"}`
SHA-256: `a5051c8aef6c526a9cf761d460133a9a0654dbe8a62b124140576dafb9a556a0`

The cell ids in vector 3 are illustrative strings, not a real parcel.

## 12. AI extraction contract

The extraction agent returns a JSON array validated by schema: `{kind, value, unit, document_ref, page, char_start, char_end, quote}`. The checker accepts an item only if `quote` appears verbatim in the document text at the stated span after whitespace normalization, and `value` appears inside `quote`. Accepted items are stored as `pending_confirmation` with provenance of the document (for example `measured` for a laboratory report), source `model`, and cannot enter a calculation until a human confirms them. Documents flagged `HIDDEN_TEXT_IN_DOCUMENT` have the flagged text removed before the agent sees them. The agent's tool set contains no write route except `POST /batches/{id}/evidence` as `extractor`.

## 13. Fixtures (synthetic dossiers)

Layout: `fixtures/<case>/package.json` (EvidencePackage plus Facility, FacilityYear, Batch), `fixtures/<case>/docs/` (generated PDFs and CSVs), `fixtures/<case>/expected.json` (`{findings: [codes], blocks_calculation, kg_co2e: {low, central, high}, state_after_verification}`). Every fixture file carries `"provenance": "synthetic"`.

Minimum cases: `happy_high_tech` (>600 °C, H:Corg 0.2, expected central 261,067 kg for 100 t at `FC` 0.80 with `PE` 0, see `METHODOLOGY-VM0044.md` section 6); `happy_low_tech_default_0.56`; `wet_as_dry` (dry-basis moisture not converted); `moisture_basis_missing`; `hcorg_0.69`, `hcorg_0.70`, `hcorg_0.71` (VM0044 profile accepts 0.69 and 0.70, rejects 0.71); `transport_150_vs_250_km`; `transport_exactly_200_km`; `application_after_one_year`; `non_soil_low_tech`; `overlap_exact_key`; `overlap_cell_set_shifted`; `contiguous_periods` (no conflict); `rejected_releases_period`; `hidden_text_injection` (PDF with white-on-white instruction); `benford_fabricated_series` and `benford_natural_series`; `mass_balance_freight_mismatch`; `unverified_parameter`. The hidden-text PDFs are generated by a script from the fixture manifest; the evaluation set size and block rate are reported from these cases only.

## 14. Consistency fixes decided here

- The H:Corg = 0.70 case is accepted by the VM0044 profile (`operator: le`) and raises `METHODOLOGY_TEXT_AMBIGUOUS` (low), not `METHODOLOGY_PARAMETER_UNVERIFIED`.
- `recommendation` values are `human_review | return | reject` everywhere, with underscores.
- A test-only `gwp_ch4` is fixed in fixtures (value chosen by the fixture author and labeled test-only); the real value comes from the latest VCS Standard `[VERIFY]`.

## 15. Decisions to confirm

1. System of record is the API database; Hedera holds trail and token; ledger port with Guardian and direct adapters.
2. Issue the `low` bound, floored to whole kg; token unit = 1 kg.
3. `period` = application period; non-soil batches are outside the spatial guard.
4. Uncertainty by adverse/favorable bound re-computation; placeholder `modeled_relative_uncertainty` 0.10 is unvalidated.
5. Transport-mode check only flags non-road modes above 200 km.
6. Canonical JSON = RFC 8785 subset, integers and decimal strings only.
7. Prototype authentication by static role API keys.

## For your review
- Decisions 1 to 7 above.
- Whether non-soil applications stay in scope or are dropped from the prototype.
- The Guardian adapter details, which need the Guardian 3.7.1 documentation read first.

## 16. Implementation status (backend/, 2026-10-16)

Built and covered by tests (146 passing at first build; 222 after the review fixes, section 17): configuration from environment, canonical JSON and hash chain with the three literal vectors, Decimal calculation of VM0044 Eq. 1-15 and the TOOL03/05/12 calculators, profile files with `extends`, closed evidence kinds, rule checks, Benford screen, PDF sanitizer, two-layer double-counting guard, finding catalog with blocking semantics, closed state machine, SQLite system of record, idempotency table, role matrix, HTTP API, fake ledger, extraction checker and an optional Claude extractor, fixture generator with 18 synthetic dossiers.

Differences from the sections above, decided while building (see `DECISIONS-LEDGER.md` D-110 onward):
- Added route `PUT /facilities/{facility_id}/years/{year}/evidence` for facility-year inputs (owner); it is refused once a batch of that facility and year has left DRAFT/NEEDS_INFO.
- `owner` may also transfer and retire the credits it holds; issued units belong to the project owner.
- Documents are uploaded as JSON with base64 content (`POST /batches/{id}/documents`).
- The DRAFT to SUBMITTED request also performs the system step SUBMITTED to UNDER_REVIEW and writes both state events.
- The Eq. 9 CH4 term is evaluated on the facility total and then allocated by mass share, which equals `Fe * GWP * M`.
- A Table 3 boundary temperature shared by two classes (450 C) goes to the lower class.
- Not implemented at the time of this status (2026-10-16): the `direct` and `guardian` ledger adapters, the frontend, RAG. The two adapters were added later (sections 18 and 19); the frontend and RAG are still not built.

## 17. Changes after the independent code review (2026-10-16)

Fixes for the defects proven by the review; reasons in `DECISIONS-LEDGER.md` D-130 to D-145. These supersede earlier sections where they differ.

- **Evidence kinds:** `production_date` and `application_date` are per-lot (grouped); `transport_declaration` (`legs_provided` or `none`) is required; the electricity and fuel kinds of section 5 were removed; `gwp_ch4` and `ch4_factor_t_per_t` need a `document_ref`.
- **Period:** derived on the server from the application dates; the declared period is ignored for the guard.
- **Spatial guard:** cell ids are normalized and validated as H3 cells of one allowed resolution.
- **Routes added or changed:** `POST /batches/{id}/findings/override` (verifier or admin, overridable codes only, audited); `PUT /facilities/{id}/years/{year}/evidence` replaces the year's inputs; `GET /audit/verify` needs a privileged role; `/health` returns only `{"status": "ok"}`; docs are served only when `CP_ENV=dev`.
- **Access:** holders may read the audit and the batch of credits they hold and see only their own balance; after submission only a verifier or admin confirms evidence; the alternative profile needs admin or verifier.
- **Issuance:** per-batch key, intent row (committed only when `service.issue()` runs outside the API request transaction; through the API recovery relies on the ledger-side lookup, see O-25), store lock, units never above the current claim, facility-year mass conservation checked at verification and at issuance.
- **Configuration added:** `CP_MAX_UPLOAD_BYTES`, `CP_FORCE_SYNTHETIC`.
- **Findings:** `MASS_BALANCE_MISMATCH` carries `origin` (`production_log`, `freight` or `facility_total`) instead of `source`.

## 18. Hedera direct adapter (2026-10-16)

`CP_LEDGER_MODE=direct` now selects `DirectHederaAdapter` (`backend/src/climaudit/ledger/hedera.py`) when `CP_HEDERA_OPERATOR_ID`, `CP_HEDERA_OPERATOR_KEY`, `CP_HCS_TOPIC_ID` and `CP_HTS_TOKEN_ID` are set; otherwise it fails closed and lists the missing variables. Testnet only. Reasons and open points: `DECISIONS-LEDGER.md` D-150 to D-155, O-18, O-19. Create the topic and token once with `backend/scripts/hedera_setup.py`. The Guardian adapter is described in section 19. Status of sections 1 and 16: the direct fallback adapter exists but has been exercised only against an in-memory gateway.

## 19. Guardian adapter (2026-10-17)

`CP_LEDGER_MODE=guardian` selects `GuardianAdapter` (`backend/src/climaudit/ledger/guardian.py`) when `CP_GUARDIAN_URL`, `CP_GUARDIAN_USERNAME`, `CP_GUARDIAN_PASSWORD` and `CP_GUARDIAN_POLICY_ID` are set; otherwise it fails closed and lists the missing variables. Decisions: `DECISIONS-LEDGER.md` D-160 to D-165, O-23, O-24. Verified live against Guardian 3.7.1 running from the official quickstart.

- Authentication: `POST /api/v1/accounts/login` returns `refreshToken`; `POST /api/v1/accounts/access-token` returns `accessToken`; calls send `Authorization: Bearer`. On 401/403 the adapter logs in once more and retries once.
- Audit anchoring: import `backend/guardian/climaudit_audit.policy` into Guardian (`POST /api/v1/policies/import/file`, raw ZIP, `Content-Type: binary/octet-stream`) and publish it (`PUT /api/v1/policies/{id}/publish` with `{"policyVersion": "1.0.0"}`). `anchor` posts `{"document": {eventHash, eventType, batchId, seq}}` to `/api/v1/policies/{id}/tag/form/blocks`, waits until the credential shows in `/tag/grid/blocks`, and takes the topic and consensus timestamp from it; the sequence number and transaction id come from the mirror node.
- `published_hashes` returns the event hashes of the grid in consensus order.
- Tokens: mint, transfer and retire are delegated to the direct Hedera token adapter when `CP_HEDERA_OPERATOR_ID`, `CP_HEDERA_OPERATOR_KEY` and `CP_HTS_TOKEN_ID` are set, otherwise they fail closed (`token_ledger_not_configured`).
- Optional variables: `CP_GUARDIAN_FORM_TAG` (default `form`), `CP_GUARDIAN_GRID_TAG` (default `grid`).
- Use a dedicated policy instance per environment: a credential not created by this backend makes the independent audit verifier report a mismatch.

## 20. Public-data cross-checks (2026-10-17)

An optional advisory layer (`backend/src/climaudit/external/`, enabled with `CP_EXTERNAL_CHECKS=1`). Decisions: `DECISIONS-LEDGER.md` D-170 to D-178. Research behind the choice of sources: `research/PUBLIC-DATA-LAYER.md`.

Principles: the checks only add findings for the human verifier; none blocks calculation or verification, none changes a number, and a check that cannot run adds an `EXTERNAL_CHECK_UNAVAILABLE` info finding instead of failing. They run before the verification transaction opens (they can take seconds) and are never part of the calculation.

| Check | Data | Inputs | Finding |
|---|---|---|---|
| Distance | Great-circle geometry (no network) | `Facility.cell`, `BatchRecord.cell_set`, biochar transport legs | `TRANSPORT_DISTANCE_IMPLAUSIBLE` when a declared return trip is shorter than twice the gap between the facility and the nearest application cell (road, rail and sea distances are never shorter than the great circle; the cell sizes are subtracted as location uncertainty) |
| Weather | Open-Meteo historical (ERA5), no key, CC BY 4.0, free for non-commercial use | application dates, first application cell | `WEATHER_UNSUITABLE_FOR_APPLICATION` on a day with maximum temperature below 0 C or precipitation of 50 mm or more |
| Land cover | ESA WorldCover v200 (2021), public AWS COG, CC BY 4.0, needs rasterio (`geo` extra) | application cells (at most 10), `land_type` evidence | `LAND_COVER_MISMATCH` when the observed class is implausible for the declared land type; without a declared type only open water and snow/ice are flagged |
| Registry | Berkeley Voluntary Registry Offsets Database (CC BY 4.0), local index | `Project.registry_project_id`, `BatchRecord.year` | `REGISTRY_PROJECT_NOT_FOUND`, `REGISTRY_METHODOLOGY_MISMATCH`, `REGISTRY_VINTAGE_ALREADY_ISSUED`, plus the info findings `REGISTRY_RECORD_FOUND` and `REGISTRY_MANUAL_CHECK` (Verra lookup link) |

Registry index: download the workbook from the Berkeley page and run `python scripts/build_registry_index.py <xlsx> data/registry_index.json` (extra `registry`), then set `CP_REGISTRY_INDEX_PATH`. The workbook and the index are not committed. Attribution is carried in the index metadata and must be shown with any use of the data.

New optional fields: `registry_project_id` on a project, `cell` (H3, resolution 7 to 10) on a facility.

Limits to state honestly: the datasets are snapshots with their own lag (the registry data is published roughly every two months); WorldCover is a 2021 10 m map sampled at a cell center, so one pixel can be unrepresentative; the weather thresholds are screening heuristics, not methodology rules; Verra has no bulk data in this layer.

## 21. Hardening after the second review (2026-10-17)

Decisions D-181 to D-185 in `DECISIONS-LEDGER.md`. (1) Issuance: `Store.checkpoint()` commits the mint intent before the ledger call and the recorded mint result right after it, so both survive a rollback of the request and a retry reuses the recorded result instead of asking the ledger again. (2) A buffering ASGI middleware refuses bodies above twice `CP_MAX_UPLOAD_BYTES` with HTTP 413, including chunked bodies. `content_base64` and the evidence `span` have schema limits and a batch holds at most `CP_MAX_DOCUMENTS_PER_BATCH` documents. (3) A transfer recipient must be an actor id of an `owner` or `holder` API key and match a safe character set. (4) `CP_ENV` defaults to `prod`; `/docs` and `/openapi.json` are served only when it is `dev`. (5) Every state-changing request deletes up to 200 expired idempotency rows. Remaining known gaps are listed in `submission/SECURITY-ASSESSMENT.md`.

## 22. Read routes for the user interface (2026-10-17)

Decisions D-187 to D-190. All need a valid role key and are read-only. `GET /me` returns the actor id and role. `GET /config` returns the ledger mode, network, HashScan base URL (null for the in-memory ledger), provenance mode and whether external checks are on. `GET /catalog` returns findings (code, severity, blocking flags, overridable), states, transitions per role with reason requirements, permissions, error codes with HTTP status and the evidence kinds. `GET /projects`, `/batches` and `/credits` return role-scoped lists (owners see their own, holders the credits they hold, verifier, registry, admin and system everything; extractor is refused), with `limit` from 1 to 500; batches carry a summary of the latest report. `GET /credits/{id}` and the credit lists also return the `retirements` (scoped like balances). `GET /batches/{id}/report` also returns the `overrides` accepted for that report (code, actor, reason, time). `GET /batches/{id}/documents` lists documents with their sanitizer findings and `GET /documents/{ref}/text` returns the sanitized visible text. `backend/scripts/export_openapi.py` writes the OpenAPI document used to generate the frontend types.
