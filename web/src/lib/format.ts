/** Figures use ASCII digits and a point in every language (LANGUAGES.md), so numbers read the same in a screenshot. */
export function formatKg(value: number | null | undefined): string {
  if (value === null || value === undefined || !Number.isFinite(value)) return "-";
  return Math.round(value).toLocaleString("en-US");
}

export type KgRange = { low: number; central: number; high: number };

export function isKgRange(value: unknown): value is KgRange {
  if (typeof value !== "object" || value === null) return false;
  const v = value as Record<string, unknown>;
  return typeof v.low === "number" && typeof v.central === "number" && typeof v.high === "number";
}

export function formatDate(iso: string | null | undefined): string {
  if (!iso) return "-";
  return iso.slice(0, 10);
}
