import type { ProfileDoc } from "@/lib/types";

export type ParameterRow = { name: string; value: string; page: string | null; verified: boolean; note: string | null };

/**
 * Every number the calculation takes from the methodology profile: any object with a `value` and a `verified` flag,
 * wherever it sits in the file, listed with its path, its page in the source document and whether it was confirmed.
 */
export function collectParameters(profile: ProfileDoc): ParameterRow[] {
  const rows: ParameterRow[] = [];
  const visit = (node: unknown, path: string) => {
    if (Array.isArray(node)) {
      node.forEach((item, index) => {
        const tag = typeof item === "object" && item !== null ? ((item as Record<string, unknown>).label ?? (item as Record<string, unknown>).field ?? index) : index;
        visit(item, `${path}[${String(tag)}]`);
      });
      return;
    }
    if (typeof node !== "object" || node === null) return;
    const entry = node as Record<string, unknown>;
    if ("value" in entry && typeof entry.verified === "boolean") {
      const note = entry.note ?? entry.ambiguity ?? null;
      rows.push({
        name: path,
        value: String(entry.value),
        page: entry.page === undefined || entry.page === null ? null : String(entry.page),
        verified: entry.verified,
        note: note === null ? null : String(note),
      });
      return;
    }
    for (const [key, child] of Object.entries(entry)) visit(child, path ? `${path}.${key}` : key);
  };
  for (const [key, child] of Object.entries(profile)) {
    if (["profile_id", "label", "version", "horizon_years", "source", "methodology_id"].includes(key)) continue;
    visit(child, key);
  }
  return rows;
}
