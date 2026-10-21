import { mkdtempSync, rmSync, writeFileSync } from "node:fs";
import { tmpdir } from "node:os";
import { join } from "node:path";
import { NextRequest } from "next/server";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { GET as getMode } from "@/app/api/mode/route";
import { GET, POST } from "@/app/api/cp/[...path]/route";
import { GET as getPersona } from "@/app/api/persona/route";
import { recordedAnswer, snapshotEnabled, type Snapshot } from "@/lib/snapshot";

const ctx = (...path: string[]) => ({ params: Promise.resolve({ path }) });
const request = (url: string, init: { method?: string; cookie?: string; body?: string } = {}) =>
  new NextRequest(`http://localhost${url}`, {
    method: init.method ?? "GET",
    headers: init.cookie ? { cookie: `cp_persona=${init.cookie}` } : {},
    body: init.body,
  });

const snapshot: Snapshot = {
  meta: { generated_at: "2026-10-18T12:00:00Z", ledger_mode: "direct", network: "testnet" },
  roles: {
    verifier: {
      batches: { status: 200, body: [{ batch_id: "b-1" }] },
      "batches/b-1": { status: 200, body: { batch_id: "b-1", state: "VERIFIED" } },
    },
  },
};

let dir = "";
beforeEach(() => {
  dir = mkdtempSync(join(tmpdir(), "cp-snapshot-"));
  const file = join(dir, "snapshot.json");
  writeFileSync(file, JSON.stringify(snapshot));
  vi.stubEnv("CP_SNAPSHOT", "1");
  vi.stubEnv("CP_SNAPSHOT_FILE", file);
});
afterEach(() => {
  vi.unstubAllEnvs();
  vi.restoreAllMocks();
  rmSync(dir, { recursive: true, force: true });
});

describe("snapshot mode", () => {
  it("is on only when CP_SNAPSHOT is 1", () => {
    expect(snapshotEnabled({ CP_SNAPSHOT: "1" })).toBe(true);
    expect(snapshotEnabled({})).toBe(false);
    expect(snapshotEnabled({ CP_SNAPSHOT: "true" })).toBe(false);
  });

  it("looks up a recorded answer by role and path", () => {
    expect(recordedAnswer(snapshot, "verifier", "batches")?.status).toBe(200);
    expect(recordedAnswer(snapshot, "verifier", "nope")).toBeNull();
    expect(recordedAnswer(snapshot, "owner", "batches")).toBeNull();
  });

  it("answers reads from the file without calling any API or needing a key", async () => {
    const upstream = vi.spyOn(globalThis, "fetch");
    const list = await GET(request("/api/cp/batches", { cookie: "verifier" }), ctx("batches"));
    expect(list.status).toBe(200);
    expect(await list.json()).toEqual([{ batch_id: "b-1" }]);
    const one = await GET(request("/api/cp/batches/b-1", { cookie: "verifier" }), ctx("batches", "b-1"));
    expect((await one.json()).state).toBe("VERIFIED");
    expect(upstream).not.toHaveBeenCalled();
  });

  it("refuses every write with SNAPSHOT_READ_ONLY", async () => {
    const upstream = vi.spyOn(globalThis, "fetch");
    const response = await POST(request("/api/cp/batches/b-1/transitions", { method: "POST", cookie: "verifier", body: '{"to":"ISSUED"}' }), ctx("batches", "b-1", "transitions"));
    expect(response.status).toBe(403);
    expect((await response.json()).error.code).toBe("SNAPSHOT_READ_ONLY");
    expect(upstream).not.toHaveBeenCalled();
  });

  it("returns not found for a route that was not recorded, and still needs a persona", async () => {
    const missing = await GET(request("/api/cp/batches/b-9", { cookie: "verifier" }), ctx("batches", "b-9"));
    expect(missing.status).toBe(404);
    const noPersona = await GET(request("/api/cp/batches"), ctx("batches"));
    expect(noPersona.status).toBe(401);
  });

  it("reports every persona as configured and exposes the recording facts", async () => {
    const persona = await getPersona(request("/api/persona", { cookie: "owner" }));
    expect(await persona.json()).toEqual({ role: "owner", configured: true });
    const mode = await (await getMode()).json();
    expect(mode).toEqual({ snapshot: true, generated_at: "2026-10-18T12:00:00Z", ledger_mode: "direct", network: "testnet" });
  });

  it("says it is not a snapshot when the switch is off", async () => {
    vi.stubEnv("CP_SNAPSHOT", "");
    expect(await (await getMode()).json()).toEqual({ snapshot: false });
  });
});
