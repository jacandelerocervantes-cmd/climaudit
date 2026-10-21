import { NextRequest, NextResponse } from "next/server";
import { PERSONA_COOKIE, isRole, keyFor } from "@/lib/config";
import { snapshotEnabled } from "@/lib/snapshot";

const available = (role: Parameters<typeof keyFor>[0]) => snapshotEnabled() || keyFor(role) !== undefined;

// The demo persona: which role the proxy acts as. This is not authentication, it only selects a server-side demo key.
export const dynamic = "force-dynamic";

export async function GET(request: NextRequest): Promise<NextResponse> {
  const value = request.cookies.get(PERSONA_COOKIE)?.value;
  const role = isRole(value) ? value : null;
  return NextResponse.json({ role, configured: role ? available(role) : false });
}

export async function POST(request: NextRequest): Promise<NextResponse> {
  const body: unknown = await request.json().catch(() => null);
  const role = typeof body === "object" && body !== null ? (body as { role?: unknown }).role : undefined;
  if (!isRole(role)) return NextResponse.json({ error: { code: "VALIDATION_FAILED", params: { field: "role" }, correlation_id: "-" } }, { status: 422 });
  const response = NextResponse.json({ role, configured: available(role) });
  response.cookies.set(PERSONA_COOKIE, role, { httpOnly: true, sameSite: "lax", path: "/", maxAge: 60 * 60 * 24 * 7 });
  return response;
}

export async function DELETE(): Promise<NextResponse> {
  const response = NextResponse.json({ role: null, configured: false });
  response.cookies.delete(PERSONA_COOKIE);
  return response;
}
