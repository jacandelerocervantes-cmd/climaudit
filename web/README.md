# ClimAudit web

Next.js (App Router), TypeScript and Tailwind CSS 4. Design: `../FRONTEND-CONCEPTUAL-DESIGN.md` and `../FRONTEND-DESIGN.md`. Decisions: `../DECISIONS-LEDGER.md` D-187 to D-190.

## Run it locally (mode A)

1. In `../backend`, with its `.venv` active: `python scripts/dev_stack.py`. It generates random demo keys, writes them to `web/.env.local` (git-ignored, server side only), starts the API with the in-memory ledger and a temporary database, and seeds three synthetic batches (verified, under review, draft). Leave it running; Ctrl+C stops it.
2. In this folder: `npm install` (first time), then `npm run dev`, and open http://localhost:3000. Choose a role in the sidebar: this is a demo selector that picks which server-side key the proxy uses, not a sign-in.

To run the backend yourself instead, set `CP_API_KEYS` (a JSON object `{"<key>": {"actor_id": "...", "role": "owner|verifier|registry|holder|admin"}}`), start it with `python -m uvicorn climaudit.api.app:app_factory --factory --port 8000`, and copy `env.example` to `.env.local` with the same keys as `CP_KEY_<ROLE>`. Never prefix those variables with `NEXT_PUBLIC_`.

## Checks

`npm run check` runs the type check, lint, the i18n check (every text is extracted; every language must have every key with the same placeholders), the contrast check (WCAG AA for the palette, light and dark) and the tests. After a backend change, regenerate the contract: `python ../backend/scripts/export_openapi.py` then `npm run types`.

## How the pieces fit

- `src/app/api/cp/[...path]/route.ts`: same-origin proxy that forwards only the allowlisted routes (`src/lib/config.ts`) with the persona's key. `tests/contract.test.ts` compares the allowlist with the exported OpenAPI file.
- `src/lib/client/api.ts`: typed fetch with an `Idempotency-Key` on every write and the backend error envelope turned into a typed failure; `src/lib/messages.ts` holds the sentence for every backend error code and state.
- `src/lib/i18n*.ts*`: the key of a text is its English text; backend texts are shown as sent.

## Recorded run (public, read-only)

Set `CP_SNAPSHOT=1` and the app replays `snapshot/snapshot.json` instead of calling the API. The file is a real run on the Hedera testnet, written by `backend/scripts/make_snapshot.py`. Reads are answered per persona from the file, every write returns `SNAPSHOT_READ_ONLY`, and no `CP_API_URL` or `CP_KEY_*` is needed. `CP_SNAPSHOT_FILE` points to another file. See `DEPLOY.md` for how to record and deploy it.

## Not claimed

- That the AI replaces verifiers.
- That a blockchain makes bad source data good: hashes show only that the record did not change after it was recorded.
- That test network tokens are real credits or carry the label of any standard.
- Any accuracy or detection rate of the AI or of the document checks.
- It is not a verification, a certification or a compliance statement. A person decides: the output is a recommendation, not a ruling.
- The data is synthetic and the ledger is a test network.
