# Frontend: analysis and conceptual design

Status: 2026-10-17. The decisions of section 12 were approved (palette A, ledger teal); phase F1 is done in `web/` (see section 13). The text of sections 1 to 12 is the design as proposed. It follows the method used for the OneAquaHealth frontend (`docs/frontend_conceptual_design.md` there: what exists, purpose, principles, information architecture, trust elements, states, data layer, technology, backend gaps, phases, decisions) and reuses its design language. `FRONTEND-DESIGN.md` holds the visual language, `LANGUAGES.md` the language policy.

## 1. What exists today

No frontend. The backend (`backend/`, 258 tests) exposes this contract (all routes except `/health` need a role key; state-changing routes need an `Idempotency-Key`):

| Route | Role | Returns |
|---|---|---|
| `GET /profiles`, `/profiles/{id}` | any key | methodology profiles (parameters with source, page, verified flag) |
| `POST /projects`, `/projects/{id}/facilities`, `PUT /facilities/{id}/years/{y}/evidence` | owner | create project, facility, facility-year evidence |
| `POST /batches`, `PUT /batches/{id}`, `GET /batches/{id}` | owner, any (read) | batch with evidence |
| `POST /batches/{id}/documents`, `/evidence`, `/evidence/{item}/confirm` | owner, verifier | upload a document (sanitizer findings returned), add and confirm evidence |
| `POST /batches/{id}/transitions` | per role | state change (submit, review, verify, reject, needs info) |
| `POST /batches/{id}/verification`, `GET /report`, `GET /findings`, `POST /findings/override` | verifier, admin | report with range, findings, overrides with reason |
| `POST /batches/{id}/issue` | registry | issue credits (ledger mint) |
| `GET /credits/{id}`, `POST /credits/{id}/transfer`, `/retire` | holder, owner | balances, transfer, retire |
| `GET /audit/{batch_id}`, `GET /audit/verify` | any key | audit events with ledger references, chain and ledger comparison |

**Gaps for a usable interface:**
1. No list routes: the UI cannot show "my projects", "my batches" or "my credits".
2. No identity route (`GET /me`): the UI cannot show who it is acting as.
3. No catalog route: finding codes, error codes, states and their blocking semantics exist only in `SCHEMA.md`; the UI needs them as data (codes, severity, blocks, overridable) to render and translate.
4. No document read-back (the sanitized visible text) for the verifier.
5. No exported OpenAPI file: `/openapi.json` is now off by default, so types must be generated from a script (as OneAquaHealth does with `app.openapi()`).
6. The ledger network and ids are needed to build HashScan links (`topic_id`, `tx_id` are in the audit events; the network name is not).
7. Browsers cannot hold role keys: a same-origin server layer must.

## 2. Purpose and audience

A hackathon deliverable that must make one story clear in under three minutes, then survive a closer look: *how a batch of biochar evidence becomes a bounded, auditable credit, who decided, and how anyone can check it.* Primary audiences: the judges (clarity, trust, blockchain evidence); the verifier persona (works through findings and the number); the auditor persona (checks the chain). Secondary: a technical reader (method, sources, decisions).

## 3. Design principles

Inherited from `FRONTEND-DESIGN.md` and the OneAquaHealth lessons:
1. **Honesty first.** Every number shows its provenance (measured, modeled, synthetic), its uncertainty as a range, and its source; synthetic and testnet are permanent, visible labels.
2. **Recommendation, not verdict.** No "approved" or "fraud" badges; wording such as "consistent evidence" and "needs review"; the human decision is its own, clearly attributed action.
3. **Explain, do not decorate.** Each screen answers one question: "what is this batch", "why this number", "what blocks it", "who decided", "can I check it".
4. **Accessible by default.** Colour is never the only channel (icon and text with every status), keyboard first, `lang` per fragment, reduced motion.
5. **Backend text stays English, interface text is translated.** The interface translates its own labels, state names, finding and error codes; free text from the backend is shown as it is, with a "text in English" hint.
6. **Single source of truth.** Tokens in one file; every visible string from a catalog; types generated from the API.

## 4. Information architecture and layout

This is a workflow tool, not a chat. It keeps the OneAquaHealth shell (left sidebar, centred content, optional right pane) but swaps the conversation for a **batch workspace**.

```
/                      Batches: list with state, claimed vs computed range, last event
/batches/new           Guided intake: project, facility, batch, evidence, documents
/batches/:id           Workspace (tabs): Overview | Evidence | Findings | Report | Decision | Credit | Audit
/credits               Credits and balances (holder and registry views)
/audit                 Chain and ledger check for everything the key can see
/method                What the calculation is: profile parameters with sources, what it is not
/about                 Attributions, licences, synthetic and testnet notice, AI disclosure
/settings              Language, theme, demo persona
```

**Shell.** Left sidebar: persona switcher at the top (where OneAquaHealth has the country selector), then Batches, Credits, Audit; Method and About at the bottom with Settings. No numbers in the sidebar. Right pane (closed by default, like the map pane there): **Evidence and audit drawer** for the selected item (document text, hash chain link, ledger reference). A permanent footer notice: "Recommendation, not a ruling. Synthetic data. Testnet only."

**Workspace tabs, in the order a reader needs them:**
1. *Overview*: state timeline (DRAFT to RETIRED, with BLOCKED and NEEDS_INFO), claim versus computed range as one bar, the three most important findings, next allowed action for the current persona.
2. *Evidence*: items grouped by kind with provenance dot, unit, document reference and confirmation status; documents with their sanitizer findings; pending proposals from the extractor with the quote shown next to the value.
3. *Findings*: cards grouped by severity with a "blocks calculation / blocks verification / advisory" chip, parameters in plain language, and the override dialog (reason required) for overridable codes.
4. *Report*: the calculation as a readable ladder (inputs, equation steps, parameter references with source and verified flag), the range (low, central, high), the issuable amount and why it is the lower bound, public-data advisories.
5. *Decision*: the actions the persona may take (start review, run verification, verify, reject, request info, issue), each with its consequence stated; disabled with the reason when not allowed.
6. *Credit*: units, balances, transfer and retire forms, mint transaction and token links.
7. *Audit*: the event list (type, sequence, hash abbreviated with copy, ledger topic and transaction with a HashScan link) and a "verify against the public ledger" button showing chain intact, ledger match and the first broken sequence.

**Guided intake** is a stepper that mirrors the evidence kinds closed list, with the unit pickers and the "measured, modeled, synthetic" choice at every field; it is the heaviest screen and the one most worth cutting to a pre-filled example for the demo.

## 5. Trust elements that must appear

| Element | Source | Where |
|---|---|---|
| Provenance dot (measured, modeled, synthetic) | evidence `provenance` | every value |
| Range, not a point | `kg_co2e.low/central/high`, `issuable_kg` | batch list, overview, report |
| Claim versus computed | batch `claimed_kg_co2e` | overview bar |
| Parameter source and verified flag | `calc` parameter references | report ladder |
| Finding blocking semantics | catalog `blocks_calculation`, `blocks_verified`, `overridable` | finding card |
| Who decided and why | audit events, override records | decision tab, audit |
| Anchored hash | audit `hash`, `ledger_ref` | anchored-evidence component with HashScan link |
| Chain verified | `GET /audit/verify` | audit tab and footer status |
| Advisory public data | `REGISTRY_*`, `WEATHER_*`, `LAND_COVER_*`, `TRANSPORT_DISTANCE_*` | report, labelled "advisory" with dataset and version |
| Synthetic and testnet | `provenance`, config | permanent footer and per-screen tag |
| AI disclosure | extractor source `model` | evidence item "proposed by AI, confirmed by <person>" |

## 6. States the interface must handle

Loading, empty (no batches), partial (report incomplete with its blocking findings), 401 (missing or invalid key), 403 (role not allowed, shown with the required role), 404 (unknown batch), 409 (state conflict, period overlap with the other batch id, idempotency conflict), 413 (body too large), 422 (validation with the field names), 429 and 503 (ledger unavailable, retry with the same idempotency key), offline. Each has a sentence written for a person, mapped from the backend error code through the language catalog.

## 7. Roles, access and demo mode

The backend authenticates with static role keys. A browser must never hold them. Recommended: a **Next.js server layer** that holds the demo keys in server environment variables and exposes a same-origin proxy; the persona switcher (owner, verifier, registry, holder, auditor) chooses which key the proxy uses. This is explicit demo access ("Demo: acting as Verifier"), not authentication. Write actions are enabled in the local live mode and disabled or replayed in the public snapshot mode (section 9).

## 8. Data layer

Types generated from an OpenAPI file exported by a script from `create_app().openapi()` (the live route is off by default). A typed client per route with the error envelope mapped to messages, an `Idempotency-Key` created per user action and reused on retry, short-lived fetch hooks (no polling; refresh after an action). The base URL and the proxy keys come from environment variables. Catalogs for findings, errors and states come from a new backend catalog route, not from copies in the frontend.

## 9. Technology and modes

Follow the reference stack so its components and checks carry over: Next.js (App Router), React, TypeScript, Tailwind CSS 4 with the shared semantic tokens, `openapi-typescript`, Vitest with Testing Library, ESLint, an i18n catalog check script (every key present in every catalog), a plain SVG for the range bar, no charting library. Leaflet is not needed for the first version (an optional small parcel map of H3 cells can come later).

**Run modes** (the real decision, section 12):

| Mode | What it is | Cost | Fits |
|---|---|---|---|
| A. Local live | frontend and backend on the author's machine (or a compose file), real Hedera testnet, real Guardian | none | the video, the judges who clone the repository |
| B. Public snapshot | a hosted read-only frontend that replays a recorded real run (batch, report, audit events with the real HashScan links), clearly labelled "recorded run" | small: a static or Vercel deployment, no backend | a link in the Devpost entry that works without any setup |
| C. Public live | backend in a container on a small host with a persistent volume plus the frontend; write actions on | real: hosting, abuse protection, key handling | not recommended for a 7-day sprint |

Recommendation: **A for recording and for judges who clone, B for the public link.** The snapshot is generated by a script from a real run, so no number in it is invented.

## 10. Backend additions the frontend needs (small, testable)

1. `GET /projects`, `GET /batches`, `GET /credits`: role-scoped lists with the fields the list screens show (state, claimed and computed range, updated at).
2. `GET /me`: actor id and role.
3. `GET /catalog`: findings (code, severity, blocks, overridable), states and transitions allowed per role, error codes with HTTP status.
4. `GET /batches/{id}/documents` and `GET /documents/{ref}/text`: list and sanitized text (verifier and owner).
5. `GET /config/public`: ledger mode, network name, mirror and HashScan base URL, provenance mode.
6. `scripts/export_openapi.py` that writes the OpenAPI file used for the generated types.

## 11. Delivery phases (today 17 Oct, submission target 24 Oct 6:00 PM CST)

| Phase | Content | Exit criterion | When |
|---|---|---|---|
| F0 | this design and the decisions of section 12 | scope, mode and identity agreed | 17 Oct |
| F1 | backend additions, OpenAPI export, project scaffold, tokens, shell, client, persona proxy, catalogs (English) | contract test passes against the running API | 18 Oct |
| F2 | batches list, workspace Overview and Evidence | the demo batch reads correctly end to end | 19 Oct |
| F3 | Findings, Report (range bar, parameter ladder), advisories | every trust element of section 5 visible | 20 Oct |
| F4 | Decision, Credit, transfer and retire | the full lifecycle works in the live mode | 21 Oct |
| F5 | Audit tab, verify button, HashScan links, Method and About; snapshot generator and mode B | the public snapshot replays a real run | 22 Oct |
| F6 | second language tier, accessibility and script audit, tests, demo capture and video | checks pass, video recorded | 23 to 24 Oct |

The schedule is tight; the lever is scope, not quality: the guided intake (section 4) can be replaced by a pre-filled example, and languages beyond the first tier can follow the submission (`LANGUAGES.md` tiers).

## 12. Decisions needed

1. **Run mode:** A plus B (recommended), A only, or C.
2. **Identity and layout:** the workflow shell of section 4 with the OneAquaHealth tokens and a new earth-and-green palette (recommended), or the same palette as OneAquaHealth.
3. **Languages for the first submission:** English default with a selector that offers Spanish (D-187, restored by D-195). The code, documents and demo are English.
4. **Guided intake:** a full stepper, or a pre-filled example plus an advanced form later (recommended for the deadline).
5. **Backend additions of section 10:** approved as listed?
6. **Product name and tagline** shown in the interface (ClimAudit is the working name).

## 13. Status of the delivery phases

- **F0 done (2026-10-17):** decisions D-187 and D-188: run mode A plus B, workflow shell, English default with a Spanish option in a selector (D-195), pre-filled example first, backend additions approved, palette A.
- **F1 done (2026-10-17):** the read routes of `BACKEND-SPEC.md` section 22; OpenAPI export and generated types; `web/` with Next.js, Tailwind tokens (palette A, light and dark, contrast checked), the shell with persona and language switchers, the server proxy and persona cookie, the typed client with idempotency keys, error and state sentences for every backend code, English and Spanish catalogs with a check script, and the batches list as the first screen. Verified against the running backend. Section 10 items 1 to 3, 5 and 6 are done; item 4 (document listing and text) is done as well.
- **F2 done (2026-10-17):** batch workspace with Overview and Evidence (D-191), list rows link to it, plain names and units for all evidence kinds, sanitized document text on demand, tabs with keyboard navigation, English default with a selector (Spanish selectable, D-195). Verified live. Small-screen layout uses cards for the list; the evidence tables scroll inside their card.
- **F3 done (2026-10-18):** Findings tab (texts for every code, blocking chips, accept-with-a-reason form) and Report tab (calculation ladder, inputs, parameters with page and check, uncertainty, advisories, grounded summary), D-193 and D-194. The interface is English by default with a selector (D-195).
- **F4 done (2026-10-18):** Decision tab and Credit tab (D-196, D-197), confirmation of proposed evidence, explorer links for real ledgers. The whole lifecycle was walked through the interface on the running stack.
- **F5 done (2026-10-18):** Audit tab and page with the verify button, Method and About pages, and snapshot mode (D-198): a recorded real testnet run replayed read-only with no API and no keys.
- **F6 done (2026-10-18):** start page with role cards (D-199), axe audit of every page and tab in the test suite, translated error pages, video script for the web app. Left to the author: record the video and the final submission.
