## Inspiration

A carbon credit is only as good as the evidence behind it. For biochar, that evidence is a stack of lab reports, production logs, freight invoices and application records that a verifier reconciles by hand. A typo, a missing moisture correction, or the same field sold twice can inflate a claim. Registries publish the result, but the checking itself is slow, manual and hard to audit afterwards.

We wanted the checking to be transparent: every step reproducible, every decision recorded, and the final trail verifiable by a third party **without trusting us**.

## What it does

ClimAudit helps a verifier decide whether a batch of biochar justifies the credits it claims under **Verra VM0044 v1.2**.

1. A **project owner** submits a batch: facility, production, application and transport data, plus the supporting PDFs.
2. A **sanitizer** strips or flags hidden and injected text in the documents. An optional, read-only AI module can *propose* values with a verbatim quote; the server accepts a value only if the quote is really in the document, and a person must confirm it.
3. **Rules and guards** run: mass balance across documents, the H:Corg eligibility limit, the one-year application rule, and a two-layer double-counting guard (exact key plus H3 spatial overlap).
4. A **deterministic calculation** (exact decimals, no floats, every factor with its source page) returns the carbon dioxide removed as a **range**. Only the lower bound can be issued, never more than the claim.
5. A **human verifier** reviews the findings and numbers and decides. The AI never approves or issues anything.
6. The **registry** issues credits as a Hedera token (1 unit = 1 kg CO2e). Holders transfer and retire them.
7. Every step is a **hash-chained audit event**. Only the hash is published on a Hedera topic; the evidence stays off-chain. Anyone can recompute the chain and compare it with the public ledger.

For the organic carbon in the biochar and the removal it represents:

$$CC = M \times FC \times PR_{de}, \qquad \text{gross removal} = CC \times \tfrac{44}{12}$$

For a batch of 100 t dry biochar with carbon fraction 0.80 and permanence factor 0.89, that is 71.2 t C, or 261.07 t CO2e before emissions and leakage. The synthetic demo batch claims 300,000 kg and the system computes 250,728 to 271,614 kg, so it would issue the lower bound.

## Track alignment: Carbon Markets & Emissions Transparency

The track asks for trust, transparency and efficiency in carbon markets, and names blockchain-based credit verification and double-counting prevention. ClimAudit does exactly that for biochar removal credits: reproducible verification, a double-counting guard, a token for the credits on Hedera, and a public audit trail that anyone can check against the ledger.

## How we built it

- **Backend:** Python 3.12, FastAPI, SQLite as system of record, a closed state machine, idempotent issuance, canonical JSON with SHA-256 hash chaining.
- **Hedera:** an HCS topic for audit hashes, an HTS fungible token for the credits, mirror-node read-back, via the Hiero Python SDK (testnet only). An optional adapter anchors the same events through a **Hedera Guardian** policy.
- **Methodology as data:** VM0044 parameters and CDM tool factors live in a versioned data file with source pages and a "verified" flag, so an unconfirmed parameter is visible in every report. Key equations were checked against the PDF page images.
- **Web app:** Next.js and React with one screen per role (owner, verifier, registry, holder), a batch workspace, an audit page that checks the chain against the ledger, English and Spanish, and an automated accessibility audit (axe).
- **Public demo:** a read-only **recorded run** of a real Hedera testnet run, so the public link holds no keys and cannot change anything.
- **Process:** every design decision and its reason is in a decisions ledger. An independent code review found 29 issues, all fixed with regression tests. 265 backend tests and 55 web tests pass in CI. The software was written with the help of an AI coding assistant (Claude Code) under the author's direction.

## Challenges

- The methodology PDFs lost their math symbols in text extraction, so we rendered the pages and checked the key equations by eye before trusting them.
- Guardian's bundled VM0044 policy could not be imported on a local node, so we built a minimal audit policy and documented why.
- Hedera has no idempotency key, so a retry after a crash looks up the earlier transaction through its memo.
- Keeping AI useful but harmless: documents are untrusted input, so the model is read-only, its proposals pass literal-text checks on the server, and a person confirms and decides.

## What we learned

A blockchain does not fix bad source data. What it can do is make the checking tamper-evident after the evidence is in. The valuable part is deterministic, inspectable checking plus a record nobody can quietly edit.

## What is real and what is a demo

All project data is **synthetic** and the network is the Hedera **test network**. The credits are not real and carry no label from any standard. ClimAudit is not a verification, a certification or a compliance statement: a person decides.

## Who it is for and how it scales

It is for verifiers and registries that want a reproducible second opinion on evidence packages, and for project owners who want to show their claim is consistent. The methodology is data, so a new Verra or Gold Standard profile, or a new kind of environmental credit, is a new profile with the same evidence checks, the same human decision and the same public trail. Per Hedera's published fee schedule, one audit message costs about 0.0008 USD and one token mint about 0.001 USD (checked 2026-10-16).

## What is next

More interface languages, minting through a Guardian token, per-holder accounts for on-chain transfers, a larger injection test set so a detection rate can be measured, an external security review, and more methodology profiles.
