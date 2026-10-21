// Takes the gallery screenshots for the Devpost project page (3:2, 1500x1000) from a running ClimAudit site.
//
//   node gallery.mjs [--base https://climaudit.vercel.app]
//
// Works on the recorded-run site, which is read-only. Writes out/gallery/NN-name.png.
import { mkdirSync } from "node:fs";
import { dirname, join } from "node:path";
import { fileURLToPath } from "node:url";
import { chromium } from "playwright";

const HERE = dirname(fileURLToPath(import.meta.url));
const args = process.argv.slice(2);
const BASE = args.includes("--base") ? args[args.indexOf("--base") + 1] : "https://climaudit.vercel.app";
const OUT = join(HERE, "out", "gallery");
mkdirSync(OUT, { recursive: true });
const wait = (ms) => new Promise((r) => setTimeout(r, ms));

const browser = await chromium.launch({ channel: process.platform === "win32" ? "msedge" : undefined });
const context = await browser.newContext({ viewport: { width: 1500, height: 1000 }, deviceScaleFactor: 1 });
await context.addCookies([{ name: "cp_persona", value: "verifier", url: BASE }]);
const page = await context.newPage();

async function shot(name) {
  await wait(1500);
  await page.screenshot({ path: join(OUT, `${name}.png`) });
  console.log(name);
}
async function batchId(state) {
  const list = await (await context.request.get(`${BASE}/api/cp/batches`)).json();
  return list.find((b) => b.state === state).batch_id;
}
async function as(role) {
  await context.addCookies([{ name: "cp_persona", value: role, url: BASE }]);
}

await page.goto(`${BASE}/`);
await shot("01-start-page");

const review = await batchId("UNDER_REVIEW");
await page.goto(`${BASE}/batches/${review}`);
await shot("02-batch-overview-range");

await page.goto(`${BASE}/batches/${review}?tab=evidence`);
await shot("03-evidence");

await page.goto(`${BASE}/batches/${review}?tab=findings`);
await page.mouse.wheel(0, 330);
await shot("04-findings-accepted-with-reason");

await page.goto(`${BASE}/batches/${review}?tab=report`);
await page.mouse.wheel(0, 120);
await shot("05-report-calculation");

await as("registry");
const issued = await batchId("PARTIALLY_RETIRED");
await page.goto(`${BASE}/batches/${issued}?tab=credit`);
await shot("06-credit-token-balances");

await page.goto(`${BASE}/batches/${issued}?tab=audit`);
await shot("07-audit-trail-events");

await page.goto(`${BASE}/audit`);
await page.getByRole("button", { name: "Run the check" }).click();
await page.getByText("Ledger matches").waitFor();
await shot("08-audit-check-ledger-matches");

await page.goto(`${BASE}/method`);
await shot("09-method-parameters");

await browser.close();
