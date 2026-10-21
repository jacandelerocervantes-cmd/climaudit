# Demo video

The video is made from two things: clips recorded from the running web app (`record.mjs`) and the narration audio, which
the author makes with a text-to-speech service such as ElevenLabs (`narration/*.txt` is the text). `assemble.mjs` joins them.

## 1. Narration (author)

Each file in `narration/` is one segment. Paste its text into the voice service, pick one voice for all segments, and save
the result as `audio/<same name>.mp3` (for example `audio/03-evidence.mp3`). The nine segments add up to about 3:00 of speech, which makes a video of about 3:30 with the pauses (Devpost asks for 3 to 5 minutes).
If a sentence needs a different wording, edit the text file first; the captions are made from it.

## 2. Clips

Record them from the deployed demo (a read-only recorded run, so no keys and no data change):

```bash
cd demo
npm install
node record.mjs --base https://<your-site>.vercel.app        # all nine segments, written to out/clips/*.webm
node record.mjs --base https://<your-site>.vercel.app --only 03,05   # redo some
```

In that mode the segments show the recorded results (the accepted finding, the minted credit, the balances, the retirement, the audit check) instead of clicking the actions. To test locally first: `cd web && npm run build && CP_SNAPSHOT=1 npx next start -p 3100`, then `node record.mjs`.

To record the clicks themselves on a live stack instead (every action works, needs a fresh stack because some segments change data):

```bash
cd backend && .venv/Scripts/python scripts/dev_stack.py --ledger direct --fresh-ledger
cd ../web && npm run build && npx next start -p 3100            # in another terminal, without CP_SNAPSHOT
cd ../demo && node record.mjs
```

On Windows the recorder drives the installed Edge; set `CP_DEMO_CHANNEL=chrome` or `CP_DEMO_CHROMIUM=<path>` to use another browser.

## 3. Assemble

```bash
node assemble.mjs          # needs audio/*.mp3 and ffmpeg; --silent builds a preview without audio
```

Writes `out/climaudit-demo.mp4` and `out/climaudit-demo.srt` (English captions to upload with the video). A clip shorter
than its audio is held on its last frame, a longer one is sped up (at most 2.2 times) or cut. The script warns if the total is
under 3:00 or over 5:00. Everything on screen is synthetic data on the Hedera test network; no key appears in the clips.
