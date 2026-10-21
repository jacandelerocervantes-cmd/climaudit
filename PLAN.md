# PLAN — IEEE ClimateChain Global Hackathon 2026

- Deadline (Devpost schedule): submissions close **25 Oct 2026, 8:00 AM CST** (open since 4 Oct, 10:00 PM CST); judging 26 Oct to 8 Nov; winners 20 Nov. The organizer page states 11:59 PM UTC, so the earlier time is used. Target: submit by 24 Oct, 6:00 PM CST.
- Team: individual. Track: **Carbon Markets & Emissions Transparency**.
- Chosen chain: **Hedera + Guardian** (HTS for tokens, HCS for audit).
- Working rules: no commits unless requested, no `Co-Authored-By`.

## Status (2026-10-17)

Done and verified: backend (265 tests), direct Hedera testnet adapter and Guardian adapter (both run live end to end), advisory public-data checks, submission package in `submission/` (Devpost draft, video script, architecture diagram, security assessment). Frontend: phases F1 to F6 done (`web/`, `FRONTEND-CONCEPTUAL-DESIGN.md` section 13), including the public recorded-run mode. Not done: the recorded video, final Devpost submission (the author fills the placeholders and submits). Open items are tracked in `DECISIONS-LEDGER.md`.

## Document map

`DECISIONS-LEDGER.md` (every decision with its reason; append-only) · `RULES.md` (rules and claims governance) · `PLAN.md` (this file) · `ARCHITECTURE.md` (design) · `SCHEMA.md` (entities, states, codes) · `BACKEND-SPEC.md` (build contract: routes, roles, evidence kinds, profile schema, calculation rules, hash spec with vectors, fixtures, open decisions) · `METHODOLOGY-VM0044.md` (equations, defaults, CDM tools) · `VERIFICATIONS.md` (what was checked and how) · `LANGUAGES.md` and `FRONTEND-DESIGN.md` (UI) · `DEPLOY.md` · `DEEP-RESEARCH-PROMPT.md` · `agents/` and `skills/`.

## Idea: ClimAudit (provisional name)

Verification of carbon credits of agro/bioprocess origin (biochar, soil, agricultural residues) with:
1. **Anchored evidence**: each batch stores in HCS the hash of its evidence package (plot, period, method, measurements).
2. **Anti double counting**: a plot + period can only be credited once; overlaps are rejected.
3. **Deterministic verifier**: code checks consistency (ranges, units, dates, mass balance) and computes the CO2e range; an optional read-only AI assistant only proposes extracted values, gated by a literal-text check and a person; a human verifier decides.
4. **Tokenized credit on HTS**, with retirement traceable to a beneficiary.
5. **Guardian**: a published audit policy anchors each audit hash as a signed credential (the full VM0044 policy could not be imported on a local node, see `DECISIONS-LEDGER.md` O-23 and D-160).

## Judging criteria and how they are covered

| Criterion | Coverage |
|---|---|
| Climate Impact | Verification evidence for biochar removal credits: tamper-evident trail, in-registry overlap guard and conservative uncertainty (no claim that fraud is eliminated) |
| Innovation | Reproducible deterministic verification with a human decision, an optional read-only AI behind literal-text gates, and an audit trail anyone can check against the public ledger (Hedera direct or Guardian) |
| Technical Execution | HTS + HCS + Guardian policy + verification backend working on testnet |
| Practical Usefulness | Low cost per operation, flow with real roles |
| Presentation | Video of 3 to 5 minutes (Devpost page), story: problem, flow, impact |

## Architecture

- **Hedera testnet**: credit token (HTS), audit topic (HCS), accounts per role.
- **Guardian 3.7.1** (local Docker quickstart): audit policy `backend/guardian/climaudit_audit.policy`; tokens go through the direct HTS adapter.
- **Backend (Python/FastAPI)**: evidence ingestion, deterministic verification + AI agent, sending hashes/messages to Hedera.
- **Frontend**: built (`web/`, phases F1 to F6); the demo runs in the web app, and the lifecycle also runs from `backend/scripts/demo_flow.py`.
- **Data**: sample evidence marked as synthetic; real or external data labeled with its origin.

## Milestones (today 16 Oct → submission target 24 Oct, 6:00 PM CST)

Code is authorized in `backend/` (`RULES.md` user rule 2). A public repository, any commit and any push happen only after the user's explicit order (user rule 1).

| Date | Milestone |
|---|---|
| 16–17 Oct | Hedera testnet account, Guardian running, public repository |
| 18–19 Oct | HTS token + HCS + deterministic verifier |
| 20–21 Oct | AI agent + checks + Guardian policy |
| 22–23 Oct | Frontend and full flow on testnet |
| 24 Oct | Video (3 to 5 minutes), README, Devpost description |
| 24 Oct, by 6:00 PM CST | Final review and submission on Devpost (closes 25 Oct, 8:00 AM CST) |

## Deliverables to satisfy (strictest reading of both sources, see `VERIFICATIONS.md` 4b)

- Working prototype on Hedera testnet; public repository with documentation.
- Architecture diagram and technical specification: `submission/architecture.svg`, `submission/ARCHITECTURE-DIAGRAM.md`, `ARCHITECTURE.md`, `SCHEMA.md`, `BACKEND-SPEC.md`.
- Security and data integrity assessment document: `submission/SECURITY-ASSESSMENT.md` (written 2026-10-17).
- Demo video of 3 to 5 minutes (the Devpost page; an earlier note said 3 or less). Recommended (not an organizer rule, from the research report): at least 45 seconds of live Hedera testnet transaction ids and Guardian outputs.
- Problem statement and solution overview, climate impact assessment, adoption strategy, scalability roadmap (the organizer lists these as impact deliverables).
- Organizer weighting, if it applies: climate impact 30%, technical innovation and blockchain implementation 30%, feasibility 10%, data security and transparency 10%, UX and design 10%, scalability 10% `[VERIFY: a second 70/20/10 list appears on the same page]`.

## Differentiation strategy (from the research report, adapted)

Pitch thesis: an evidence-grounded, adversarially aware biochar verification copilot for Hedera Guardian. Effort figures are the report author's estimates, not measurements; all metrics are targets until measured on our own test data.

| Angle | What it is | Role |
|---|---|---|
| 1. Neuro-symbolic evidence checker and mass-balance auditor | Deterministic checker blocks any figure not found verbatim in the cited span; cross-checks production, laboratory and freight records | Core spine |
| 2. Provenance-scored uncertainty engine | VM0044 v1.2 equations with Table 3 permanence defaults (Woolf regression only as a separate labeled profile) plus an explicit conservative discount for modeled inputs; haircut recorded on HCS | Core spine |
| 3. Adversarial document shield | PDF sanitizer for hidden text, injection test set with measured block rate, Benford screen as a flag | Lightweight module |
| 4. Parcel-and-period double-counting guard | H3 cell sets and period overlap; only hashes public | Lightweight module (already in `SCHEMA.md`) |
| 5. UI languages and verifier-review log | English backend, frontend catalogs (machine-translated, agent-audited), signed JSONL review log as the LoRA foundation | Lightweight module |

Demo contrast to show: a naive AI wrapper hijacked by a hidden-text PDF and over-crediting wet biochar versus the checker quarantining the injection, flagging the mass-balance and Benford signals, computing persistence with a haircut, verifying the parcel-period hash on HCS and routing the clean record to a human verifier.

## Reuse of AquaLedger (OneAquaHealth-clean)

Read-only; the repository is not modified. Whatever is copied is noted with its origin.

| Piece | Origin | Use |
|---|---|---|
| Figure verification | `src/oah/chat`, `scripts/eval_grounding.py` | Skill `grounded-report-check` |
| Hash-chained record | `src/oah/audit` | Skill `hcs-hash-anchoring` (HCS instead of a local chain) |
| Measured / modeled / synthetic label | `AGENTS.md`, `src/oah/synthetic` | `RULES.md` |
| QC and plausibility | `src/oah/qc`, `src/oah/reliability` | Batch validation |
| Uncertainty | `src/oah/uncertainty` | CO2e as a range |
| Privacy | `src/oah/privacy` | Generalized plots |
| FastAPI, Dockerfile, Cloud Run | `src/oah/api`, `deploy/` | Backend |
| Next.js on Vercel | `web/` | Frontend |
| Submission templates | `docs/devpost_description.md`, `demo_video_script.md` | Description and script |

Water- and health-specific material is not reused: `waterbase`, `bathing`, `fhir`, `indices`, `risk`.

## Agents, skills and rules from `00_plataforma-ia`

Origin: the user's local `00_plataforma-ia` repository (read-only; its location is not recorded here).

**Rules merged** into `RULES.md`: `core/reglas/reglas-comunes.md`, `stacks/ambiental/comun/reglas-ambiental.md`, `stacks/agentes-competencias/comun/reglas-agentes-competencias.md`, plus the user's rules (no commits unless ordered, no `Co-Authored-By`).

**Existing items that work as-is or adapted:**

| Item | Path in plataforma-ia | Purpose |
|---|---|---|
| `hackathon-prize-strategy`, `hackathon-backward-plan`, `competition-intake` | `stacks/agentes-competencias/skills/` | Strategy, backward plan, eligibility |
| `submission-prep-checklist`, `competition-day1-checklist` | same | Prepare the submission |
| `decision-log`, `session-handoff`, `experiment-log` | same | Decision log and continuity |
| `hash-chain-evidence-ledger` | `stacks/civico-legal/skills/` | Basis of `hcs-hash-anchoring` |
| `ingesta-qc-datos-ambientales`, `politica-de-tiempo-utc` | `stacks/ambiental/skills/` | Environmental data and time |
| `security-engineer`, `solutions-architect`, `qa-test-engineer`, `technical-writer`, `code-reviewer`, `ui-ux-designer`, `product-manager`, `backend-engineer` | `stacks/dev-ia/agents/` | Supporting roles |
| `council-lite`, `verification-before-completion`, `systematic-debugging`, `estrategia-testing`, `diseno-apis`, `observabilidad`, `rag-implementacion`, `agentes-ia-en-producto` | `stacks/dev-ia/skills/` | Quality and design |
| Commands `iniciar`, `auditar-proyecto`, `cerrar-especificacion`, `verificar-reutilizacion` | `stacks/dev-ia/commands/` | Workflow |

**Own versions created** (in this folder):

| Type | File | Function |
|---|---|---|
| Agent | `agents/carbon-evidence-verifier.md` | Audits the evidence of a batch |
| Agent | `agents/hedera-architect.md` | Hedera design and costs |
| Agent | `agents/climatechain-judge-simulator.md` | Scores against the 5 criteria |
| Agent | `agents/devpost-submission-writer.md` | Drafts the submission without sending it |
| Skill | `skills/carbon-credit-evidence-verification/` | Evidence and CO2e verification |
| Skill | `skills/double-counting-guard/` | Anti double-counting rule |
| Skill | `skills/hcs-hash-anchoring/` | Hash anchoring in HCS |
| Skill | `skills/grounded-report-check/` | Report figures against the evidence |
| Skill | `skills/climatechain-submission-checklist/` | Checklist and backward plan |

## Pending decisions

- Guardian 3.7.1 (2026-10-06) is the current release; confirm how to deploy it (local Docker or service) and its license `[VERIFY]`.
- Hedera fees were verified on 2026-10-16 (`VERIFICATIONS.md` section 1); re-check before citing in the submission.
- Confirm eligibility: age of majority, student, non-excluded country (see full rules on Devpost).
- Register on Devpost if not done; review recordings of the organizer's training sessions that have already taken place.
