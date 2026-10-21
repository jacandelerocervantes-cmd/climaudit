// Interface translations: extract the keys from the source, or check the locale files against them.
//
//   node scripts/i18n.mjs extract   writes src/lib/locales/_keys.json (every English text shown through t() or msg())
//   node scripts/i18n.mjs check     fails if a locale file misses a key, holds an unknown key, or changes a {placeholder}
//
// The key of a text is the English text itself. Only literals in double quotes are read; a text built at run time must be
// declared with msg() somewhere (see src/lib/messages.ts). Backend texts are not translated: they are shown as sent.
import { readFileSync, readdirSync, statSync, writeFileSync, existsSync } from "node:fs";
import { join } from "node:path";

const SRC = "src";
const LOCALES = join(SRC, "lib", "locales");
const KEYS_FILE = join(LOCALES, "_keys.json");
// Languages with a dictionary file (English, the default, has none). Add a code here and a `src/lib/locales/<code>.json`
// file to add a language.
const CODES = ["es"];

function walk(dir) {
  return readdirSync(dir).flatMap((name) => {
    const path = join(dir, name);
    if (statSync(path).isDirectory()) return name === "locales" ? [] : walk(path);
    return /\.(ts|tsx)$/.test(name) && !name.endsWith("api-types.ts") ? [path] : [];
  });
}

export function extractKeys() {
  const found = new Set();
  const re = /\b(?:t|msg)\(\s*"((?:[^"\\\n]|\\.)*)"/g;
  for (const file of walk(SRC)) {
    const text = readFileSync(file, "utf8");
    for (const m of text.matchAll(re)) found.add(JSON.parse(`"${m[1]}"`));
  }
  return [...found].sort();
}

const placeholders = (text) => [...text.matchAll(/\{(\w+)\}/g)].map((m) => m[1]).sort().join(",");

function check() {
  const keys = extractKeys();
  let failures = 0;
  for (const code of CODES) {
    const file = join(LOCALES, `${code}.json`);
    if (!existsSync(file)) {
      console.error(`missing locale file ${file}`);
      failures += 1;
      continue;
    }
    const dict = JSON.parse(readFileSync(file, "utf8"));
    for (const key of keys) {
      if (!(key in dict)) {
        console.error(`${code}: missing key "${key}"`);
        failures += 1;
      } else if (placeholders(key) !== placeholders(dict[key])) {
        console.error(`${code}: placeholders differ for "${key}"`);
        failures += 1;
      }
    }
    for (const key of Object.keys(dict)) {
      if (!keys.includes(key)) {
        console.error(`${code}: unknown key "${key}"`);
        failures += 1;
      }
    }
  }
  if (failures > 0) process.exit(1);
  console.log(`i18n ok: ${keys.length} keys x ${CODES.length} language(s)`);
}

const command = process.argv[2];
if (command === "extract") {
  const keys = extractKeys();
  writeFileSync(KEYS_FILE, `${JSON.stringify(keys, null, 2)}\n`);
  console.log(`wrote ${keys.length} keys to ${KEYS_FILE}`);
} else if (command === "check") {
  check();
} else {
  console.error("usage: node scripts/i18n.mjs extract|check");
  process.exit(2);
}
