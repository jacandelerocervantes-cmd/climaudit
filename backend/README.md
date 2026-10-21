# ClimAudit backend

Evidence verification for biochar carbon credits (Verra VM0044 v1.2) with a hash-chained audit trail and a ledger
port for Hedera. All data in this repository is synthetic and labeled so; nothing here is a real credit.

Design contract: `../BACKEND-SPEC.md`. Entities, states and codes: `../SCHEMA.md`. Equations and defaults:
`../METHODOLOGY-VM0044.md`. Decisions and reasons: `../DECISIONS-LEDGER.md`.

## What it does

- Validates evidence against a closed list of kinds and converts units (`evidence.py`).
- Runs deterministic checks and the VM0044 calculation with Decimal arithmetic (`checks/`, `calc/`, `verification.py`).
- Produces a report with findings, a conservative interval and a recommendation (`human_review | return | reject`).
  It never approves or issues; a human verifier and the registry role do (`states.py`, `service.py`).
- Guards double counting by exact key and by H3 cell-set overlap (`guard.py`).
- Sanitizes uploaded documents so hidden text never reaches a model (`checks/sanitizer.py`).
- Keeps a hash chain of audit events and anchors each hash through a ledger port (`hashchain.py`, `ledger/`).
- Exposes everything over HTTP with role keys and `Idempotency-Key` (`api/app.py`), including an audited verifier override for overridable findings.

## Run it

Requires Python 3.11 or newer.

```bash
python -m venv .venv
.venv/Scripts/python -m pip install -e ".[dev,geo]"      # Windows; on Linux/macOS use .venv/bin/python
.venv/Scripts/python -m pytest                        # runs the whole suite
.venv/Scripts/python scripts/build_fixtures.py        # regenerates ./fixtures
```

Start the API (all settings come from environment variables, see `.env.example`):

```bash
CP_API_KEYS='{"my-key":{"actor_id":"admin-1","role":"admin"}}' \
  .venv/Scripts/python -m uvicorn climaudit.api.app:app_factory --factory --port 8000
```

`GET /health` needs no key. Every other route needs `Authorization: Bearer <key>`, and every state-changing route
needs an `Idempotency-Key` header.

## Configuration

Only environment variables; nothing is hardcoded to a machine. `CP_LEDGER_MODE` is `fake` (default, in-memory),
`direct` or `guardian`.

- `direct` talks to Hedera **testnet** through the Hiero SDK (extra `hedera`: `pip install -e ".[hedera]"`) and the
  public mirror node. Put your testnet operator account in a local `.env`, never in chat or in git:
  `CP_HEDERA_OPERATOR_ID`, `CP_HEDERA_OPERATOR_KEY`. Create the audit topic and the credit token once with
  `python scripts/hedera_setup.py` (use `--dry-run` to see the plan), then add the printed `CP_HCS_TOPIC_ID` and
  `CP_HTS_TOKEN_ID` and set `CP_LEDGER_MODE=direct`. It has only been tested against an in-memory gateway so far;
  `tests/test_hedera_live.py` runs the real roundtrip when `CP_LIVE_HEDERA=1` and the variables are set.
- Transfers between application holders are custodial bookkeeping (anchored in the audit trail); retirement burns
  units from the treasury.
- `guardian` anchors the audit trail through a Guardian policy (`guardian/climaudit_audit.policy`, see
  `guardian/README.md`): set `CP_GUARDIAN_URL`, `CP_GUARDIAN_USERNAME`, `CP_GUARDIAN_PASSWORD` and
  `CP_GUARDIAN_POLICY_ID` in your local `.env`. Credit tokens are delegated to the direct Hedera adapter (set the
  `CP_HEDERA_*` and `CP_HTS_TOKEN_ID` variables). Verified live on Guardian 3.7.1; details in BACKEND-SPEC.md section 19.
  Incomplete configuration fails closed with `LEDGER_UNAVAILABLE`.

## Layout

| Path | Purpose |
|---|---|
| `src/climaudit/` | Package: models, calculation, checks, service, API, ledger port |
| `src/climaudit/profiles_data/` | Methodology profile JSON files (no methodology constants in code) |
| `fixtures/` | Generated synthetic dossiers with `expected.json` computed by independent arithmetic |
| `scripts/build_fixtures.py` | Fixture generator |
| `tests/` | Unit, guard, verification, API-flow and fixture tests |

Public-data cross-checks (advisory, off by default): set `CP_EXTERNAL_CHECKS=1`, install the extras (`pip install -e ".[geo,registry]"`) and, for the registry check, build an index from the Berkeley workbook with `scripts/build_registry_index.py` and set `CP_REGISTRY_INDEX_PATH`. See BACKEND-SPEC.md section 20.

Demo and live tests: `python scripts/demo_flow.py` walks one synthetic batch through the whole lifecycle on the ledger selected by `CP_LEDGER_MODE` and prints the audit events and HashScan links. `tests/test_hedera_live.py` and `tests/test_e2e_live.py` run against the real ledger when `CP_LIVE_HEDERA=1` or `CP_LIVE_E2E=1` (testnet account and a fresh topic required).

Extra settings: `CP_MAX_UPLOAD_BYTES` (default 10 MiB), `CP_FORCE_SYNTHETIC` (default on: projects are always synthetic), `CP_ENV` (`dev` serves `/docs`; the default is `prod`, which does not), `CP_MAX_DOCUMENTS_PER_BATCH` (default 20). Request bodies above twice `CP_MAX_UPLOAD_BYTES` are refused with 413, including chunked ones. Credit transfers go only to known holders (the actor ids of the `owner` and `holder` API keys).

## Known limits

- The PDF sanitizer is heuristic: it flags near-white, tiny (after text matrix and CTM), transparent, off-page, covered-by-white-rectangle and invisible text, text in Form XObjects, and invisible characters. It does not see text hidden behind images, clipping paths, optional-content layers, non-white backgrounds, or in fonts without a text mapping.
- Ledger anchoring happens inside the database transaction; if the ledger accepts a message and the transaction then
  fails, an orphan message can remain on the ledger. `GET /audit/verify` reports a mismatch.
- The modeled-input uncertainty value (0.10) and all profile ceilings are demo parameters, not validated figures.
- The store lock assumes one API process; several processes need a database with row-level locking.
- TOOL03 and TOOL05 are library helpers only; their emissions enter the report as explicit tCO2e totals.
- VM0044 additionality, non-soil life-time proof beyond a document reference, and cross-registry double counting are
  out of scope.

## Not claimed

- That the AI replaces verifiers.
- That a blockchain makes bad source data good: hashes show only that the record did not change after it was recorded.
- That test network tokens are real credits or carry the label of any standard.
- Any accuracy or detection rate of the AI or of the document checks.
- It is not a verification, a certification or a compliance statement. A person decides: the output is a recommendation, not a ruling.
- The data is synthetic and the ledger is a test network.
