"use client";

import { useState } from "react";
import { useI18n } from "@/lib/i18n";

/** A hash shown short, with its full value on hover and a copy button. Also used for ledger references. */
export function HashChip({ value, label }: { value: string; label: string }) {
  const { t } = useI18n();
  const [copied, setCopied] = useState(false);
  const short = value.length > 18 ? `${value.slice(0, 8)}…${value.slice(-6)}` : value;

  async function copy() {
    try {
      await navigator.clipboard.writeText(value);
      setCopied(true);
      window.setTimeout(() => setCopied(false), 1500);
    } catch {
      // clipboard access can be refused; the full value stays available in the tooltip
    }
  }

  return (
    <span className="inline-flex items-center gap-1.5 rounded-md border border-line bg-canvas px-1.5 py-0.5 font-mono text-xs" title={value}>
      <span>{short}</span>
      <button type="button" onClick={() => void copy()} aria-label={t("Copy {label}", { label })} className="rounded px-1 text-muted hover:text-ink">
        {copied ? t("Copied") : t("Copy")}
      </button>
    </span>
  );
}
