# DEPLOY: ClimAudit

Step-by-step guide to publish ClimAudit. Everything runs on the **Hedera testnet** with synthetic data; nothing here costs money. The public link is a **recorded run**: a read-only copy of the web app that replays a real testnet run. It needs no backend and no keys, so nothing secret is ever deployed.

Fees, for reference (read from the official Hedera fee table on 2026-10-16, see `VERIFICATIONS.md` section 1; they are charged in HBAR converted from USD and can change): HCS message submit 0.0008 USD; token create 1.00 USD; fungible token mint 0.001 USD; token transfer 0.001 USD. On the testnet the HBAR is free from the faucet.

## What you need

| Item | Why | Where |
|---|---|---|
| GitHub account | public repository | github.com |
| Vercel account (free plan is enough) | hosts the web app | vercel.com, sign in with GitHub |
| Node.js 20 or newer, Python 3.11 or newer | build and test locally | nodejs.org, python.org |
| Hedera testnet account (only to record a new run) | publish audit hashes and the credit token | portal.hedera.com |

## 1. Check everything locally first

```bash
cd backend
python -m venv .venv
.venv/Scripts/python -m pip install -e ".[dev,geo]"      # Linux/macOS: .venv/bin/python
.venv/Scripts/python -m pytest                            # 265 passed, 2 skipped
cd ../web
npm install
npm run check                                             # types, lint, translations, contrast, 55 tests
npm run build
```

Preview the recorded run exactly as it will be deployed:

```bash
CP_SNAPSHOT=1 npx next start -p 3100                      # PowerShell: $env:CP_SNAPSHOT="1"; npx next start -p 3100
```

Open http://localhost:3100, choose a role, open a batch, and on the Audit page press "Run the check". You should see "Hash chain intact" and "Ledger matches".

## 2. Publish the code on GitHub

1. Make sure no secret is tracked: `git ls-files | grep -E "\.env$"` must print nothing (only `backend/.env.example` is allowed).
2. Commit, then create the repository and push (public, because Devpost requires a public repository):

```bash
git add -A
git commit -m "ClimAudit: evidence checking for biochar carbon credits"
gh repo create climaudit --public --source=. --remote=origin --push
```

After the push, open the repository's **Actions** tab: the workflow `.github/workflows/ci.yml` runs the backend tests, the web checks and build, a dependency audit and a hygiene scan (no `.env` files, no keys, no local paths, no `NEXT_PUBLIC_` variables). Deploy on Vercel only when it is green.

Without the GitHub CLI: create an empty public repository named `climaudit` on github.com, then `git remote add origin https://github.com/<your-user>/climaudit.git` and `git push -u origin main`.

## 3. Deploy the recorded run on Vercel

1. In Vercel choose **Add New, Project**, and import the `climaudit` repository.
2. **Root Directory:** `web`. Framework preset: Next.js (detected). Leave build and install commands as they are.
3. **Environment Variables:** add one, `CP_SNAPSHOT` = `1`, for Production and Preview. Add nothing else: no `CP_API_URL`, no `CP_KEY_*`, nothing starting with `NEXT_PUBLIC_`.
4. Press **Deploy**. When it finishes, open the URL Vercel gives you.

Check the deployed site:

- A banner says "Recorded run, read-only" with the network and the recording date.
- Pick each role; the batch list, the tabs and the Audit page load.
- The Decision and Credit tabs show no action buttons.
- On the Audit page, "Run the check" shows a matching chain.
- `https://<your-site>/api/mode` returns `{"snapshot":true,...}`.

Put the site URL in `submission/DEVPOST.md` (`[DEMO URL]`), and the repository URL in `[REPOSITORY URL]`.

Vercel redeploys on every push to `main`. To change the data the public site shows, record a new run (section 5), commit `web/snapshot/snapshot.json` and push.

## 4. Optional: a custom name

In the Vercel project, Settings, Domains lets you use a free `*.vercel.app` name such as `climaudit-demo`. A custom domain is not needed for the hackathon.

## 5. Record a new run on the testnet (only if you want fresh data)

1. Create a testnet account in the Hedera portal. Copy `backend/.env.example` to `backend/.env` and fill `CP_HEDERA_OPERATOR_ID` and `CP_HEDERA_OPERATOR_KEY` (never commit this file, never paste it into a chat).
2. Install the Hedera extra: `.venv/Scripts/python -m pip install -e ".[dev,geo,hedera]"`.
3. Record: `cd backend && .venv/Scripts/python scripts/make_snapshot.py --ledger direct --out ../web/snapshot/snapshot.json`. It creates a new topic and token, runs the whole lifecycle with synthetic data and writes the file.
4. Look at the result in the explorer: `https://hashscan.io/testnet/topic/<topic id printed>`.
5. Commit the new `snapshot.json` and update the ids in `submission/DEVPOST.md`.

## 6. Optional: run the live app (every action works)

For a demo video or local trials, not for a public link, because a live API would need keys on a server:

```bash
cd backend
.venv/Scripts/python scripts/dev_stack.py                          # in-memory ledger, three demo batches
.venv/Scripts/python scripts/dev_stack.py --ledger direct --fresh-ledger   # publishes to the testnet account in backend/.env
cd ../web && npm run dev                                            # http://localhost:3000
```

`dev_stack.py` writes random demo keys to `web/.env.local` (git-ignored). Delete that file when you stop.

## 7. Optional: Hedera Guardian

Guardian anchors each audit event through a published policy (`backend/guardian/climaudit_audit.policy`). It needs a local Guardian 3.7.1 stack in Docker and a Standard Registry account; see `backend/scripts/guardian_probe.py` and decisions D-155 to D-159 in `DECISIONS-LEDGER.md`. It is not needed for the public link.

## 8. Demo video

Record it from the deployed site: `cd demo && npm install && node record.mjs --base https://<your-site>.vercel.app`. You record the narration (text in `demo/narration/`) and `node assemble.mjs` joins everything. Details in `demo/README.md` and `submission/VIDEO-SCRIPT.md`. Devpost asks for 3 to 5 minutes.

## Security

- Keys and API keys only in environment variables or the git-ignored `.env` and `.env.local`.
- Separate test accounts per role; testnet only.
- The public deployment holds no key and cannot change data (`SNAPSHOT_READ_ONLY`).
- Never print or paste the operator key; rotate it if it was ever exposed.

## Pre-submission checklist

- [ ] Public repository with README and documentation
- [ ] Demo deployed and working (recorded run on the Hedera testnet)
- [ ] Architecture diagram and technical specification (`submission/`)
- [ ] Security and data integrity assessment (`submission/SECURITY-ASSESSMENT.md`)
- [ ] Video of 3 to 5 minutes (the Devpost page and rules say so; aim for about 3:15)
- [ ] Devpost text: track, problem, solution, users, scalability, repository and demo links
- [ ] Trademark check of the name "ClimAudit" in your national register
- [ ] Submitted on Devpost by Oct 24, 6:00 PM CST at the latest (Devpost closes Oct 25, 8:00 AM CST; confirm the date in the Devpost header)
