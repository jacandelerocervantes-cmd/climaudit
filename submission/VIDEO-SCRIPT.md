# Demo video script: ClimAudit (3 to 5 minutes)

Format: screen recording of the web app with voice-over. The clips are recorded by `demo/record.mjs`, the author makes the narration audio from `demo/narration/*.txt` with a text-to-speech service, and `demo/assemble.mjs` joins them (see `demo/README.md`); the table below is the storyboard and the text of the segments. The Devpost page asks for a video of 3 to 5 minutes (an earlier note said 3 minutes or less; the Devpost page is the one that counts), so the target is about 3:15. Voice-over is about 130 words per minute. The author records it; nothing is posted by an agent.

The video is recorded on the **deployed demo** (the Vercel site, a read-only recorded run of a real Hedera testnet run), so every action in it (accepting a finding, issuing, transferring, retiring) is shown through its recorded result, not clicked. The recorder detects that mode from `/api/mode`. A live local stack is only needed if you want the clicks themselves (see `demo/README.md`).

## Before recording (checklist)

1. Deploy the demo from GitHub on Vercel with `CP_SNAPSHOT=1` (see `DEPLOY.md`, section 3) and open it once to check the banner and the Audit check.
2. Record the clips from that site: `cd demo && npm install && node record.mjs --base https://<your-site>.vercel.app`. The clips are written to `demo/out/clips/`.
3. Open the HashScan topic of the recorded run (`topic_id` in `web/snapshot/snapshot.json`, also in `submission/DEVPOST.md`) so you know it loads.
4. Show only synthetic data. No keys and no `.env` contents are ever on screen: the deployed site holds none.

## Timeline

| Time | On screen | Voice-over |
|---|---|---|
| 0:00 to 0:20 | Title card "ClimAudit", then the start page (role cards). | "A biochar carbon credit is only as good as its evidence. Lab reports, production logs and freight invoices are checked by hand, and a missing moisture correction, a typo, or the same field sold twice can inflate a claim. ClimAudit makes that checking reproducible and its record public." |
| 0:20 to 0:42 | The architecture diagram, highlighting boxes in order: sanitizer, optional AI, rules, deterministic calculation, human verifier, ledger. | "A project submits a batch. A sanitizer strips hidden text from documents. An optional AI module can only propose values, each with a verbatim quote that must really be in the document, and a person confirms it. Rules run, then a deterministic calculation of Verra VM0044. A human verifier decides. The AI never approves or issues. Only hashes go to Hedera." |
| 0:42 to 1:08 | "Enter as Verifier", open the batch under review: Evidence (quotes), then Findings, ending on the finding accepted with a written reason. | "I enter as the verifier and open a batch under review. Each value of the evidence shows the quote it came from. The findings come from rules, not from the AI. This one sits exactly at a threshold, so the verifier accepted it with a written reason, and that reason is part of the audit trail." |
| 1:08 to 1:30 | Report tab: the range bar and the calculation ladder. | "The calculation returns a range, two hundred fifty thousand seven hundred twenty-eight to two hundred seventy-one thousand six hundred fourteen kilograms of CO2e, central two hundred sixty-one thousand sixty-seven, against a claim of three hundred thousand. Only the lower bound can be issued, never more than the claim." |
| 1:30 to 1:50 | "Enter as Registry", open the issued batch: Decision tab, then Credit tab, pointing at the mint transaction. | "Now a verified batch. The registry issued its credits as a token on Hedera, one unit per kilogram. Here is the mint transaction, a public record anyone can open." |
| 1:50 to 2:10 | "Enter as Credit holder", Credit tab: balances and the retirement for a named beneficiary. | "The project owner transferred some credits to a buyer, and the buyer retired part of them for a named beneficiary. Balances and retirements are listed here. Retired credits cannot be sold again." |
| 2:10 to 2:35 | Audit tab (events and hashes), then the Audit page "Run the check" (the recorded result), then the topic page on HashScan, Messages tab. | "Every step is a hash-chained audit event published on a Hedera topic. This is the check made at the end of the run: it recomputed every hash and compared the chain with the public ledger, and they matched. Anyone can read these messages on HashScan without trusting our software." |
| 2:35 to 3:00 | Web app, Method page then About page: the methodology is a data profile, so a new methodology or credit type is a new profile. | "The methodology is data, not code. Verra VM0044 is one profile, with every parameter tied to its page in the source document. A new methodology, or a new kind of environmental credit, is a new profile with the same evidence checks, the same human decision and the same public trail. That is how this approach can grow beyond biochar." |
| 3:00 to 3:15 | Closing card: "Synthetic data. Testnet only. Human verifier decides." plus repository URL. | "All data is synthetic and testnet only. The point: deterministic checking, a human decision, and a record you can verify yourself." |

Optional segments if there is time left (each about 12 seconds): the double-counting refusal (submit the same parcel again; the guard answers with an overlap error, shown by `python scripts/demo_flow.py` step 6), and the Guardian policy page on `http://localhost:3000` of the Guardian stack, anchored through `CP_LEDGER_MODE=guardian`.

## Narration word count

About 345 words, roughly 2:45 of speech at 130 words per minute inside a 3:15 timeline, which leaves pauses for clicks. If the first take runs long, shorten the architecture segment first.

## Claims to avoid in the video (from `RULES.md`)

- Do not say the AI replaces verifiers, that the tokens are real credits, that the blockchain prevents fraud before ingestion, or give any detection percentage.
- Say "synthetic" and "testnet" on screen at least once.
- Every number spoken must match what the screen shows in the recorded run. If you re-record with other data, update the numbers in the narration.

## For your review

1. Confirm whether to show Guardian live (adds risk if the local containers are slow); the script works without it.
2. After the final take, check the transaction ids shown are visible long enough to read and that no key or `.env` content appears.
3. Add captions (English) for accessibility if the platform allows.
