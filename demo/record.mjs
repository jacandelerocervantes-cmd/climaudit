// Records one video clip per narration segment from the running web app.
//
//   node record.mjs [--only 03,04] [--base http://localhost:3100] [--headed]
//
// Needs the live stack running first (see ../submission/VIDEO-SCRIPT.md): the API with --ledger direct --fresh-ledger and the
// web app. Some segments change data (accepting a finding, issuing, transferring, retiring), so a full run needs a fresh stack.
// Clips are written to out/clips/<segment>.webm. Nothing here reads or prints a key.
import { existsSync, mkdirSync, readFileSync, renameSync, readdirSync, rmSync } from "node:fs";
import { dirname, join } from "node:path";
import { fileURLToPath } from "node:url";
import { chromium } from "playwright";

const HERE = dirname(fileURLToPath(import.meta.url));
const args = process.argv.slice(2);
const flag = (name, fallback) => (args.includes(name) ? args[args.indexOf(name) + 1] : fallback);
const BASE = flag("--base", "http://localhost:3100");
const ONLY = flag("--only", "").split(",").filter(Boolean);
const HEADED = args.includes("--headed");
// A recorded-run site (CP_SNAPSHOT=1, the public deployment) cannot change anything, so the segments show the recorded result instead of
// clicking the actions. It is detected from /api/mode; --readonly forces it.
async function isReadOnly() {
  if (args.includes("--readonly")) return true;
  try {
    return (await (await fetch(`${BASE}/api/mode`)).json()).snapshot === true;
  } catch {
    return false;
  }
}
const READ_ONLY = await isReadOnly();
const SIZE = { width: 1280, height: 720 };
const OUT = join(HERE, "out");
const ARCH_PNG = join(HERE, "..", "submission", "architecture.png");

// Chromium: the one Playwright installed, or any Chromium given in CP_DEMO_CHROMIUM.
function chromiumPath() {
  if (process.env.CP_DEMO_CHROMIUM) return process.env.CP_DEMO_CHROMIUM;
  const root = join(process.env.LOCALAPPDATA ?? join(process.env.HOME ?? "", ".cache"), "ms-playwright");
  if (!existsSync(root)) return undefined;
  const builds = readdirSync(root).filter((n) => /^chromium-\d+$/.test(n)).sort();
  const latest = builds.at(-1);
  if (!latest) return undefined;
  for (const sub of ["chrome-win64/chrome.exe", "chrome-win/chrome.exe", "chrome-linux/chrome", "chrome-mac/Chromium.app/Contents/MacOS/Chromium"]) {
    const candidate = join(root, latest, sub);
    if (existsSync(candidate)) return candidate;
  }
  return undefined;
}

const wait = (ms) => new Promise((r) => setTimeout(r, ms));

const CURSOR = `
(() => {
  const dot = document.createElement("div");
  dot.style.cssText = "position:fixed;z-index:2147483647;width:18px;height:18px;border-radius:50%;background:rgba(15,118,110,.55);border:2px solid #fff;box-shadow:0 0 0 1px rgba(0,0,0,.35);pointer-events:none;left:-40px;top:-40px;transform:translate(-50%,-50%)";
  const add = () => document.documentElement.appendChild(dot);
  document.documentElement ? add() : document.addEventListener("DOMContentLoaded", add);
  addEventListener("mousemove", (e) => { dot.style.left = e.clientX + "px"; dot.style.top = e.clientY + "px"; }, true);
})();`;

const CARD_STYLE = `
<style>
  html,body{margin:0;height:100%;font-family:system-ui,Segoe UI,sans-serif;background:#0b2f2c;color:#eaf6f4}
  .c{height:100%;display:flex;flex-direction:column;align-items:center;justify-content:center;text-align:center;padding:0 80px}
  h1{font-size:68px;margin:0 0 18px;letter-spacing:.5px} p{font-size:28px;margin:6px 0;color:#bfe3de;max-width:900px}
  small{font-size:20px;color:#8fc5be;margin-top:34px}
</style>`;
const card = (title, lines, foot = "") => `<!doctype html><meta charset="utf-8">${CARD_STYLE}<div class="c"><h1>${title}</h1>${lines.map((l) => `<p>${l}</p>`).join("")}${foot ? `<small>${foot}</small>` : ""}</div>`;

async function open(browser, name, role) {
  const dir = join(OUT, "raw", name);
  rmSync(dir, { recursive: true, force: true });
  mkdirSync(dir, { recursive: true });
  const context = await browser.newContext({ viewport: SIZE, deviceScaleFactor: 1, recordVideo: { dir, size: SIZE } });
  await context.addInitScript(CURSOR);
  if (role) await context.addCookies([{ name: "cp_persona", value: role, url: BASE }]);
  const page = await context.newPage();
  return { context, page, dir };
}

async function close({ context, page, dir }, name) {
  const video = page.video();
  await context.close();
  const file = (await video.path()) ?? join(dir, readdirSync(dir)[0]);
  mkdirSync(join(OUT, "clips"), { recursive: true });
  const target = join(OUT, "clips", `${name}.webm`);
  rmSync(target, { force: true });
  renameSync(file, target);
  console.log(`clip ${name}`);
}

// Move the pointer to an element the way a person would, then act on it.
async function point(page, locator, hold = 500) {
  await locator.scrollIntoViewIfNeeded();
  const box = await locator.boundingBox();
  if (box) await page.mouse.move(box.x + box.width / 2, box.y + box.height / 2, { steps: 25 });
  await wait(hold);
}
async function click(page, locator, hold = 500) {
  await point(page, locator, hold);
  await locator.click();
}
async function type(page, locator, text) {
  await click(page, locator, 300);
  await locator.pressSequentially(text, { delay: 55 });
}
async function scrollBy(page, dy, ms = 1400) {
  await page.mouse.wheel(0, dy);
  await wait(ms);
}

async function getJson(context, path) {
  const response = await context.request.get(`${BASE}/api/cp/${path}`);
  return response.json();
}
async function findBatch(context, state) {
  const batches = await getJson(context, "batches");
  const hit = batches.find((b) => b.state === state);
  if (!hit) throw new Error(`no batch in state ${state}; the stack needs to be fresh`);
  return hit.batch_id;
}
const tab = (page, name) => page.getByRole("tab", { name, exact: true });
async function enterAs(page, label) {
  await page.goto(`${BASE}/`);
  await click(page, page.getByRole("button", { name: new RegExp(`^(Enter|Continue) as ${label}$`) }), 700);
  await page.waitForURL("**/batches");
  await wait(1200);
}
async function openBatch(page, id) {
  await click(page, page.getByRole("link", { name: id }).first(), 600);
  await page.waitForURL(`**/batches/${id}`);
  await wait(1200);
}

// Shortest length of each clip in seconds, about what the narration needs. The assembler fits the clip to the audio anyway.
const MIN_SECONDS = { "01-intro": 22, "02-architecture": 27, "03-evidence": 26, "04-report": 26, "05-issue": 12, "06-holder": 14, "07-audit": 20, "08-scale": 24, "09-closing": 12 };

const SEGMENTS = {
  "01-intro": async ({ page }) => {
    await page.setContent(card("ClimAudit", ["Checking the evidence behind biochar carbon credits"], "Synthetic data. Test network only."));
    await wait(3500);
    await page.goto(`${BASE}/`);
    await wait(1500);
    for (const role of ["Project owner", "Verifier", "Registry"]) await point(page, page.getByRole("heading", { name: role, exact: true }), 1100);
    await wait(1500);
  },

  "02-architecture": async ({ page }) => {
    const png = readFileSync(ARCH_PNG).toString("base64");
    await page.setContent(`<!doctype html><meta charset="utf-8"><style>html,body{margin:0;height:100%;background:#fff;display:flex;align-items:center;justify-content:center}img{max-width:100%;max-height:100%}</style><img src="data:image/png;base64,${png}">`);
    await wait(2500);
    await page.mouse.move(640, 360, { steps: 5 });
    await wait(22000);
  },

  "03-evidence": async ({ page, context }) => {
    const id = await findBatch(context, "UNDER_REVIEW");
    await enterAs(page, "Verifier");
    await openBatch(page, id);
    await wait(2500);
    await click(page, tab(page, "Evidence"));
    await wait(2000);
    await scrollBy(page, 420);
    await scrollBy(page, 420);
    await click(page, tab(page, "Findings"));
    await wait(2500);
    await scrollBy(page, 360);
    const card = page.locator("li", { hasText: "Transport distance is exactly at the threshold" });
    if (READ_ONLY) {
      await point(page, card, 1500); // the recorded run already holds the verifier's accepted finding and its reason
      await wait(4000);
      return;
    }
    await click(page, card.getByRole("button", { name: "Accept with a reason" }), 900);
    await type(page, card.getByLabel("Reason (required, recorded in the audit trail)"), "Checked the freight invoice: the leg is 200 km.");
    await wait(900);
    await click(page, card.getByRole("button", { name: "Accept finding" }), 700);
    await wait(3500);
  },

  "04-report": async ({ page, context }) => {
    const id = await findBatch(context, "UNDER_REVIEW");
    await page.goto(`${BASE}/batches/${id}?tab=report`);
    await wait(3500);
    await scrollBy(page, 300, 2400);
    await scrollBy(page, 300, 2400);
    await wait(1500);
  },

  "05-issue": async ({ page, context }) => {
    if (READ_ONLY) {
      const issued = await findBatch(context, "PARTIALLY_RETIRED");
      await enterAs(page, "Registry");
      await openBatch(page, issued);
      await click(page, tab(page, "Decision"));
      await wait(3000);
      await click(page, tab(page, "Credit"));
      await wait(4000);
      await point(page, page.getByRole("link", { name: /^0\.0\.\d+@/ }).first(), 1500); // the mint transaction
      await wait(3000);
      return;
    }
    const id = await findBatch(context, "VERIFIED");
    await enterAs(page, "Registry");
    await openBatch(page, id);
    await click(page, tab(page, "Decision"));
    await wait(2500);
    await click(page, page.getByRole("button", { name: "Issue credits" }), 900);
    await wait(2500);
    await click(page, page.getByRole("button", { name: "Confirm", exact: true }), 800);
    await page.getByText(/Issued .* credit units/).waitFor({ timeout: 90000 });
    await wait(3500);
    await click(page, tab(page, "Credit"));
    await wait(3500);
  },

  "06-holder": async ({ page, context }) => {
    if (READ_ONLY) {
      const issued = await findBatch(context, "PARTIALLY_RETIRED");
      await enterAs(page, "Credit holder");
      await openBatch(page, issued);
      await click(page, tab(page, "Credit"));
      await wait(4000);
      await scrollBy(page, 420, 3500);
      await scrollBy(page, 420, 3500);
      return;
    }
    const id = await findBatch(context, "ISSUED");
    await enterAs(page, "Project owner");
    await openBatch(page, id);
    await click(page, tab(page, "Credit"));
    await wait(2500);
    await type(page, page.locator("#transfer-to"), "buyer-1");
    await type(page, page.locator("#transfer-units"), "5000");
    await click(page, page.getByRole("button", { name: "Transfer", exact: true }), 700);
    await page.getByText(/Transferred .* units to/).waitFor({ timeout: 90000 });
    await wait(2500);
    await enterAs(page, "Credit holder");
    await openBatch(page, id);
    await click(page, tab(page, "Credit"));
    await wait(2200);
    await type(page, page.locator("#retire-units"), "1200");
    await type(page, page.locator("#retire-who"), "Demo Foods Ltd");
    await click(page, page.getByRole("button", { name: "Review retirement" }), 700);
    await wait(1500);
    await click(page, page.getByRole("button", { name: "Confirm", exact: true }), 800);
    await page.getByText(/Retired .* units for/).waitFor({ timeout: 90000 });
    await wait(3000);
  },

  "07-audit": async ({ page, context }) => {
    const id = await findBatch(context, "PARTIALLY_RETIRED");
    await enterAs(page, "Registry");
    await openBatch(page, id);
    await click(page, tab(page, "Audit"));
    await wait(3000);
    await scrollBy(page, 420, 2000);
    await page.goto(`${BASE}/audit`);
    await wait(2000);
    await click(page, page.getByRole("button", { name: "Run the check" }), 800);
    await page.getByText("Ledger matches").waitFor({ timeout: 90000 });
    await wait(3500);
    await page.goBack();
    await wait(1200);
    const href = await page.locator('a[href*="hashscan.io"]').first().getAttribute("href");
    if (href) {
      await page.goto(href, { waitUntil: "domcontentloaded" });
      await wait(4000);
      const reject = page.getByRole("button", { name: "Reject" });
      if (await reject.isVisible().catch(() => false)) await reject.click(); // decline the explorer's cookies
      await wait(2500);
      const messages = page.getByText("Messages", { exact: true }).first();
      if (await messages.isVisible().catch(() => false)) await click(page, messages, 600);
      await wait(6000);
    }
  },

  "08-scale": async ({ page }) => {
    await enterAs(page, "Verifier");
    await click(page, page.getByRole("link", { name: "Method", exact: true }), 700);
    await page.waitForURL("**/method");
    await wait(3000);
    await scrollBy(page, 700, 3000);
    await scrollBy(page, 600, 3000);
    await click(page, page.getByRole("link", { name: "About", exact: true }), 700);
    await wait(3500);
    await scrollBy(page, 500, 3000);
  },

  "09-closing": async ({ page }) => {
    await page.setContent(card("ClimAudit", ["Deterministic checking. A human decision. A record you can verify yourself."], "Synthetic data. Test network only."));
    await wait(8000);
  },
};

const browser = await chromium.launch({ headless: !HEADED, ...((process.env.CP_DEMO_CHANNEL ?? (process.platform === "win32" ? "msedge" : "")) ? { channel: process.env.CP_DEMO_CHANNEL ?? "msedge" } : { executablePath: chromiumPath() }), args: [`--window-size=${SIZE.width},${SIZE.height}`] });
let failed = false;
for (const [name, run] of Object.entries(SEGMENTS)) {
  if (ONLY.length && !ONLY.some((n) => name.startsWith(n))) continue;
  const session = await open(browser, name, ["01-intro", "02-architecture", "09-closing"].includes(name) ? null : "admin");
  const started = Date.now();
  try {
    await run(session);
    await wait(Math.max(0, (MIN_SECONDS[name] ?? 0) * 1000 - (Date.now() - started)));
  } catch (error) {
    failed = true;
    console.error(`segment ${name} failed: ${String(error.message).split("\n")[0]}`);
    await session.page.screenshot({ path: join(OUT, `failed-${name}.png`) }).catch(() => undefined);
  }
  await close(session, name);
}
await browser.close();
process.exit(failed ? 1 : 0);
