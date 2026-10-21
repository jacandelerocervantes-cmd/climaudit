import { readFileSync } from "node:fs";
import { describe, expect, it } from "vitest";
import { isAllowed, isRole, keyFor, ROLES } from "@/lib/config";
import { KIND_LABELS } from "@/lib/evidence-labels";
import { ERROR_MESSAGES, STATE_LABELS } from "@/lib/messages";

type OpenApi = { paths: Record<string, Record<string, unknown>> };
const openapi = JSON.parse(readFileSync("openapi/climaudit.openapi.json", "utf8")) as OpenApi;

describe("proxy allowlist against the backend contract", () => {
  it("covers every route of the API except the health check, with the right methods", () => {
    const missing: string[] = [];
    for (const [path, methods] of Object.entries(openapi.paths)) {
      if (path === "/health") continue;
      for (const method of Object.keys(methods)) {
        const concrete = path.replace(/^\//, "").replace(/\{(\w+)\}/g, (_m, name: string) => (name === "year" ? "2026" : name === "profile_id" ? "VM0044@1.2" : "abc123"));
        if (!isAllowed(method.toUpperCase(), concrete)) missing.push(`${method.toUpperCase()} ${path}`);
      }
    }
    expect(missing).toEqual([]);
  });

  it("does not forward anything else", () => {
    expect(isAllowed("GET", "health")).toBe(false);
    expect(isAllowed("DELETE", "batches/abc")).toBe(false);
    expect(isAllowed("GET", "batches/../me")).toBe(false);
    expect(isAllowed("GET", "batches/abc/../../etc")).toBe(false);
    expect(isAllowed("POST", "batches/abc/issue/extra")).toBe(false);
    expect(isAllowed("GET", "http://evil.test/me")).toBe(false);
    expect(isAllowed("PUT", "batches")).toBe(false);
  });

  it("every API error code and state has a sentence for the interface", () => {
    const errors = readFileSync("../backend/src/climaudit/errors.py", "utf8");
    const codes = [...errors.matchAll(/^\s+"([A-Z_]+)":\s*\d+,/gm)].map((m) => m[1] as string);
    expect(codes.length).toBeGreaterThan(15);
    expect(codes.filter((c) => !(c in ERROR_MESSAGES))).toEqual([]);
    const states = readFileSync("../backend/src/climaudit/states.py", "utf8");
    const stateNames = new Set([...states.matchAll(/\("([A-Z_]+)",\s*"([A-Z_]+)"\)/g)].flatMap((m) => [m[1] as string, m[2] as string]));
    expect([...stateNames].filter((s) => !(s in STATE_LABELS))).toEqual([]);
  });
});

describe("evidence vocabulary", () => {
  it("has a plain name for every evidence kind of the backend", () => {
    const source = readFileSync("../backend/src/climaudit/evidence.py", "utf8");
    const kinds = [...source.matchAll(/^ {4}"([a-z0-9_]+)": _k\(/gm)].map((m) => m[1] as string);
    expect(kinds.length).toBeGreaterThan(40);
    expect(kinds.filter((k) => !(k in KIND_LABELS))).toEqual([]);
    expect(Object.keys(KIND_LABELS).filter((k) => !kinds.includes(k))).toEqual([]);
  });
});

describe("demo personas", () => {
  it("recognises only the known roles", () => {
    expect(ROLES.every((r) => isRole(r))).toBe(true);
    expect(isRole("extractor")).toBe(false);
    expect(isRole(undefined)).toBe(false);
  });

  it("reads the demo key of a role from the server environment only", () => {
    expect(keyFor("owner", { CP_KEY_OWNER: " k-owner " })).toBe("k-owner");
    expect(keyFor("owner", { NEXT_PUBLIC_CP_KEY_OWNER: "leak" })).toBeUndefined();
    expect(keyFor("verifier", { CP_KEY_VERIFIER: "  " })).toBeUndefined();
  });
});
