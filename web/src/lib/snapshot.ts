import { existsSync, readFileSync } from "node:fs";
import { join } from "node:path";

/**
 * Snapshot mode (CP_SNAPSHOT=1): the app replays a recorded real run instead of calling the API. It is read-only, needs no
 * keys and no backend, and is meant for a public link. The file is written by `backend/scripts/make_snapshot.py`.
 */
export type Recorded = { status: number; body: unknown };
export type Snapshot = { meta: Record<string, unknown>; roles: Record<string, Record<string, Recorded>> };

export function snapshotEnabled(env: Record<string, string | undefined> = process.env): boolean {
  return env.CP_SNAPSHOT === "1";
}

const cache = new Map<string, Snapshot | null>();

export function loadSnapshot(env: Record<string, string | undefined> = process.env): Snapshot | null {
  const file = env.CP_SNAPSHOT_FILE ?? join(process.cwd(), "snapshot", "snapshot.json");
  if (!cache.has(file)) {
    try {
      cache.set(file, existsSync(/* turbopackIgnore: true */ file) ? (JSON.parse(readFileSync(/* turbopackIgnore: true */ file, "utf8")) as Snapshot) : null);
    } catch {
      cache.set(file, null);
    }
  }
  return cache.get(file) ?? null;
}

export function recordedAnswer(snapshot: Snapshot, role: string, path: string): Recorded | null {
  return snapshot.roles[role]?.[path] ?? null;
}
