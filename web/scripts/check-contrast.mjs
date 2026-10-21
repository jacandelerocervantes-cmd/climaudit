// Checks the colour tokens of src/app/globals.css against WCAG 2.2 contrast thresholds, in light and dark mode.
//   node scripts/check-contrast.mjs
// Text pairs need 4.5:1; the accent used as a line, icon or focus ring and the provenance dots need 3:1.
import { readFileSync } from "node:fs";

const css = readFileSync("src/app/globals.css", "utf8");

function block(startMarker) {
  const start = css.indexOf(startMarker);
  const open = css.indexOf("{", start);
  let depth = 0;
  for (let i = open; i < css.length; i += 1) {
    if (css[i] === "{") depth += 1;
    if (css[i] === "}") {
      depth -= 1;
      if (depth === 0) return css.slice(open + 1, i);
    }
  }
  throw new Error(`unterminated block ${startMarker}`);
}

function tokens(text) {
  const out = {};
  for (const m of text.matchAll(/--([a-z-]+):\s*(#[0-9a-fA-F]{6})\s*;/g)) out[m[1]] = m[2];
  return out;
}

const light = tokens(block(":root {"));
const dark = { ...light, ...tokens(block("@media (prefers-color-scheme: dark)")) };

function luminance(hex) {
  const channel = (i) => {
    const v = parseInt(hex.slice(1 + i * 2, 3 + i * 2), 16) / 255;
    return v <= 0.03928 ? v / 12.92 : ((v + 0.055) / 1.055) ** 2.4;
  };
  return 0.2126 * channel(0) + 0.7152 * channel(1) + 0.0722 * channel(2);
}

function ratio(a, b) {
  const [hi, lo] = [luminance(a), luminance(b)].sort((x, y) => y - x);
  return (hi + 0.05) / (lo + 0.05);
}

const TEXT = 4.5;
const GRAPHIC = 3;
const pairs = [
  ["ink", "canvas", TEXT], ["ink", "surface", TEXT], ["ink", "sidebar", TEXT],
  ["muted", "canvas", TEXT], ["muted", "surface", TEXT], ["muted", "sidebar", TEXT],
  ["accent-ink", "accent", TEXT],
  ["accent", "canvas", TEXT], ["accent", "surface", TEXT],
  ["ok-ink", "ok-bg", TEXT], ["warn-ink", "warn-bg", TEXT], ["bad-ink", "bad-bg", TEXT],
  ["info-ink", "info-bg", TEXT], ["synthetic-ink", "synthetic-bg", TEXT],
  ["ink", "range-bg", TEXT],
  ["measured", "surface", GRAPHIC], ["modeled", "surface", GRAPHIC], ["synthetic", "surface", GRAPHIC],
  ["accent", "range-bg", GRAPHIC],
];

let failures = 0;
for (const [mode, set] of [["light", light], ["dark", dark]]) {
  for (const [fg, bg, min] of pairs) {
    const a = set[fg];
    const b = set[bg];
    if (!a || !b) {
      console.error(`missing token in ${mode}: ${fg} or ${bg}`);
      failures += 1;
      continue;
    }
    const r = ratio(a, b);
    if (r < min) {
      console.error(`FAIL ${mode}: ${fg} ${a} on ${bg} ${b} = ${r.toFixed(2)}:1 (needs ${min}:1)`);
      failures += 1;
    }
  }
}
if (failures > 0) process.exit(1);
console.log(`contrast ok: ${pairs.length} pairs x 2 modes`);
