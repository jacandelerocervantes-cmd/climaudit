"use client";

import { useI18n } from "@/lib/i18n";
import { formatKg, type KgRange } from "@/lib/format";

/**
 * The computed range against the claim, as one bar: the shaded span is low to high, the solid tick the central value, the
 * dashed tick the claim. Numbers are printed under the bar, so the bar is never the only channel.
 */
export function RangeBar({ range, claimed }: { range: KgRange; claimed: number | null }) {
  const { t } = useI18n();
  const top = Math.max(range.high, claimed ?? 0) * 1.05 || 1;
  const pct = (v: number) => `${Math.max(0, Math.min(100, (v / top) * 100))}%`;
  const label = t("Range {low} to {high} kg CO2e, central {central}, claim {claim}", {
    low: formatKg(range.low),
    high: formatKg(range.high),
    central: formatKg(range.central),
    claim: claimed === null ? "-" : formatKg(claimed),
  });
  return (
    <div>
      <div role="img" aria-label={label} className="relative h-6">
        <div className="absolute inset-x-0 top-[10px] h-1 rounded bg-line" />
        <div className="absolute top-[6px] h-3 rounded-md border border-accent bg-range-bg" style={{ left: pct(range.low), width: `calc(${pct(range.high)} - ${pct(range.low)})` }} />
        <div className="absolute top-[2px] h-5 w-0.5 bg-accent" style={{ left: pct(range.central) }} />
        {claimed !== null ? <div className="absolute top-0 h-6 border-l-2 border-dashed border-muted" style={{ left: pct(claimed) }} /> : null}
      </div>
      <div className="mt-1 flex justify-between text-xs text-muted">
        <span>{t("Low {value}", { value: formatKg(range.low) })}</span>
        <span className="font-medium text-ink">{t("Central {value}", { value: formatKg(range.central) })}</span>
        <span>{t("High {value}", { value: formatKg(range.high) })}</span>
      </div>
    </div>
  );
}
