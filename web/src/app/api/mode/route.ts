import { NextResponse } from "next/server";
import { loadSnapshot, snapshotEnabled } from "@/lib/snapshot";

// Tells the interface whether it replays a recorded run (read-only) or talks to a live API.
export const dynamic = "force-dynamic";

export async function GET(): Promise<NextResponse> {
  if (!snapshotEnabled()) return NextResponse.json({ snapshot: false });
  const meta = loadSnapshot()?.meta ?? {};
  return NextResponse.json({
    snapshot: true,
    generated_at: typeof meta.generated_at === "string" ? meta.generated_at : null,
    ledger_mode: typeof meta.ledger_mode === "string" ? meta.ledger_mode : null,
    network: typeof meta.network === "string" ? meta.network : null,
  });
}
