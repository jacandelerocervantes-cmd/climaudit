import { NextRequest } from "next/server";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { GET, POST } from "@/app/api/cp/[...path]/route";
import { GET as getPersona, POST as setPersona } from "@/app/api/persona/route";

const ctx = (...path: string[]) => ({ params: Promise.resolve({ path }) });
const request = (url: string, init: { method?: string; cookie?: string; body?: string; headers?: Record<string, string> } = {}) =>
  new NextRequest(`http://localhost${url}`, {
    method: init.method ?? "GET",
    headers: { ...(init.cookie ? { cookie: `cp_persona=${init.cookie}` } : {}), ...init.headers },
    body: init.body,
  });

beforeEach(() => {
  vi.stubEnv("CP_API_URL", "http://api.test");
  vi.stubEnv("CP_KEY_VERIFIER", "secret-verifier-key");
});
afterEach(() => {
  vi.unstubAllEnvs();
  vi.restoreAllMocks();
});

describe("same-origin proxy", () => {
  it("forwards an allowed call with the persona's server-side key and never returns the key", async () => {
    const upstream = vi.spyOn(globalThis, "fetch").mockResolvedValue(new Response(JSON.stringify([{ batch_id: "b-1" }]), { status: 200, headers: { "content-type": "application/json" } }));
    const response = await GET(request("/api/cp/batches?limit=5&evil=1", { cookie: "verifier" }), ctx("batches"));
    expect(response.status).toBe(200);
    expect(await response.text()).not.toContain("secret-verifier-key");
    const [url, init] = upstream.mock.calls[0] as [string, RequestInit];
    expect(url).toBe("http://api.test/batches?limit=5");
    expect((init.headers as Record<string, string>).Authorization).toBe("Bearer secret-verifier-key");
  });

  it("passes the idempotency key and the body of a write", async () => {
    const upstream = vi.spyOn(globalThis, "fetch").mockResolvedValue(new Response("{}", { status: 200, headers: { "content-type": "application/json" } }));
    await POST(request("/api/cp/batches/b-1/transitions", { method: "POST", cookie: "verifier", body: '{"to":"VERIFIED"}', headers: { "content-type": "application/json", "idempotency-key": "k-1" } }), ctx("batches", "b-1", "transitions"));
    const [, init] = upstream.mock.calls[0] as [string, RequestInit];
    expect((init.headers as Record<string, string>)["Idempotency-Key"]).toBe("k-1");
    expect(init.method).toBe("POST");
  });

  it("refuses dot segments that could leave the allowed route", async () => {
    const upstream = vi.spyOn(globalThis, "fetch");
    expect((await GET(request("/api/cp/profiles/..", { cookie: "verifier" }), ctx("profiles", ".."))).status).toBe(404);
    expect((await GET(request("/api/cp/profiles/.", { cookie: "verifier" }), ctx("profiles", "."))).status).toBe(404);
    expect(upstream).not.toHaveBeenCalled();
  });

  it("refuses routes outside the allowlist and calls without a persona or key", async () => {
    const upstream = vi.spyOn(globalThis, "fetch");
    expect((await GET(request("/api/cp/health", { cookie: "verifier" }), ctx("health"))).status).toBe(404);
    const noPersona = await GET(request("/api/cp/batches"), ctx("batches"));
    expect(noPersona.status).toBe(401);
    expect((await noPersona.json()).error.code).toBe("AUTH_REQUIRED");
    const noKey = await GET(request("/api/cp/batches", { cookie: "owner" }), ctx("batches"));
    expect(noKey.status).toBe(401);
    expect(upstream).not.toHaveBeenCalled();
  });

  it("reports an unreachable API with its own code the interface can retry", async () => {
    vi.spyOn(globalThis, "fetch").mockRejectedValue(new Error("connect ECONNREFUSED"));
    const response = await GET(request("/api/cp/me", { cookie: "verifier" }), ctx("me"));
    expect(response.status).toBe(503);
    const body = await response.json();
    expect(body.error.code).toBe("API_UNREACHABLE");
    expect(body.error.params.reason).toBe("api_unreachable");
  });
});

describe("persona route", () => {
  it("sets an http-only cookie for a known role and rejects others", async () => {
    const ok = await setPersona(request("/api/persona", { method: "POST", body: '{"role":"verifier"}', headers: { "content-type": "application/json" } }));
    expect(ok.status).toBe(200);
    expect(ok.headers.get("set-cookie")).toMatch(/cp_persona=verifier/i);
    expect(ok.headers.get("set-cookie")).toMatch(/HttpOnly/i);
    expect((await ok.json()).configured).toBe(true);
    const bad = await setPersona(request("/api/persona", { method: "POST", body: '{"role":"extractor"}', headers: { "content-type": "application/json" } }));
    expect(bad.status).toBe(422);
    const current = await getPersona(request("/api/persona", { cookie: "owner" }));
    expect(await current.json()).toEqual({ role: "owner", configured: false });
  });
});
