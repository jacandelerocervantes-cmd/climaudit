/** Server-side configuration and the proxy allowlist. Importable from server and client code; reads no secret by itself. */

export const ROLES = ["owner", "verifier", "registry", "holder", "admin"] as const;
export type Role = (typeof ROLES)[number];

export const PERSONA_COOKIE = "cp_persona";

export function isRole(value: unknown): value is Role {
  return typeof value === "string" && (ROLES as readonly string[]).includes(value);
}

export function apiBase(env: Record<string, string | undefined> = process.env): string {
  return (env.CP_API_URL ?? "http://127.0.0.1:8000").replace(/\/+$/, "");
}

/** The demo key of a persona, from a server-side environment variable (never one exposed to the browser). */
export function keyFor(role: Role, env: Record<string, string | undefined> = process.env): string | undefined {
  const value = env[`CP_KEY_${role.toUpperCase()}`];
  return value && value.trim() ? value.trim() : undefined;
}

const ID = "[A-Za-z0-9_-]{1,64}";
const REF = "[A-Za-z0-9_@.-]{1,64}";

/** The only routes the proxy forwards: exactly the API of the backend, nothing else, so it is not an open relay. */
const ALLOWED: Record<string, RegExp[]> = {
  GET: [
    /^(me|config|catalog|projects|batches|credits|profiles)$/,
    new RegExp(`^profiles/${REF}$`),
    new RegExp(`^batches/${ID}(/(report|findings|documents))?$`),
    new RegExp(`^credits/${ID}$`),
    /^audit\/verify$/,
    new RegExp(`^audit/${ID}$`),
    new RegExp(`^documents/${ID}/text$`),
  ],
  POST: [
    /^(projects|batches)$/,
    new RegExp(`^projects/${ID}/facilities$`),
    new RegExp(`^batches/${ID}/(documents|evidence|transitions|verification|issue|findings/override)$`),
    new RegExp(`^batches/${ID}/evidence/${ID}/confirm$`),
    new RegExp(`^credits/${ID}/(transfer|retire)$`),
  ],
  PUT: [new RegExp(`^batches/${ID}$`), new RegExp(`^facilities/${ID}/years/[0-9]{4}/evidence$`)],
};

/** Only the paging parameters are forwarded to the API; anything else a visitor adds to the URL is dropped. */
export function safeQuery(search: URLSearchParams): string {
  const kept = new URLSearchParams();
  for (const name of ["limit", "offset"]) {
    const value = search.get(name);
    if (value !== null && /^\d{1,6}$/.test(value)) kept.set(name, value);
  }
  const text = kept.toString();
  return text ? `?${text}` : "";
}

export function isAllowed(method: string, path: string): boolean {
  // A path segment of "." or ".." would be resolved by the URL parser and could leave the allowed route.
  if (path.split("/").some((segment) => segment === "." || segment === "..")) return false;
  const patterns = ALLOWED[method.toUpperCase()];
  return patterns !== undefined && patterns.some((p) => p.test(path));
}

export const MAX_PROXY_BODY_BYTES = 30 * 1024 * 1024;
export const PROXY_TIMEOUT_MS = 60_000;
