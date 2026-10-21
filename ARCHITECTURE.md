# ARCHITECTURE — ClimAudit (from A to Z)

Complements `PLAN.md`, `DEPLOY.md` and `RULES.md`. Everything marked `[VERIFY]` must be checked against the official source before it is asserted. Documentation only: there is no code yet.

## 0. Guiding principle

> The AI proposes and explains; the code calculates and checks; the human or the verifier role decides; the chain records.

This comes from `RULES.md` and from the AquaLedger pattern ("verified data, not invented").

## 1. Overview

```
Project owner ──► Frontend (Next.js, multi-language)
                          │
                          ▼
                    API (FastAPI) ── Uniform error handling
                          │
   ┌──────────────┬───────┴────────┬───────────────────┐
   ▼              ▼                ▼                   ▼
Ingestion + QC  Math engine       AI layer          Ledger layer
(validation)    (CO2e, uncert.)   (LLM + RAG)       (Hedera HTS/HCS + Guardian)
   │              │                │                   │
   └──────────────┴────► Figure verification ◄─────────┘
                          (grounded-report-check)
                                  │
                           Interpretation (no verdict)
                                  │
                   Human / verifier role decides
```

## 2. Multi-language (i18n)

Reuses the idea of `src/oah/i18n` from AquaLedger.

- **Languages:** the official languages of the G20 countries plus China, by quality tiers (tier 1: en, es, zh-Hans, hi, ar, fr, pt, ru, de, ja, ko, id, it, tr; then EU, India and South Africa). Detail, adaptations (RTL, CJK, per-language lengths) and tests in `LANGUAGES.md`.
- **Design (user decision):** the backend is 100% in English and returns structured data with stable finding and error codes plus parameters. The frontend turns them into text with per-language catalogs. The narrative report is verified in English; its translation is optional, on demand and labeled as machine-translated. The messages in the error table of section 3 are catalog keys, not server phrases.
- **Interface:** message files per language (stable keys), date, number and unit formats according to the locale; storage always in UTC and SI units.
- **AI-generated content:** the narrative report is generated over structured data and written in English, and verified in English. An optional on-demand machine translation sits outside the evidence path and is labeled as such; **figures are not translated, they are formatted**.
- **Technical terms:** controlled glossary (CO2e, baseline, additionality, retirement, vintage) with fixed translation, so the AI does not vary the terminology.
- **Tests:** the same case in each language must give the same figures; machine translations are marked as unreviewed until someone reviews them.
- **Risk:** a translation can change the legal meaning of a sentence; the "not an opinion" disclaimers are written by hand in each language.

## 3. Error handling

Principle: **fail closed and explainably**. A doubtful batch is held, not approved by default.

| Layer | Typical error | Handling |
|---|---|---|
| Input | Missing field, invalid unit, ambiguous date | Schema validation; 422 response with field, reason and example |
| Ingestion | Corrupt file, unsupported format | Rejection with code, no silent partial processing |
| QC | Out-of-range value, duplicate | Finding with severity; does not stop everything unless critical |
| Calculation | Factor without source, division by zero, NaN | Typed exception; the batch is left "blocked: factor without source" |
| AI/LLM | Timeout, invalid response, unsupported figure | Limited retry; if figure verification fails, the report is **withheld** |
| Chain | Insufficient funds, saturated network, rejected message | Queue with retries and idempotency; the status shows "pending on chain" |
| Guardian | Policy rejects the transition | The policy reason is shown; no blind retry |
| Security | Injection attempt, access without role | Rejection, audit log with digest, no echo of the content |

Conventions:
- Single error structure: `stable code`, `params`, `correlation id` (the technical detail goes to server logs only; the text shown to the person is the frontend catalog entry for the code).
- The backend returns only `code` and `parameters` (in English); the per-language messages live in the frontend.
- **Idempotency** on every on-chain operation (key per batch and action) so that a retry does not issue twice.
- Explicit batch states exactly as in `SCHEMA.md` section 3 (DRAFT, SUBMITTED, UNDER_REVIEW, NEEDS_INFO, REJECTED, VERIFIED, BLOCKED, ISSUED, PARTIALLY_RETIRED, RETIRED) with defined allowed transitions.
- Traces or keys are never shown to the user.

## 4. Interpreting results

What is said and what is **not** said (environmental rule: an index does not issue an opinion).

- **Delivered:** value, uncertainty range, assumptions, sources, measured/modeled/synthetic label, comparison with the reference value with its citation.
- **Not delivered:** "this credit is valid/fraudulent", "this project meets the standard". The wording is "evidence consistent with..." and "recommendation: move to human review".
- **Reading levels:** (a) plain-language summary, (b) technical detail with formulas, (c) audit with hashes and links to the explorer.
- **Explainability:** each finding points to the field and the rule that originated it; the confidence score is broken down into its components (not an opaque number).
- **Visible uncertainty:** bars or ranges, never a point figure alone.
- **Human-reviewed interpretation templates** per language; the AI fills them with verified data and does not invent opinion phrases.

## 5. Mathematics and statistics

Every number comes from deterministic code, never from the LLM.

- **Tonnes CO2e:** activity × factor, with a cited factor (source, version, date) `[VERIFY applicable methodology: Verra, Gold Standard or other]`. For biochar and soil the calculation depends on the methodology; it is not invented.
- **Uncertainty:** error propagation (analytical method or Monte Carlo) and reporting as an interval; optional, declared conservative discount.
- **Anomaly detection:** plausibility rules plus simple statistics (robust z-score with median/MAD, range checks) on measurements and time series.
- **Conformal prediction / intervals:** reuse the idea of `src/oah/uncertainty` and `scripts/eval_conformal.py` for intervals with measurable coverage `[VERIFY applicability to small data]`.
- **Period overlap:** interval algebra [start, end) in UTC (see skill `double-counting-guard`).
- **Geospatial:** geohash/H3 with documented resolution; parcel area and overlap with declared tolerance.
- **Hashes and signatures:** SHA-256 with canonical JSON; optional Ed25519 signature (see `hcs-hash-anchoring`).
- **Property tests:** properties such as "summing batches does not change the total", "reordering does not change the head hash" and fixed test vectors.
- **Small data:** with little real data, no statistical performance is claimed; a labeled example is shown.

## 6. Artificial intelligence

### 6.1 What the AI does and does not do
| Does | Does not do |
|---|---|
| Read evidence documents and extract structured fields | Calculate tonnes or approve batches |
| Detect inconsistencies and propose them as findings | Issue credits or sign transactions |
| Write the report and the explanation in English (translation is optional, on demand, outside the evidence path) | Invent factors, citations or standards |
| Answer questions about the batch with read-only tools | Execute on-chain actions by itself |

### 6.2 Agent with tools (AquaLedger pattern)
- LLM (Claude API) with **read-only tools**: query evidence, run calculations, query the mirror node, search the regulatory base.
- **Structured output** (JSON schema) for findings and extraction; free text only in the final report.
- **Figure verification** before showing anything: numbers and units must match the tool results; links, markup or leaked instructions are rejected.
- **Isolation of untrusted content:** uploaded documents go in a block separate from the system prompt; they are treated as data.
- **Audit log:** digests and verdicts only, not the text.
- **Cost and latency:** result cache by evidence hash, tool limit per request, smaller model for extraction and a larger one for the report `[VERIFY current models and prices]`.

### 6.3 Evaluation (without this there are no claims)
- Case set: correct batches, with an altered figure, with a changed unit, with an overlapping period, with instruction injection.
- Metrics: rate of supported figures, findings detected, false positives, stability across runs.
- Every number that appears in the video comes from these saved evaluations.

### 6.4 Defenses for untrusted documents (from the research report)

Indirect prompt injection is the top risk for LLM applications that read third-party files (OWASP LLM01:2025). Guardrail classifiers alone are not enough (Hackett et al., arXiv:2504.11168 report evasion of up to 100% in some instances against six detectors). Controls, all deterministic:
1. **Pre-ingestion sanitizer:** strip hidden layers and metadata from PDFs, flag zero-contrast, tiny or off-page text (finding `HIDDEN_TEXT_IN_DOCUMENT`), and never pass flagged text to the model.
2. **Privilege separation:** the agent is read-only and holds no keys or tokens for Guardian `mintDocumentBlock` or any state-changing endpoint.
3. **Data spotlighting and schema validation:** untrusted chunks are wrapped in unambiguous delimiters; model output must validate against a JSON schema (value, unit, document id, page, verbatim character span).
4. **Independent numeric checker and human sign-off:** every extracted number must appear verbatim in the cited span; consequential actions need a human verifier.
5. **Measured, not claimed:** an injection test set (poisoned PDFs) with its size and block rate reported; any "blocked X%" claim comes from that set only.

### 6.5 Deterministic checks on the evidence

- **Mass balance across documents:** dry mass from wet mass using the moisture basis declared with the value (VM0044 defines moisture on a dry basis, `w = m_water / m_dry`, so `Q_dry = Q_wet / (1 + w/100)`; for a wet-basis value, `Q_dry = Q_wet * (1 - w/100)`; see `METHODOLOGY-VM0044.md` 7.1); production logs versus laboratory results versus freight records within a stated tolerance (findings `MOISTURE_NOT_DEDUCTED`, `MASS_BALANCE_MISMATCH`).
- **Physical limits per methodology profile:** H/Corg and similar limits are read from a data file per `methodology_id` + `version` with `source` and `verified` flags, never hard-coded (see `VERIFICATIONS.md` 4e). A batch checked against an unverified profile raises `METHODOLOGY_PARAMETER_UNVERIFIED`.
- **Benford screen:** first-digit chi-square and mean absolute deviation across multi-batch series, as a screening flag for manual review. It applies to data spanning several orders of magnitude, so a narrow range (one reactor, similar batch weights) must not be over-flagged; it is never proof of fabrication.

### 6.6 Provenance-weighted uncertainty

- Every input carries `measured | modeled | synthetic`. Measured inputs use their laboratory or sensor uncertainty; modeled inputs (for example regional soil temperature instead of a sensor) receive an explicit, parameterized conservative discount shown as a separate line item.
- Discount rule options to decide: a minus-one-standard-deviation rule (as Isometric reportedly does for its protocols `[VERIFY against the Isometric documents]`) and/or the lower bound of a split-conformal interval. The confidence level (for example alpha 0.10 versus the 15.87th percentile for -1 sigma) is fixed explicitly and displayed.
- Persistence depends on the **methodology profile**. The Verra VM0044 v1.2 profile uses the Table 3 defaults by pyrolysis temperature (0.89 above 600 °C, 0.80 for 450-600 °C, 0.65 for 350-450 °C, 0.56 if unknown; 100-year horizon) and the eligibility limit H:Corg ≤ 0.7 (see `VERIFICATIONS.md` 4h). A separate, clearly labeled alternative profile uses the Woolf et al. (2021) linear model `F_perm = c + m * (H/Corg)` with coefficients for the chosen horizon and soil temperature (4d), `F_perm` capped at 1 as our documented choice; its regressions explain only 7-33% of variance (R² of the rows read in `VERIFICATIONS.md` 4d), so the interval matters more than the point value. The two are never mixed or both called "VM0044".
- Mapping to Guardian: the Missing / Default / Suggested / Not-null value statuses of Guardian's Formulas view are used as a design analogy for the three provenance tiers, not as an equivalence `[VERIFY in the Guardian 3.7.x docs]`.

## 7. RAG (regulatory and methodological base)

Measured guidance from the research report (Climate Finance Bench, arXiv:2505.22752, a preprint on corporate sustainability reports, not on carbon methodologies): adding BM25 to dense retrieval and then a cross-encoder reranker raised the best configuration from 54.8% to 62.1% (figures from the preprint, not independently checked `[VERIFY]`), with retrieval named as the main bottleneck, and 25-30% of answers still wrong. Consequences: hybrid retrieval (dense + BM25 + reranker) with strict metadata pre-filtering (`methodology_id`, `version`, `effective_date`), exact-match lexical search for identifiers such as VM0044 or H/Corg, and no decision made on retrieval alone. A 75% dense / 25% BM25 weighting is a design choice to tune, not a tested value.

Useful if there is a real corpus; if not, it is not forced.

- **What to index:** carbon methodologies, monitoring guides, Guardian and hackathon rules, glossary. Only documents whose license allows their use.
- **Pipeline:** load with metadata (source, version, date, license) → chunking by sections → embeddings → hybrid search (vector + keyword) → reranking → answer **with mandatory citation**.
- **Rules:** no citation, no claim; if there is no relevant fragment, "not found" and `[VERIFY]`. Limits and factors are loaded as **data with source**, not summarized from memory.
- **Language:** queries in one language can retrieve documents in another; the language of the source is indicated.
- **Evaluation:** questions with a known answer, measure whether the citation really contains the claim.
- Reuse the approach of the skill `rag-implementacion` and `rag-normativa-agro` from 00_plataforma-ia.
- **Pending decision:** vector store (lightweight local for the demo) `[VERIFY]`.

## 8. Fine-tuning (LoRA / QLoRA) — an honest decision

**Recommendation: do not train for the submission.**

Reasons:
- There is not enough labeled corpus of real carbon batches; with synthetic data you get a model that learns the template, not the phenomenon.
- The risk of claiming performance that does not exist outweighs the benefit.
- The tasks (extraction, report, explanation) are well covered by an LLM with schema, tools and RAG.
- Judges evaluate impact and execution, not the size of the training.

**User decision:** LoRA is not trained now, but the groundwork is **left prepared** to implement it later. The groundwork consists of:
- Swappable model interface (LLM provider behind an interface) so the base model can be replaced by a fine-tuned one.
- Versioned dataset schema (input, expected output, language, measured/modeled/synthetic label, license, source) and provenance record.
- Record of each agent run (digests, no text) and of human corrections, to later turn them into fine-tuning data with consent `[VERIFY]`.
- Verifier-review log in a fixed, signed JSONL schema, one record per review: `document_chunk`, `candidate_extraction_json`, `checker_flags`, `vvb_approved_ground_truth` (the corrected value approved by the human verifier), plus ids, schema version and provenance label. In the demo these records are synthetic and labeled so. The expert-review pattern is the one described for SSKG Hub (arXiv:2603.00669, a preprint).
- Fixed evaluation set and metrics defined before training (supported figures, findings, false positives, translation quality per language).
- Anonymization and licensing rules for the fine-tuning data.
- Model registry with version and comparison against the base model; acceptance criterion written in advance.
- Candidates to fine-tune once there is data: extraction of fields from documents and translation of carbon terms in low-resource languages.
None of this is presented as trained or measured in the submission.

When it would be worthwhile (future work, declared as such): a small local model for extracting fields from documents, with LoRA on real, anonymized and licensed data, evaluated against the base LLM. It is documented as a scaling path, not as work done.

## 9. Other things worth implementing

| Topic | What | Priority |
|---|---|---|
| Audit log | Chained hash + anchor in HCS | High |
| Roles and permissions | Project owner, verifier, registry, buyer; least privilege | High |
| Anti double counting | Canonical key and overlaps | High |
| Provenance labels | Measured / modeled / synthetic on all data | High |
| Privacy | Generalized parcels; no personal data on chain | High |
| Credit retirement | Traceable event with beneficiary | High |
| Tests | Unit, property, negative-case, integration with testnet | High |
| Observability | Structured logs, metrics, correlation id | Medium |
| Rate limit and quotas | Protection of the API and of LLM spend | Medium |
| Accessibility | Contrast, keyboard, screen readers | Medium |
| Exports | Verifiable PDF/JSON report, link to HashScan | Medium |
| IoT / sensors | Simulated and labeled as synthetic for the demo | Low |
| Oracles and satellite data | External context (climate, NDVI) labeled as modeled | Low |
| Marketplace | Only minimal buyer-retirement flow | Low |
| Zero-knowledge proofs | Out of scope; mention only as future work | Out |

## 10. Security

- Keys in environment variables; separate test accounts per role.
- The LLM never signs or executes transactions; confirmation is by a human or a role.
- Injection defense: separate blocks, schema-validated output, no execution of document content.
- Dependencies pinned with hashes, as in AquaLedger.
- Tool guards (hooks) to block destructive commands and filter secrets, reusing `hooks/` from AquaLedger.
- Final review with the `security-engineer` agent from dev-ia.

## 11. Data and labels

| Type | Source | Label | Use |
|---|---|---|---|
| Measured | Real and with verified license | `measured` | Demonstration with source |
| Modeled | Climate, satellite, factors | `modeled` | Context, never mixed without a mark |
| Synthetic | Generated for the demo | `synthetic` | Example cases, outside any "official registry" |

The main demo will use clearly labeled synthetic data unless usable real data is obtained `[VERIFY]`.

## 12. Testing and quality

- Negative cases before happy ones: altered figure, overlapping period, injection, factor without source.
- Fixed hash vectors reproducible by another implementation.
- Contract tests with the Hedera testnet and network-failure simulation.
- Measurement of figure verification with the evaluation set.
- Document formulas and assumptions (like `docs/math_registry.md` in AquaLedger).

## 13. Suggested implementation order (when code is authorized)

1. Data schema, batch states and errors (no AI).
2. Mathematics engine and deterministic verifier with tests.
3. HTS token, HCS topic and hash anchoring.
4. Anti double-counting guard.
5. AI agent with read-only tools and figure verification.
6. Guardian policy and roles.
7. Multi-language frontend and interpretations.
8. RAG if there is a usable corpus.
9. Evaluation, video and Devpost description.

## 14. Pending decisions

- Methodology is decided: Verra VM0044 v1.2 (see `METHODOLOGY-VM0044.md`); the open decisions are listed in `BACKEND-SPEC.md` section 15.
- Final interface languages.
- Whether RAG is included or declared as future work.
- Guardian deployment mode and license `[VERIFY]` (current release 3.7.1, 2026-10-06).
- AI models to use and their cost `[VERIFY]`.

## For your review
Language scope, whether RAG is in the submission, and the decision not to use LoRA.
