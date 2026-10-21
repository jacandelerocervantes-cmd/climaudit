// Joins the recorded clips and the narration audio into one video, and writes English captions.
//
//   node assemble.mjs [--silent]
//
// Inputs:  out/clips/<NN-name>.webm (from record.mjs) and audio/<NN-name>.mp3|wav|m4a (the narration of narration/<NN-name>.txt,
//          made with a text-to-speech service). With --silent a segment without audio keeps its clip length and has no sound.
// Outputs: out/climaudit-demo.mp4 (H.264 + AAC, 1280x720) and out/climaudit-demo.srt.
// Each segment is as long as its audio plus a short pause: a clip that is shorter is held on its last frame, a clip that is a
// little longer is sped up, and a much longer one is cut. Needs ffmpeg and ffprobe on the PATH.
import { execFileSync } from "node:child_process";
import { existsSync, mkdirSync, readFileSync, readdirSync, writeFileSync } from "node:fs";
import { dirname, join } from "node:path";
import { fileURLToPath } from "node:url";

const HERE = dirname(fileURLToPath(import.meta.url));
const SILENT = process.argv.includes("--silent");
const OUT = join(HERE, "out");
const PAUSE = 0.5; // seconds of quiet after each segment's narration
const MAX_SPEEDUP = 2.2;

const run = (cmd, args) => execFileSync(cmd, args, { encoding: "utf8", stdio: ["ignore", "pipe", "pipe"] });
const duration = (file) => Number(run("ffprobe", ["-v", "error", "-show_entries", "format=duration", "-of", "csv=p=0", file]).trim());
const fmt = (s) => {
  const ms = Math.round(s * 1000);
  const p = (n, w) => String(n).padStart(w, "0");
  return `${p(Math.floor(ms / 3600000), 2)}:${p(Math.floor(ms / 60000) % 60, 2)}:${p(Math.floor(ms / 1000) % 60, 2)},${p(ms % 1000, 3)}`;
};

const names = readdirSync(join(HERE, "narration")).filter((f) => f.endsWith(".txt")).map((f) => f.replace(/\.txt$/, "")).sort();
const parts = join(OUT, "parts");
mkdirSync(parts, { recursive: true });

let clock = 0;
let cue = 1;
let srt = "";
const files = [];
for (const name of names) {
  const clip = join(OUT, "clips", `${name}.webm`);
  if (!existsSync(clip)) throw new Error(`missing clip ${clip}; run record.mjs first`);
  const audio = ["mp3", "wav", "m4a", "ogg"].map((e) => join(HERE, "audio", `${name}.${e}`)).find(existsSync);
  if (!audio && !SILENT) throw new Error(`missing audio for ${name} (audio/${name}.mp3); add it or use --silent`);
  const tv = duration(clip);
  const ta = audio ? duration(audio) : tv;
  const target = audio ? ta + PAUSE : tv;

  let vfilter = "scale=1280:720,fps=25,format=yuv420p";
  if (tv > target) {
    const speed = tv / target;
    vfilter = speed <= MAX_SPEEDUP ? `setpts=PTS/${speed.toFixed(4)},${vfilter}` : vfilter; // beyond that the clip is cut by -t
  } else if (tv < target) {
    vfilter = `tpad=stop_mode=clone:stop_duration=${(target - tv + 0.1).toFixed(3)},${vfilter}`;
  }
  const part = join(parts, `${name}.mp4`);
  const input = audio ? ["-i", clip, "-i", audio] : ["-i", clip, "-f", "lavfi", "-i", "anullsrc=r=44100:cl=stereo"];
  run("ffmpeg", ["-v", "error", "-y", ...input, "-vf", vfilter, "-af", "apad,aresample=44100", "-t", target.toFixed(3), "-r", "25", "-c:v", "libx264", "-preset", "medium", "-crf", "20", "-c:a", "aac", "-b:a", "160k", "-ac", "2", "-shortest", part]);
  files.push(part);

  // Captions: one cue per sentence, timed by its share of the narration.
  const text = readFileSync(join(HERE, "narration", `${name}.txt`), "utf8").trim();
  const sentences = text.match(/[^.!?]+[.!?]+/g)?.map((s) => s.trim()) ?? [text];
  const total = sentences.reduce((n, s) => n + s.length, 0);
  let at = clock;
  for (const sentence of sentences) {
    const length = (sentence.length / total) * ta;
    srt += `${cue++}\n${fmt(at)} --> ${fmt(at + length)}\n${sentence}\n\n`;
    at += length;
  }
  clock += target;
  console.log(`${name}: clip ${tv.toFixed(1)} s, audio ${audio ? ta.toFixed(1) : "none"} s, segment ${target.toFixed(1)} s`);
}

const list = join(parts, "list.txt");
writeFileSync(list, files.map((f) => `file '${f.replaceAll("\\", "/")}'`).join("\n") + "\n", "utf8");
const final = join(OUT, "climaudit-demo.mp4");
run("ffmpeg", ["-v", "error", "-y", "-f", "concat", "-safe", "0", "-i", list, "-c", "copy", "-movflags", "+faststart", final]);
writeFileSync(join(OUT, "climaudit-demo.srt"), srt, "utf8");
console.log(`wrote ${final} (${clock.toFixed(1)} s)${clock < 180 || clock > 300 ? "  WARNING: the Devpost page asks for a video of 3 to 5 minutes" : ""}`);
