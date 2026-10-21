"use client";

import { useState } from "react";
import { useI18n } from "@/lib/i18n";
import { api, ApiFailure } from "@/lib/client/api";
import { useMode } from "@/lib/client/mode";
import { usePersona } from "@/lib/client/persona";
import { errorMessage } from "@/lib/messages";
import type { Batch, Finding, Report } from "@/lib/types";
import { FindingCard } from "@/components/finding-card";
import { Card } from "@/components/ui";

const ORDER = ["critical", "high", "medium", "low", "info"];
const MAX_REASON = 512;

function OverrideForm({ batchId, code, onDone }: { batchId: string; code: string; onDone: () => void }) {
  const { t } = useI18n();
  const [open, setOpen] = useState(false);
  const [reason, setReason] = useState("");
  const [problem, setProblem] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);

  async function submit() {
    if (reason.trim() === "") {
      setProblem(t("Enter a reason first."));
      return;
    }
    setBusy(true);
    setProblem(null);
    try {
      await api(`batches/${batchId}/findings/override`, { method: "POST", body: { code, reason: reason.trim() } });
      setOpen(false);
      setReason("");
      onDone();
    } catch (error) {
      setProblem(errorMessage(error instanceof ApiFailure ? error : new ApiFailure("INTERNAL_ERROR", 0), t));
    } finally {
      setBusy(false);
    }
  }

  if (!open) {
    return (
      <button type="button" onClick={() => setOpen(true)} className="mt-3 rounded-md border border-line px-3 py-1.5 text-sm hover:bg-sidebar">
        {t("Accept with a reason")}
      </button>
    );
  }
  const fieldId = `reason-${code}`;
  return (
    <form
      className="mt-3 flex flex-col gap-2"
      onSubmit={(e) => {
        e.preventDefault();
        void submit();
      }}
    >
      <label htmlFor={fieldId} className="text-sm font-medium">
        {t("Reason (required, recorded in the audit trail)")}
      </label>
      <textarea
        id={fieldId}
        value={reason}
        maxLength={MAX_REASON}
        rows={3}
        onChange={(e) => {
          setReason(e.target.value);
          setProblem(null);
        }}
        aria-describedby={problem ? `${fieldId}-error` : undefined}
        aria-invalid={problem ? true : undefined}
        className="w-full rounded-md border border-line bg-canvas p-2 text-sm"
      />
      <p className="text-xs text-muted">{t("{n} of {max} characters", { n: reason.length, max: MAX_REASON })}</p>
      {problem ? <p id={`${fieldId}-error`} role="alert" className="text-sm text-bad-ink">{problem}</p> : null}
      <div className="flex gap-2">
        <button type="submit" disabled={busy} className="rounded-md bg-accent px-3 py-1.5 text-sm font-medium text-accent-ink disabled:opacity-60">
          {busy ? t("Saving") : t("Accept finding")}
        </button>
        <button type="button" onClick={() => { setOpen(false); setProblem(null); }} className="rounded-md border border-line px-3 py-1.5 text-sm">
          {t("Cancel")}
        </button>
      </div>
    </form>
  );
}

export function BatchFindings({ batch, report, onChanged }: { batch: Batch; report: Report | null; onChanged: () => void }) {
  const { t } = useI18n();
  const { role } = usePersona();
  const { snapshot } = useMode();
  if (!report) return <Card><p className="text-sm text-muted">{t("Findings appear after the verification runs.")}</p></Card>;

  const accepted = new Map((report.overrides ?? []).map((o) => [o.code, o]));
  const canOverride = !snapshot && (role === "verifier" || role === "admin") && batch.state === "UNDER_REVIEW";
  const sorted: Finding[] = [...report.findings].sort((a, b) => ORDER.indexOf(a.severity) - ORDER.indexOf(b.severity));
  const blocking = sorted.filter((f) => (f.blocks_calculation || f.blocks_verified) && !accepted.has(f.code)).length;

  return (
    <div className="flex flex-col gap-4">
      <Card>
        <h2 className="text-base font-semibold">{t("Findings")}</h2>
        <p className="mt-1 text-sm">
          {sorted.length === 0
            ? t("No findings.")
            : blocking > 0
              ? t("{n} finding(s) block the next step.", { n: blocking })
              : t("No finding blocks the next step.")}
        </p>
        <p className="mt-1 text-xs text-muted">
          {t("Severity and blocking come from the rules, not from the AI. Some findings can be accepted by a verifier with a written reason, which is recorded in the audit trail.")}
        </p>
      </Card>
      {sorted.length > 0 ? (
        <ul className="flex flex-col gap-3">
          {sorted.map((finding, index) => (
            <FindingCard key={`${finding.code}-${index}`} finding={finding} accepted={accepted.get(finding.code)}>
              {finding.overridable && !accepted.has(finding.code) && canOverride ? <OverrideForm batchId={batch.batch_id} code={finding.code} onDone={onChanged} /> : null}
              {finding.overridable && !accepted.has(finding.code) && !canOverride && !snapshot && (role === "verifier" || role === "admin") ? (
                <p className="mt-3 text-xs text-muted">{t("Findings can be accepted while the batch is under review.")}</p>
              ) : null}
            </FindingCard>
          ))}
        </ul>
      ) : null}
    </div>
  );
}
