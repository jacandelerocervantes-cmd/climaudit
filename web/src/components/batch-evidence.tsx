"use client";

import { useState } from "react";
import { useI18n } from "@/lib/i18n";
import { api, ApiFailure, useApi } from "@/lib/client/api";
import { useAction } from "@/lib/client/action";
import { useMode } from "@/lib/client/mode";
import { usePersona } from "@/lib/client/persona";
import { KIND_LABELS, humanize, unitSymbol } from "@/lib/evidence-labels";
import { CONFIRMATION_LABELS, SOURCE_LABELS, errorMessage } from "@/lib/messages";
import type { DocumentRow, EvidenceItem } from "@/lib/types";
import { HashChip } from "@/components/hash-chip";
import { Badge, Card, ErrorBox, ProvenanceDot } from "@/components/ui";
import type { TFunction } from "@/lib/i18n-core";

function displayValue(item: EvidenceItem, t: TFunction): string {
  if (item.value === "true") return t("Yes");
  if (item.value === "false") return t("No");
  const unit = unitSymbol(item.unit);
  const looksCode = /^[a-z]+(_[a-z]+)+$/.test(item.value) || /^[a-z]+$/.test(item.value);
  const base = looksCode && item.unit === "" ? humanize(item.value) : item.value;
  return unit ? `${base} ${unit}` : base;
}

function ConfirmationBadge({ status }: { status: string }) {
  const { t } = useI18n();
  const tone = status === "confirmed" ? "ok" : status === "pending_confirmation" ? "warn" : "bad";
  return <Badge tone={tone}>{t(CONFIRMATION_LABELS[status] ?? status)}</Badge>;
}

function EvidenceTable({ items, caption }: { items: EvidenceItem[]; caption: string }) {
  const { t } = useI18n();
  return (
    <div className="overflow-x-auto">
      <table className="w-full min-w-[640px] text-left text-sm">
        <caption className="sr-only">{caption}</caption>
        <thead className="text-xs text-muted">
          <tr>
            <th scope="col" className="py-2 pr-3 font-medium">{t("Evidence")}</th>
            <th scope="col" className="py-2 pr-3 font-medium">{t("Value")}</th>
            <th scope="col" className="py-2 pr-3 font-medium">{t("Provenance")}</th>
            <th scope="col" className="py-2 pr-3 font-medium">{t("Source")}</th>
            <th scope="col" className="py-2 pr-3 font-medium">{t("Status")}</th>
            <th scope="col" className="py-2 font-medium">{t("Document")}</th>
          </tr>
        </thead>
        <tbody>
          {items.map((item) => (
            <tr key={item.item_id} className="border-t border-line align-top">
              <th scope="row" className="py-2 pr-3 text-left font-normal">
                {t(KIND_LABELS[item.kind] ?? humanize(item.kind))}
                {item.rel_uncertainty ? <span className="block text-xs text-muted">{t("Uncertainty ±{value}", { value: item.rel_uncertainty })}</span> : null}
              </th>
              <td className="py-2 pr-3 tabular-nums">{displayValue(item, t)}</td>
              <td className="py-2 pr-3"><ProvenanceDot provenance={item.provenance} /></td>
              <td className="py-2 pr-3 text-xs">{t(SOURCE_LABELS[item.source] ?? item.source)}</td>
              <td className="py-2 pr-3"><ConfirmationBadge status={item.confirmation} /></td>
              <td className="py-2 font-mono text-xs">{item.document_ref ?? "-"}</td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}

function DocumentText({ documentRef }: { documentRef: string }) {
  const { t } = useI18n();
  const [state, setState] = useState<{ text: string | null; error: ApiFailure | null; loading: boolean }>({ text: null, error: null, loading: false });

  async function load(open: boolean) {
    if (!open || state.text !== null || state.loading) return;
    setState({ text: null, error: null, loading: true });
    try {
      const data = await api<{ text: string }>(`documents/${documentRef}/text`);
      setState({ text: data.text, error: null, loading: false });
    } catch (error) {
      setState({ text: null, error: error instanceof ApiFailure ? error : new ApiFailure("INTERNAL_ERROR", 0), loading: false });
    }
  }

  return (
    <details onToggle={(e) => void load((e.currentTarget as HTMLDetailsElement).open)} className="mt-2 text-sm">
      <summary className="cursor-pointer text-accent">{t("Show the text a model would read")}</summary>
      {state.loading ? <p role="status" className="mt-2 text-muted">{t("Loading")}</p> : null}
      {state.error ? <p role="alert" className="mt-2 text-bad-ink">{errorMessage(state.error, t)}</p> : null}
      {state.text !== null ? (
        <>
          <p className="mt-2 text-xs text-muted">{t("Hidden text is removed. Shown as plain text, in the language of the document.")}</p>
          <pre className="mt-1 max-h-64 overflow-auto whitespace-pre-wrap rounded-md border border-line bg-canvas p-2 text-xs">{state.text || t("(no text)")}</pre>
        </>
      ) : null}
    </details>
  );
}

function Documents({ batchId }: { batchId: string }) {
  const { t } = useI18n();
  const { data, error, loading } = useApi<DocumentRow[]>(`batches/${batchId}/documents`);
  if (loading) return <p role="status" className="text-sm text-muted">{t("Loading")}</p>;
  if (error) return <p role="alert" className="text-sm text-bad-ink">{errorMessage(error, t)}</p>;
  if (!data || data.length === 0) return <p className="text-sm text-muted">{t("No documents uploaded.")}</p>;
  return (
    <ul className="flex flex-col gap-3">
      {data.map((doc) => (
        <li key={doc.document_ref} className="rounded-lg border border-line p-3">
          <div className="flex flex-wrap items-center justify-between gap-2">
            <span className="font-medium">{doc.filename}</span>
            {doc.findings.length === 0 ? <Badge tone="ok">{t("No issues found")}</Badge> : <Badge tone="warn">{t("{n} issue(s) found", { n: doc.findings.length })}</Badge>}
          </div>
          <dl className="mt-2 grid grid-cols-[auto_1fr] gap-x-3 gap-y-1 text-xs">
            <dt className="text-muted">{t("Reference")}</dt>
            <dd className="font-mono">{doc.document_ref}</dd>
            <dt className="text-muted">{t("Type and size")}</dt>
            <dd>{doc.media_type}, {(doc.size / 1024).toFixed(1)} KB</dd>
            <dt className="text-muted">SHA-256</dt>
            <dd><HashChip value={doc.sha256} label="SHA-256" /></dd>
          </dl>
          <DocumentText documentRef={doc.document_ref} />
        </li>
      ))}
    </ul>
  );
}

function PendingDecision({ batchId, item, onChanged }: { batchId: string; item: EvidenceItem; onChanged: () => void }) {
  const { t } = useI18n();
  const { run, busy, error } = useAction();
  async function decide(decision: "confirmed" | "rejected") {
    const result = await run(`batches/${batchId}/evidence/${item.item_id}/confirm`, { decision });
    if (result) onChanged();
  }
  return (
    <li className="flex flex-col gap-1 rounded-lg border border-line p-2 text-sm">
      <span>{t(KIND_LABELS[item.kind] ?? humanize(item.kind))}: <strong className="font-medium">{displayValue(item, t)}</strong></span>
      {item.span?.quote ? <span className="text-xs text-muted">{t("Quoted: “{quote}”", { quote: item.span.quote })}</span> : null}
      {error ? <ErrorBox failure={error} /> : null}
      <span className="flex gap-2">
        <button type="button" disabled={busy} onClick={() => void decide("confirmed")} className="rounded-md bg-accent px-2.5 py-1 text-xs font-medium text-accent-ink disabled:opacity-60">{t("Confirm the value")}</button>
        <button type="button" disabled={busy} onClick={() => void decide("rejected")} className="rounded-md border border-line px-2.5 py-1 text-xs disabled:opacity-60">{t("Reject the value")}</button>
      </span>
    </li>
  );
}

export function BatchEvidence({ batchId, evidence, onChanged }: { batchId: string; evidence: EvidenceItem[]; onChanged: () => void }) {
  const { t } = useI18n();
  const { role } = usePersona();
  const { snapshot } = useMode();
  const canDecide = !snapshot && (role === "owner" || role === "verifier" || role === "admin");
  const pending = evidence.filter((e) => e.confirmation === "pending_confirmation");
  const ungrouped = evidence.filter((e) => e.group === null && e.confirmation !== "pending_confirmation");
  const groups = new Map<string, EvidenceItem[]>();
  for (const item of evidence) {
    if (item.group !== null && item.confirmation !== "pending_confirmation") groups.set(item.group, [...(groups.get(item.group) ?? []), item]);
  }
  return (
    <div className="flex flex-col gap-4">
      {pending.length > 0 ? (
        <Card>
          <h2 className="mb-1 text-base font-semibold">{t("Waiting for confirmation")}</h2>
          <p className="mb-3 text-sm text-muted">{t("The AI assistant can only propose a value. It counts after a person confirms it, and only if the quoted text is really in the document.")}</p>
          <EvidenceTable items={pending} caption={t("Evidence items waiting for confirmation")} />
          {canDecide ? (
            <ul aria-label={t("Decide on the proposed values")} className="mt-3 flex flex-col gap-2">
              {pending.map((p) => <PendingDecision key={p.item_id} batchId={batchId} item={p} onChanged={onChanged} />)}
            </ul>
          ) : (
            <ul className="mt-2 flex flex-col gap-1 text-xs text-muted">
              {pending.filter((p) => p.span?.quote).map((p) => (
                <li key={p.item_id}>{t("Quoted: “{quote}”", { quote: p.span?.quote ?? "" })}</li>
              ))}
            </ul>
          )}
        </Card>
      ) : null}

      <Card>
        <h2 className="mb-3 text-base font-semibold">{t("Evidence")}</h2>
        {ungrouped.length > 0 ? <EvidenceTable items={ungrouped} caption={t("Evidence items of the batch")} /> : <p className="text-sm text-muted">{t("No evidence entered yet.")}</p>}
      </Card>

      {[...groups.entries()].map(([group, items]) => (
        <Card key={group}>
          <h2 className="mb-3 text-base font-semibold">{t("Group: {name}", { name: group })}</h2>
          <EvidenceTable items={items} caption={t("Evidence items of group {name}", { name: group })} />
        </Card>
      ))}

      <Card>
        <h2 className="mb-3 text-base font-semibold">{t("Documents")}</h2>
        <Documents batchId={batchId} />
      </Card>
    </div>
  );
}
