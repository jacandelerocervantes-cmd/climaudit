# Devpost submission draft: ClimAudit

Track: Carbon Markets & Emissions Transparency. Status: draft for the author to review and submit. Placeholders in `[BRACKETS]` must be filled by the author. The submit button is the author's.

## Tagline

Evidence checking for biochar carbon credits: deterministic Verra VM0044 math, a human verifier who decides, and an audit trail anyone can check on Hedera.

## Inspiration

A carbon credit is only as good as the evidence behind it. For biochar, that evidence is a stack of lab reports, production logs, freight invoices and application records that a verifier has to reconcile by hand, and a typo, a missing moisture correction or the same field sold twice can inflate the claim. Registries publish the result, but the checking is slow, manual and hard to audit afterwards. We wanted to make the checking itself transparent: every step reproducible, every decision recorded, and the final trail verifiable by a third party without trusting us.

## What it does

ClimAudit helps a verifier decide whether a batch of biochar justifies the credits it claims under Verra VM0044 v1.2.

1. A project owner submits a batch: facility, production, application and transport data, plus the supporting PDFs.
2. A sanitizer strips or flags hidden and injected text in the documents. An optional AI extraction module (read-only, not yet exposed through the API) can **propose** values with a verbatim quote; the server accepts a proposed value only if the quote is really in the sanitized document text, and a person must confirm it before it counts.
3. Rules and guards run: mass balance across documents, the H:Corg eligibility limit, the one-year application rule, and a two-layer double-counting guard (exact key plus H3 spatial overlap).
4. A deterministic calculation (Decimal arithmetic, VM0044 equations 1 to 15, every factor with its source and version) produces tonnes of CO2e as a **range**. Only the lower bound can be issued, and never more than the claim.
5. A human verifier reviews the findings and the numbers and decides. The AI never approves or issues anything.
6. The registry issues credits as an HTS token (1 unit = 1 kg CO2e). Holders transfer and retire them.
7. Every step becomes a hash-chained audit event. The hash is published on a Hedera topic, directly or as a signed credential through a Guardian policy, and an independent verifier compares the public record with the local chain.

An optional layer cross-checks the claims against public data (great-circle geometry for transport distances, Open-Meteo weather on the application dates, ESA WorldCover land cover, and the Berkeley Voluntary Registry Offsets Database). It only adds findings for the human and never changes a number.

## How we built it

- **Backend:** Python 3.12, FastAPI, SQLite as the system of record; a closed state machine; idempotent issuance with a ledger-side lookup after a crash; canonical JSON and SHA-256 hash chaining with literal test vectors.
- **Hedera:** HCS topic for audit hashes, HTS fungible token for credits (3 decimals: one base unit is 1 kg CO2e, one displayed token is one tonne), mirror-node read-back; the Hiero Python SDK, testnet only.
- **Guardian 3.7.1:** a small audit policy published in Guardian; the adapter submits each event hash to the policy form, reads the signed credential back and takes the consensus timestamp and sequence number from the public record.
- **Methodology as data:** VM0044 parameters and CDM tool factors live in a versioned data file with sources and a verified flag, so an unverified parameter is visible in every report. Key equations were checked against the PDF page images.
- **Optional AI:** Claude, read-only, behind the extraction gate. All reported numbers are computed by code.
- **Process:** every design decision and its reason is recorded in a decisions ledger; an independent review of the code found 29 issues, all fixed with regression tests. The code was written with the help of an AI coding assistant (Claude Code) under the author's direction.

## What is real and what is a demo

- Real: the code, the calculations, the audit chain, live transactions on **Hedera testnet** and a **local Guardian**.
- Demo: all project data is synthetic and labelled `SYNTHETIC_DEMO_DATA`. Testnet tokens are not real credits and carry no label from any standard.
- Demo: a web app (Next.js) with one screen per role, the batch workspace, the audit page and a recorded-run mode that replays a real testnet run read-only. The same lifecycle also runs from `backend/scripts/demo_flow.py`.

## Evidence you can check

- Hedera testnet topic of the recorded run: https://hashscan.io/testnet/topic/0.0.11078885
- Hedera testnet token of the recorded run: https://hashscan.io/testnet/token/0.0.11078886
- Live demo (recorded run, read-only): https://climaudit.vercel.app
- 265 backend tests and 55 web tests (including an automated accessibility audit) pass; the lifecycle is reproducible with `backend/scripts/demo_flow.py`.
- Architecture diagram, specification, security and data-integrity assessment: see the repository (`submission/` and the root documents).
- Repository: https://github.com/jacandelerocervantes-cmd/climaudit
- Video: https://www.youtube.com/watch?v=tOxZyXXK4ro

## Challenges

- The methodology PDFs lost their math symbols in text extraction, so we rendered the pages and checked the key equations by eye before trusting them.
- Guardian's bundled VM0044 policy could not be imported on a local node (its tools are published on-chain and their IPFS content was unavailable), so we built a minimal audit policy instead and documented why.
- Making retries safe: Hedera has no idempotency key, so a retry after a crash looks the earlier transaction up through its memo (the public mirror node lags by seconds, which is a known gap).
- Keeping AI useful but harmless: documents are untrusted input, so the model is read-only, its proposals are gated by literal text checks on the server, and a person confirms and decides.

## Accomplishments

- A complete, tested lifecycle from evidence to retirement, running on real Hedera testnet and Guardian.
- A calculation that is reproducible to the last digit and states its uncertainty instead of hiding it.
- An audit trail that an outsider can verify against the public ledger without our software.

## What we learned

Blockchain does not fix bad source data. What it can do is make the checking tamper-evident after the evidence is in. The valuable part is therefore deterministic, inspectable checking plus a record nobody can quietly edit.

## What is next

More interface languages (English and Spanish exist; the catalog mechanism is ready for more); minting through a Guardian token instead of the direct HTS adapter; per-holder Hedera accounts for on-chain transfers; a larger injection test set so a detection rate can be measured and reported; external security review; more methodology profiles.

## Impact material

**Problem and solution.** Biochar removal credits depend on documents that are checked manually. ClimAudit turns the checking into reproducible code with human sign-off and a public audit trail, which lowers the cost of careful verification and makes it comparable across projects.

**Climate impact assessment.** ClimAudit does not remove carbon itself; it protects the integrity of credits that represent removals. Its contribution is to reduce overstated claims (conservative lower bound, mass balance, double-counting guard) and to make verification transparent. We do not claim a tonnage of impact. The synthetic demo batch claims 300,000 kg CO2e and the system computes a range of 250,728 to 271,614 kg (central 261,067 kg) and would issue the lower bound.

**Adoption strategy.** Start with verifiers and registries that want a reproducible second opinion on evidence packages; keep the methodology as data so new Verra or Gold Standard profiles can be added without code changes; run alongside existing registry workflows rather than replacing them.

**Scalability.** Per Hedera's published fee schedule (checked 2026-10-16), one HCS message costs about 0.0008 USD and one token mint about 0.001 USD; the demo lifecycle writes ten audit messages, one mint and one burn. The backend is currently a single process on SQLite; scaling needs a networked database and a signing service, which are listed in the roadmap.

## Built with

Python, FastAPI, SQLite, Next.js, React, TypeScript, Tailwind CSS, Hedera (HCS, HTS, mirror node), Hedera Guardian, Hiero Python SDK, H3, Open-Meteo, ESA WorldCover, Berkeley Voluntary Registry Offsets Database (CC BY 4.0), Claude (optional extraction, development assistance).

## Disclosures

- AI use: the code was written with an AI coding assistant; the optional extraction agent uses a Claude model and is read-only.
- Data: synthetic only. Public datasets are used as advisory snapshots with their licences (Berkeley database: CC BY 4.0, attribution: Quartson, Haya, Bernard, Abayo, Rong, So and Elias, Voluntary Registry Offsets Database, Berkeley Carbon Trading Project, University of California, Berkeley).
- Testnet only; no real funds or credits.

## For your review

1. Fill the repository and video URLs, and confirm the track name and the field limits of the Devpost form.
2. Re-check the Hedera fee figures against the official calculator before submitting (they were read on 2026-10-16).
3. Confirm you are comfortable stating that the code was written with an AI assistant (it is also true and required by honest disclosure).
4. The synthetic numbers (250,728 / 261,067 / 271,614 kg) come from the demo dossier; rerun `demo_flow.py` if you change the dossier.
