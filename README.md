# ClimAudit

Evidence checking for biochar carbon credits, with a public audit trail on Hedera.

Built for the IEEE ClimateChain Global Hackathon 2026, track **Carbon Markets & Emissions Transparency**.

ClimAudit checks the evidence of a biochar batch against Verra methodology **VM0044 v1.2** and computes the carbon dioxide removed as a conservative range. Deterministic code does every calculation. An optional AI assistant can only propose values with a verbatim quote, and a person confirms them. A human verifier decides; the registry issues the credits as a Hedera token. Each step is a hash-chained audit event, and the hashes (never the evidence) are published on a Hedera topic, so anyone can check the chain against the public ledger.

All data in this repository is synthetic and the network is the Hedera **test network**. No credit here is real.

## What is here

| Folder | Contents |
|---|---|
| `backend/` | FastAPI service: evidence rules, VM0044 calculation, state machine, hash chain, Hedera and Guardian adapters. See `backend/README.md`. |
| `web/` | Next.js web app (verifier, registry, owner and holder roles, audit page) and the recorded-run mode. See `web/README.md`. |
| `submission/` | Devpost text, video script, architecture diagram, security assessment. |
| `demo/` | Scripts that record the demo video clips and assemble the video. |
| `research/`, `agents/`, `skills/` | Research notes and the agent and skill definitions used to build the project. |

Design documents at the top level: `PLAN.md`, `BACKEND-SPEC.md`, `FRONTEND-CONCEPTUAL-DESIGN.md`, `SCHEMA.md`, `METHODOLOGY-VM0044.md`, `RULES.md`, and `DECISIONS-LEDGER.md` (every decision with its reason).

## Try it

**Recorded run (no keys, no backend).** The web app replays a real testnet run, read-only:

```bash
cd web
npm install
npm run build
CP_SNAPSHOT=1 npx next start -p 3100     # PowerShell: $env:CP_SNAPSHOT="1"; npx next start -p 3100
```

Open http://localhost:3100 and choose a role.

**Local live stack (every action works, in-memory ledger).**

```bash
cd backend
python -m venv .venv
.venv/Scripts/python -m pip install -e ".[dev,geo]"     # Linux/macOS: .venv/bin/python
.venv/Scripts/python scripts/dev_stack.py           # API with three demo batches; writes demo keys to ../web/.env.local
cd ../web && npm install && npm run dev             # in another terminal, then open http://localhost:3000
```

To publish to the Hedera test network instead, copy `backend/.env.example` to `backend/.env`, fill in a testnet account (never commit it) and run `dev_stack.py --ledger direct --fresh-ledger`. `DEPLOY.md` covers hosting.

## Tests

```bash
cd backend && .venv/Scripts/python -m pytest    # 265 tests
cd web && npm run check                         # types, lint, translations, contrast, 55 tests (including an axe accessibility audit)
```

## What this is not

- That the AI replaces verifiers.
- That a blockchain makes bad source data good: hashes show only that the record did not change after it was recorded.
- That test network tokens are real credits or carry the label of any standard.
- Any accuracy or detection rate of the AI or of the document checks.
- A verification, a certification or a compliance statement. A person decides: the output is a recommendation, not a ruling.

The software was written with the help of an AI coding assistant.

## Licence

MIT, see `LICENSE`. Third-party data and tools are listed with their licences on the About page of the web app and in `research/PUBLIC-DATA-LAYER.md`.
