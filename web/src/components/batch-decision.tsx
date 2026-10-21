"use client";

import { useState } from "react";
import { useI18n } from "@/lib/i18n";
import { msg } from "@/lib/i18n-core";
import { useAction } from "@/lib/client/action";
import { useCatalog } from "@/lib/client/catalog";
import { useMode } from "@/lib/client/mode";
import { usePersona } from "@/lib/client/persona";
import { formatKg } from "@/lib/format";
import { ROLE_LABELS, STATE_LABELS } from "@/lib/messages";
import type { Batch, Report } from "@/lib/types";
import { Badge, Card, ErrorBox } from "@/components/ui";

type Kind = "transition" | "verification" | "issue";
type ActionDef = { id: string; kind: Kind; to?: string; label: string; consequence: string; reasonRequired: boolean; blockedBy: string[]; tone: "primary" | "plain" };

const TRANSITION_LABELS: Record<string, string> = {
  SUBMITTED: msg("Submit for review"),
  UNDER_REVIEW: msg("Start the review"),
  NEEDS_INFO: msg("Return to the owner"),
  REJECTED: msg("Reject the batch"),
  BLOCKED: msg("Block the batch"),
  VERIFIED: msg("Mark as verified"),
};

const CONSEQUENCES: Record<string, string> = {
  SUBMITTED: msg("Sends the batch for review. Its evidence can't be edited until it is returned."),
  UNDER_REVIEW: msg("Starts or resumes the review."),
  NEEDS_INFO: msg("Returns the batch to the owner with your reason. They can correct it and submit it again."),
  REJECTED: msg("Rejects the batch with your reason. This ends the batch."),
  BLOCKED: msg("Blocks the batch until an administrator unblocks it."),
  VERIFIED: msg("Records your decision that the evidence supports the computed range. The registry can then issue credits."),
  ISSUED: msg("Creates credit units on the ledger and records them in the audit trail. This can't be undone."),
  verification: msg("Runs the checks and the calculation again and creates a new report. Findings accepted for the previous report must be accepted again."),
};

const WAITING_FOR: Record<string, string> = {
  DRAFT: msg("The project owner must submit the batch."),
  SUBMITTED: msg("The batch is about to enter review."),
  UNDER_REVIEW: msg("A verifier must decide."),
  NEEDS_INFO: msg("The project owner must correct the batch and submit it again."),
  BLOCKED: msg("An administrator must unblock the batch."),
  VERIFIED: msg("The registry can issue the credits."),
  ISSUED: msg("Holders can transfer and retire the credits."),
  PARTIALLY_RETIRED: msg("Holders can transfer and retire the remaining credits."),
  REJECTED: msg("The batch was rejected. Nothing more can happen."),
  RETIRED: msg("All credits are retired. Nothing more can happen."),
};

export function BatchDecision({ batch, report, onChanged, onOpenTab }: { batch: Batch; report: Report | null; onChanged: () => void; onOpenTab: (tab: "credit") => void }) {
  const { t } = useI18n();
  const { role } = usePersona();
  const catalog = useCatalog();
  const { snapshot } = useMode();
  const [done, setDone] = useState<{ text: string; credit?: boolean } | null>(null);

  if (!role) return <Card><p className="text-sm text-muted">{t("Choose a role to see what you can do.")}</p></Card>;
  if (!catalog) return <Card><p role="status" className="text-sm text-muted">{t("Loading")}</p></Card>;
  if (snapshot) {
    return (
      <Card>
        <h2 className="mb-1 text-base font-semibold">{t("Where this batch stands")}</h2>
        <p className="text-sm">{t(WAITING_FOR[batch.state] ?? "")}</p>
        <p className="mt-2 text-sm text-muted">{t("This is a recorded run, so the actions are switched off. Run the app locally to take them.")}</p>
      </Card>
    );
  }

  const accepted = new Set((report?.overrides ?? []).map((o) => o.code));
  const blocking = (report?.findings ?? []).filter((f) => (f.blocks_calculation || f.blocks_verified) && !accepted.has(f.code)).length;
  const pending = batch.evidence.filter((e) => e.confirmation === "pending_confirmation").length;

  function readiness(target: string): string[] {
    const reasons: string[] = [];
    if (target !== "VERIFIED" && target !== "ISSUED") return reasons;
    if (!report) reasons.push(t("Run the verification first."));
    else if (report.status !== "complete") reasons.push(t("The calculation is incomplete: resolve the blocking findings and run the verification again."));
    if (blocking > 0) reasons.push(t("{n} finding(s) block the next step.", { n: blocking }));
    if (pending > 0) reasons.push(t("{n} evidence item(s) wait for a person to confirm them.", { n: pending }));
    return reasons;
  }

  const actions: ActionDef[] = [];
  if (["verifier", "system", "admin"].includes(role) && batch.state === "UNDER_REVIEW") {
    actions.push({ id: "verification", kind: "verification", label: t("Run the verification"), consequence: t(CONSEQUENCES.verification as string), reasonRequired: false, blockedBy: [], tone: "plain" });
  }
  for (const tr of catalog.transitions) {
    if (tr.from !== batch.state || !tr.roles.includes(role) || ["ISSUED", "PARTIALLY_RETIRED", "RETIRED"].includes(tr.to)) continue;
    actions.push({ id: `to-${tr.to}`, kind: "transition", to: tr.to, label: t(TRANSITION_LABELS[tr.to] ?? STATE_LABELS[tr.to] ?? tr.to), consequence: t(CONSEQUENCES[tr.to] ?? ""), reasonRequired: tr.reason_required, blockedBy: readiness(tr.to), tone: tr.to === "VERIFIED" ? "primary" : "plain" });
  }
  if (role === "registry" && batch.state === "VERIFIED") {
    actions.push({ id: "issue", kind: "issue", label: t("Issue credits"), consequence: t(CONSEQUENCES.ISSUED as string), reasonRequired: false, blockedBy: readiness("ISSUED"), tone: "primary" });
  }

  // The main decision first, then the checks, then the ways to return or end the batch.
  const rank = (x: ActionDef) => (x.tone === "primary" ? 0 : x.kind === "verification" ? 1 : x.to === "NEEDS_INFO" ? 2 : 3);
  actions.sort((x, y) => rank(x) - rank(y));

  return (
    <div className="flex flex-col gap-4">
      <Card>
        <h2 className="mb-1 text-base font-semibold">{t("Where this batch stands")}</h2>
        <p className="text-sm">{t(WAITING_FOR[batch.state] ?? "")}</p>
        <p className="mt-1 text-xs text-muted">{t("Acting as {role}.", { role: t(ROLE_LABELS[role] ?? role) })}</p>
      </Card>

      {done ? (
        <div role="status" className="rounded-xl border border-line bg-ok-bg p-4 text-ok-ink">
          <p className="text-sm font-medium">{done.text}</p>
          {done.credit ? (
            <button type="button" onClick={() => onOpenTab("credit")} className="mt-2 rounded-md border border-current px-3 py-1 text-sm">{t("Open the credit")}</button>
          ) : null}
        </div>
      ) : null}

      {actions.length === 0 ? (
        <Card><p className="text-sm text-muted">{t("As {role} you have nothing to do on this batch now.", { role: t(ROLE_LABELS[role] ?? role) })}</p></Card>
      ) : (
        <ul className="flex flex-col gap-3">
          {actions.map((action) => (
            <ActionCard key={action.id} action={action} batch={batch} report={report} onSuccess={(text, credit) => { setDone({ text, credit }); onChanged(); }} />
          ))}
        </ul>
      )}
    </div>
  );
}

function ActionCard({ action, batch, report, onSuccess }: { action: ActionDef; batch: Batch; report: Report | null; onSuccess: (text: string, credit?: boolean) => void }) {
  const { t } = useI18n();
  const { run, busy, error, clear } = useAction();
  const [open, setOpen] = useState(false);
  const [reason, setReason] = useState("");
  const [problem, setProblem] = useState<string | null>(null);
  const blocked = action.blockedBy.length > 0;
  const units = report?.issuable_kg ?? null;

  async function confirm() {
    if (action.reasonRequired && reason.trim() === "") {
      setProblem(t("Enter a reason first."));
      return;
    }
    setProblem(null);
    if (action.kind === "verification") {
      const result = await run<{ report_id: string; status: string }>(`batches/${batch.batch_id}/verification`, {});
      if (result) { setOpen(false); onSuccess(t("Verification finished. Report {id} is ready.", { id: result.report_id })); }
    } else if (action.kind === "issue") {
      const result = await run<{ credit_id: string; units: number }>(`batches/${batch.batch_id}/issue`, {});
      if (result) { setOpen(false); onSuccess(t("Issued {units} credit units (1 unit = 1 kg CO2e).", { units: formatKg(result.units) }), true); }
    } else {
      const body = action.reasonRequired ? { to: action.to, reason: reason.trim() } : { to: action.to };
      const result = await run<{ state: string }>(`batches/${batch.batch_id}/transitions`, body);
      if (result) { setOpen(false); setReason(""); onSuccess(t("Done. The batch is now {state}.", { state: t(STATE_LABELS[result.state] ?? result.state) })); }
    }
  }

  const fieldId = `reason-${action.id}`;
  return (
    <li className="rounded-xl border border-line bg-surface p-4">
      <div className="flex flex-wrap items-start justify-between gap-2">
        <h3 className="text-sm font-semibold">{action.label}</h3>
        {blocked ? <Badge tone="warn">{t("Not available yet")}</Badge> : null}
      </div>
      <p className="mt-1 text-sm text-muted">{action.consequence}</p>

      {blocked ? (
        <ul className="mt-2 list-disc pl-5 text-sm text-warn-ink">
          {action.blockedBy.map((reasonText) => <li key={reasonText}>{reasonText}</li>)}
        </ul>
      ) : !open ? (
        <button type="button" onClick={() => { setOpen(true); clear(); }} className={`mt-3 rounded-md px-3 py-1.5 text-sm font-medium ${action.tone === "primary" ? "bg-accent text-accent-ink" : "border border-line hover:bg-sidebar"}`}>
          {action.label}
        </button>
      ) : (
        <form className="mt-3 flex flex-col gap-2 rounded-lg border border-line bg-canvas p-3" onSubmit={(e) => { e.preventDefault(); void confirm(); }}>
          <p className="text-sm font-medium">
            {action.kind === "issue" && units !== null ? t("Confirm: issue {units} credit units for this batch?", { units: formatKg(units) }) : t("Confirm: {action}?", { action: action.label.toLowerCase() })}
          </p>
          {action.reasonRequired ? (
            <>
              <label htmlFor={fieldId} className="text-sm">{t("Reason (required, recorded in the audit trail)")}</label>
              <textarea id={fieldId} value={reason} maxLength={512} rows={3} onChange={(e) => { setReason(e.target.value); setProblem(null); }} aria-invalid={problem ? true : undefined} className="w-full rounded-md border border-line bg-surface p-2 text-sm" />
            </>
          ) : null}
          {problem ? <p role="alert" className="text-sm text-bad-ink">{problem}</p> : null}
          {error ? <ErrorBox failure={error} /> : null}
          <div className="flex gap-2">
            <button type="submit" disabled={busy} className="rounded-md bg-accent px-3 py-1.5 text-sm font-medium text-accent-ink disabled:opacity-60">{busy ? t("Saving") : t("Confirm")}</button>
            <button type="button" onClick={() => { setOpen(false); setProblem(null); clear(); }} className="rounded-md border border-line px-3 py-1.5 text-sm">{t("Cancel")}</button>
          </div>
        </form>
      )}
    </li>
  );
}
