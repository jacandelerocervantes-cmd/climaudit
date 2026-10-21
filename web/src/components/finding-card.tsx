"use client";

import type { ReactNode } from "react";
import { useI18n } from "@/lib/i18n";
import { FINDING_TEXTS, UNKNOWN_FINDING } from "@/lib/finding-texts";
import { humanize } from "@/lib/evidence-labels";
import { SEVERITY_LABELS } from "@/lib/messages";
import type { Finding } from "@/lib/types";
import { Badge } from "@/components/ui";

const SEVERITY_TONE: Record<string, "bad" | "warn" | "info" | "neutral"> = { critical: "bad", high: "bad", medium: "warn", low: "info", info: "neutral" };
const SEVERITY_GLYPH: Record<string, string> = { critical: "■", high: "▲", medium: "◆", low: "●", info: "○" };

function paramValue(value: unknown): string {
  if (Array.isArray(value)) return value.map(paramValue).join(", ");
  if (typeof value === "object" && value !== null) return JSON.stringify(value).slice(0, 120);
  return String(value);
}

export type Acceptance = { code: string; actor_id: string; reason: string; created_at: string };

/** One finding: what it is, how serious, what it blocks, its parameters, and whether a verifier accepted it. */
export function FindingCard({ finding, accepted, children }: { finding: Finding; accepted?: Acceptance; children?: ReactNode }) {
  const { t } = useI18n();
  const text = FINDING_TEXTS[finding.code] ?? UNKNOWN_FINDING;
  const entries = Object.entries(finding.params);
  const blocks = finding.blocks_calculation || finding.blocks_verified;
  return (
    <li className="rounded-xl border border-line bg-surface p-4">
      <div className="flex flex-wrap items-start justify-between gap-2">
        <h3 className="text-sm font-semibold">{t(text.title)}</h3>
        <Badge tone={SEVERITY_TONE[finding.severity] ?? "neutral"}>
          <span aria-hidden="true">{SEVERITY_GLYPH[finding.severity] ?? "·"}</span>
          {t(SEVERITY_LABELS[finding.severity] ?? finding.severity)}
        </Badge>
      </div>
      <p className="mt-1 text-sm text-muted">{t(text.meaning)}</p>

      <ul aria-label={t("What this finding does")} className="mt-2 flex flex-wrap gap-2">
        {finding.blocks_calculation ? <li><Badge tone="bad">{t("Blocks the calculation")}</Badge></li> : null}
        {finding.blocks_verified ? <li><Badge tone="warn">{t("Blocks verification")}</Badge></li> : null}
        {!blocks ? <li><Badge tone="neutral">{t("Does not block")}</Badge></li> : null}
        {finding.overridable ? <li><Badge tone="info">{t("A verifier can accept it with a reason")}</Badge></li> : null}
        {finding.source === "model" ? <li><Badge tone="synthetic">{t("Proposed by the AI assistant")}</Badge></li> : null}
      </ul>

      {entries.length > 0 ? (
        <dl className="mt-3 grid grid-cols-[auto_1fr] gap-x-4 gap-y-1 text-xs">
          {entries.map(([key, value]) => (
            <div key={key} className="contents">
              <dt className="text-muted">{humanize(key)}</dt>
              <dd className="break-words font-mono">{paramValue(value)}</dd>
            </div>
          ))}
        </dl>
      ) : null}

      {accepted ? (
        <div className="mt-3 rounded-lg bg-ok-bg p-3 text-sm text-ok-ink">
          <p className="font-medium">{t("Accepted by {actor}", { actor: accepted.actor_id })}</p>
          <p className="mt-1">{t("Reason: {reason}", { reason: accepted.reason })}</p>
          <p className="mt-1 text-xs">{t("This covers every finding with the same code in this report.")}</p>
        </div>
      ) : null}
      {children}
    </li>
  );
}
