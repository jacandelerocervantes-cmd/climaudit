"use client";

import type { ReactNode } from "react";
import { useI18n } from "@/lib/i18n";
import type { ApiFailure } from "@/lib/client/api";
import { errorMessage, PROVENANCE_LABELS, STATE_LABELS, STATE_STYLE } from "@/lib/messages";

type Tone = "neutral" | "info" | "ok" | "warn" | "bad" | "synthetic";

const TONE: Record<Tone, string> = {
  neutral: "bg-sidebar text-ink border border-line",
  info: "bg-info-bg text-info-ink",
  ok: "bg-ok-bg text-ok-ink",
  warn: "bg-warn-bg text-warn-ink",
  bad: "bg-bad-bg text-bad-ink",
  synthetic: "bg-synthetic-bg text-synthetic-ink",
};

export function Badge({ tone = "neutral", children }: { tone?: Tone; children: ReactNode }) {
  return <span className={`inline-flex items-center gap-1 rounded-md px-2 py-0.5 text-xs font-medium ${TONE[tone]}`}>{children}</span>;
}

/** A batch state: glyph + word + tone, never colour alone. */
export function StateBadge({ state }: { state: string }) {
  const { t } = useI18n();
  const style = STATE_STYLE[state] ?? { glyph: "·", tone: "neutral" as const };
  return (
    <Badge tone={style.tone}>
      <span aria-hidden="true">{style.glyph}</span>
      {t(STATE_LABELS[state] ?? state)}
    </Badge>
  );
}

const DOT: Record<string, string> = { measured: "bg-measured", modeled: "bg-modeled", synthetic: "bg-synthetic" };

/** The provenance of a value: a dot plus its name (measured, modeled, synthetic). */
export function ProvenanceDot({ provenance }: { provenance: string }) {
  const { t } = useI18n();
  return (
    <span className="inline-flex items-center gap-1.5 text-xs text-muted">
      <span aria-hidden="true" className={`inline-block h-2.5 w-2.5 rounded-full ${DOT[provenance] ?? "bg-muted"}`} />
      {t(PROVENANCE_LABELS[provenance] ?? provenance)}
    </span>
  );
}

export function Card({ children, className = "" }: { children: ReactNode; className?: string }) {
  return <section className={`rounded-xl border border-line bg-surface p-4 ${className}`}>{children}</section>;
}

export function EmptyState({ title, children }: { title: string; children?: ReactNode }) {
  return (
    <div className="rounded-xl border border-dashed border-line p-8 text-center">
      <p className="text-base font-medium">{title}</p>
      {children ? <p className="mx-auto mt-1 max-w-md text-sm text-muted">{children}</p> : null}
    </div>
  );
}

export function ErrorBox({ failure, onRetry }: { failure: ApiFailure; onRetry?: () => void }) {
  const { t } = useI18n();
  return (
    <div role="alert" className="rounded-xl border border-line bg-bad-bg p-4 text-bad-ink">
      <p className="text-sm font-medium">{errorMessage(failure, t)}</p>
      {failure.correlationId && failure.correlationId !== "-" ? <p className="mt-1 text-xs">{t("Reference: {id}", { id: failure.correlationId })}</p> : null}
      {onRetry ? (
        <button type="button" onClick={onRetry} className="mt-2 rounded-md border border-current px-3 py-1 text-xs font-medium">
          {t("Try again")}
        </button>
      ) : null}
    </div>
  );
}

export function Loading({ label }: { label: string }) {
  return (
    <p role="status" className="text-sm text-muted">
      {label}
    </p>
  );
}
