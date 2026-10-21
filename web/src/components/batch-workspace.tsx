"use client";

import Link from "next/link";
import { useSearchParams } from "next/navigation";
import { useState, type KeyboardEvent } from "react";
import { useI18n } from "@/lib/i18n";
import { msg } from "@/lib/i18n-core";
import { ApiFailure, useApi } from "@/lib/client/api";
import { usePersona } from "@/lib/client/persona";
import { APPLICATION_LABELS } from "@/lib/messages";
import type { Batch, Report } from "@/lib/types";
import { BatchAudit } from "@/components/batch-audit";
import { BatchCredit } from "@/components/batch-credit";
import { BatchDecision } from "@/components/batch-decision";
import { BatchEvidence } from "@/components/batch-evidence";
import { BatchFindings } from "@/components/batch-findings";
import { BatchReport } from "@/components/batch-report";
import { BatchOverview } from "@/components/batch-overview";
import { EmptyState, ErrorBox, Loading, StateBadge } from "@/components/ui";

const TABS = [
  { id: "overview", label: msg("Overview") },
  { id: "evidence", label: msg("Evidence") },
  { id: "findings", label: msg("Findings") },
  { id: "report", label: msg("Report") },
  { id: "decision", label: msg("Decision") },
  { id: "credit", label: msg("Credit") },
  { id: "audit", label: msg("Audit") },
] as const;
type TabId = (typeof TABS)[number]["id"];

function isTab(value: string | null): value is TabId {
  return TABS.some((tab) => tab.id === value);
}

export function BatchWorkspace({ batchId }: { batchId: string }) {
  const { t } = useI18n();
  const { role, configured, loading: personaLoading, version } = usePersona();
  const ready = !personaLoading && role !== null && configured;
  const initial = useSearchParams().get("tab");
  const [tab, setTab] = useState<TabId>(isTab(initial) ? initial : "overview");

  const batch = useApi<Batch>(ready ? `batches/${batchId}` : null, version);
  const report = useApi<Report>(ready ? `batches/${batchId}/report` : null, version);

  function refresh() {
    report.reload();
    batch.reload();
  }

  function choose(next: TabId) {
    setTab(next);
    window.history.replaceState(null, "", `?tab=${next}`);
  }

  function onKey(event: KeyboardEvent<HTMLButtonElement>, index: number) {
    const step = event.key === "ArrowRight" ? 1 : event.key === "ArrowLeft" ? -1 : 0;
    if (step === 0) return;
    event.preventDefault();
    const next = TABS[(index + step + TABS.length) % TABS.length];
    if (next) {
      choose(next.id);
      document.getElementById(`tab-${next.id}`)?.focus();
    }
  }

  const back = (
    <Link href="/batches" className="text-sm text-accent">
      ← {t("Batches")}
    </Link>
  );

  if (personaLoading) return <Loading label={t("Loading")} />;
  if (!role) return <EmptyState title={t("Choose a role to start")}>{t("Choose who you are acting as on the start page. This is a demo selector, not a sign-in.")}</EmptyState>;
  if (!configured) return <EmptyState title={t("This role isn't set up on the server")}>{t("Add its demo key to the server environment and reload.")}</EmptyState>;
  if (batch.error) {
    return (
      <div className="flex flex-col gap-3">
        {back}
        <ErrorBox failure={batch.error} onRetry={batch.reload} />
      </div>
    );
  }
  if (batch.loading || !batch.data) return <Loading label={t("Loading batch")} />;

  const data = batch.data;
  // A batch without a report answers 404 on the report route: that is a normal state, not an error.
  const missingReport = report.error instanceof ApiFailure && report.error.code === "NOT_FOUND";
  const reportFailure = report.error && !missingReport ? report.error : null;
  const currentReport = missingReport ? null : (report.data ?? null);

  return (
    <div className="flex flex-col gap-4">
      {back}
      <header className="flex flex-wrap items-center justify-between gap-2">
        <div>
          <h1 className="font-mono text-lg font-semibold">{data.batch_id}</h1>
          <p className="text-sm text-muted">
            {t(APPLICATION_LABELS[data.application_type] ?? data.application_type)}, {data.year}
          </p>
        </div>
        <StateBadge state={data.state} />
      </header>

      <div role="tablist" aria-label={t("Batch sections")} className="flex gap-1 border-b border-line">
        {TABS.map((item, index) => (
          <button
            key={item.id}
            id={`tab-${item.id}`}
            type="button"
            role="tab"
            aria-selected={tab === item.id}
            aria-controls={`panel-${item.id}`}
            tabIndex={tab === item.id ? 0 : -1}
            onClick={() => choose(item.id)}
            onKeyDown={(e) => onKey(e, index)}
            className={`-mb-px border-b-2 px-3 py-2 text-sm ${tab === item.id ? "border-accent font-medium text-ink" : "border-transparent text-muted hover:text-ink"}`}
          >
            {t(item.label)}
          </button>
        ))}
      </div>

      <div id={`panel-${tab}`} role="tabpanel" aria-labelledby={`tab-${tab}`} tabIndex={0}>
        {reportFailure ? <div className="mb-4"><ErrorBox failure={reportFailure} onRetry={report.reload} /></div> : null}
        {tab === "overview" ? <BatchOverview batch={data} report={currentReport} /> : null}
        {tab === "evidence" ? <BatchEvidence batchId={data.batch_id} evidence={data.evidence} onChanged={refresh} /> : null}
        {tab === "findings" ? <BatchFindings batch={data} report={currentReport} onChanged={refresh} /> : null}
        {tab === "report" ? <BatchReport batch={data} report={currentReport} /> : null}
        {tab === "decision" ? <BatchDecision batch={data} report={currentReport} onChanged={refresh} onOpenTab={choose} /> : null}
        {tab === "credit" ? <BatchCredit batch={data} onChanged={refresh} /> : null}
        {tab === "audit" ? <BatchAudit batchId={data.batch_id} /> : null}
      </div>
    </div>
  );
}
