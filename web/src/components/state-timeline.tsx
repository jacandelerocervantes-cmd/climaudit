"use client";

import { useI18n } from "@/lib/i18n";
import { STATE_LABELS } from "@/lib/messages";
import { Badge } from "@/components/ui";

/** The happy path of a batch. Side states are placed at the step where they interrupt it. */
const PATH = ["DRAFT", "SUBMITTED", "UNDER_REVIEW", "VERIFIED", "ISSUED", "RETIRED"] as const;
const POSITION: Record<string, number> = { DRAFT: 0, SUBMITTED: 1, NEEDS_INFO: 1, UNDER_REVIEW: 2, BLOCKED: 2, REJECTED: 2, VERIFIED: 3, ISSUED: 4, PARTIALLY_RETIRED: 4, RETIRED: 5 };
const SIDE: Record<string, "warn" | "bad"> = { NEEDS_INFO: "warn", BLOCKED: "bad", REJECTED: "bad" };

export function StateTimeline({ state }: { state: string }) {
  const { t } = useI18n();
  const at = POSITION[state] ?? 0;
  const side = SIDE[state];
  return (
    <div>
      <ol aria-label={t("Batch progress")} className="flex flex-wrap items-center gap-x-1 gap-y-2 text-xs">
        {PATH.map((step, i) => {
          const done = i < at;
          const current = i === at;
          return (
            <li key={step} aria-current={current ? "step" : undefined} className="flex items-center gap-1">
              {i > 0 ? <span aria-hidden="true" className="text-muted">›</span> : null}
              <span
                className={`rounded-md px-2 py-0.5 ${current ? (side === "bad" ? "bg-bad-bg font-medium text-bad-ink" : side === "warn" ? "bg-warn-bg font-medium text-warn-ink" : "bg-ok-bg font-medium text-ok-ink") : done ? "text-ink" : "text-muted"}`}
              >
                {done ? <span aria-hidden="true">✓ </span> : null}
                {t(STATE_LABELS[step] ?? step)}
              </span>
            </li>
          );
        })}
      </ol>
      {side ? (
        <p className="mt-2">
          <Badge tone={side}>
            <span aria-hidden="true">{side === "bad" ? "■" : "?"}</span>
            {t("Currently: {state}", { state: t(STATE_LABELS[state] ?? state) })}
          </Badge>
        </p>
      ) : state === "PARTIALLY_RETIRED" ? (
        <p className="mt-2 text-xs text-muted">{t("Some credits are retired; the rest are still available.")}</p>
      ) : null}
    </div>
  );
}
