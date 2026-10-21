import { NextRequest, NextResponse } from "next/server";
import { loadSnapshot, recordedAnswer, snapshotEnabled } from "@/lib/snapshot";
import { MAX_PROXY_BODY_BYTES, PERSONA_COOKIE, PROXY_TIMEOUT_MS, apiBase, isAllowed, isRole, keyFor, safeQuery } from "@/lib/config";

// Same-origin proxy to the ClimAudit API. The browser never holds an API key: the persona cookie picks which
// server-side demo key is attached. Only the routes in the allowlist are forwarded.
export const dynamic = "force-dynamic";

function failure(status: number, code: string, params: Record<string, unknown> = {}): NextResponse {
  return NextResponse.json({ error: { code, params, correlation_id: "-" } }, { status });
}

async function forward(request: NextRequest, context: { params: Promise<{ path: string[] }> }): Promise<NextResponse> {
  const { path } = await context.params;
  const joined = path.join("/");
  if (!isAllowed(request.method, joined)) return failure(404, "NOT_FOUND", { resource: "route" });

  const role = request.cookies.get(PERSONA_COOKIE)?.value;
  if (!isRole(role)) return failure(401, "AUTH_REQUIRED", { reason: "no_persona" });

  if (snapshotEnabled()) {
    // A recorded run: reads are answered from the file, nothing can change, no API and no key is involved.
    if (request.method !== "GET") return failure(403, "SNAPSHOT_READ_ONLY");
    const snapshot = loadSnapshot();
    const recorded = snapshot ? recordedAnswer(snapshot, role, joined) : null;
    if (!recorded) return failure(404, "NOT_FOUND", { resource: "route" });
    return NextResponse.json(recorded.body, { status: recorded.status, headers: { "Cache-Control": "no-store" } });
  }
  const key = keyFor(role);
  if (!key) return failure(401, "AUTH_REQUIRED", { reason: "persona_key_not_configured", role });

  const headers: Record<string, string> = { Authorization: `Bearer ${key}`, Accept: "application/json" };
  const contentType = request.headers.get("content-type");
  if (contentType) headers["Content-Type"] = contentType;
  const idempotency = request.headers.get("idempotency-key");
  if (idempotency) headers["Idempotency-Key"] = idempotency;
  const correlation = request.headers.get("x-correlation-id");
  if (correlation) headers["X-Correlation-Id"] = correlation;

  let body: ArrayBuffer | undefined;
  if (request.method !== "GET") {
    body = await request.arrayBuffer();
    if (body.byteLength > MAX_PROXY_BODY_BYTES) return failure(413, "VALIDATION_FAILED", { rule: "body_too_large" });
  }

  const url = `${apiBase()}/${joined}${safeQuery(request.nextUrl.searchParams)}`;
  try {
    const upstream = await fetch(url, { method: request.method, headers, body, signal: AbortSignal.timeout(PROXY_TIMEOUT_MS), cache: "no-store" });
    const text = await upstream.text();
    return new NextResponse(text, {
      status: upstream.status,
      headers: { "Content-Type": upstream.headers.get("content-type") ?? "application/json", "Cache-Control": "no-store" },
    });
  } catch {
    return failure(503, "API_UNREACHABLE", { reason: "api_unreachable" });
  }
}

export const GET = forward;
export const POST = forward;
export const PUT = forward;
