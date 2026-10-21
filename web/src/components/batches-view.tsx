"use client";

import Link from "next/link";
import type { ReactNode } from "react";
import { useI18n } from "@/lib/i18n";
import { useApi } from "@/lib/client/api";
import { usePersona } from "@/lib/client/persona";
import { formatDate, formatKg, isKgRange } from "@/lib/format";
import { Card, EmptyState, ErrorBox, Loading, StateBadge } from "@/components/ui";

export type BatchRow = {
  batch_id: string;
  project_id: string;
  year: number;
  biochar_type: string;
  application_type: string;
  state: string;
  claimed_kg_co2e: number | null;
  updated_at: string | null;
  report: { status: string | null; recommendation: string | null; kg_co2e: unknown; issuable_kg: number | null } | null;
};

export function BatchesView() {
  const { t } = useI18n();
  const { role, configured, loading: personaLoading, version } = usePersona();
  const idle = personaLoading || !role || !configured;
  const { data, error, loading, reload } = useApi<BatchRow[]>(idle ? null : "batches", version);

  let body: ReactNode;
  if (personaLoading) body = <Loading label={t("Loading")} />;
  else if (!role) body = <EmptyState title={t("Choose a role to start")}>{t("Choose who you are acting as on the start page. This is a demo selector, not a sign-in.")}</EmptyState>;
  else if (!configured) body = <EmptyState title={t("This role isn't set up on the server")}>{t("Add its demo key to the server environment and reload.")}</EmptyState>;
  else if (error) body = <ErrorBox failure={error} onRetry={reload} />;
  else if (loading || !data) body = <Loading label={t("Loading batches")} />;
  else if (data.length === 0) body = <EmptyState title={t("No batches yet")}>{t("Batches you can see will appear here.")}</EmptyState>;
  else body = <BatchesTable rows={data} />;

  return (
    <div className="flex flex-col gap-4">
      <h1 className="text-lg font-semibold">{t("Batches")}</h1>
      {body}
    </div>
  );
}

function rangeText(b: BatchRow, t: (key: string, params?: Record<string, string | number>) => string): string {
  return b.report && isKgRange(b.report.kg_co2e) ? t("{low} to {high}", { low: formatKg(b.report.kg_co2e.low), high: formatKg(b.report.kg_co2e.high) }) : "-";
}

function BatchesTable({ rows }: { rows: BatchRow[] }) {
  const { t } = useI18n();
  return (
    <>
      <ul aria-label={t("Batches you can see, with state and computed range")} className="flex flex-col gap-3 md:hidden">
        {rows.map((b) => (
          <li key={b.batch_id} className="rounded-xl border border-line bg-surface p-3 text-sm">
            <div className="flex items-center justify-between gap-2">
              <Link href={`/batches/${b.batch_id}`} className="font-mono text-xs text-accent underline">{b.batch_id}</Link>
              <StateBadge state={b.state} />
            </div>
            <dl className="mt-2 grid grid-cols-2 gap-x-3 gap-y-1">
              <dt className="text-muted">{t("Year")}</dt>
              <dd className="text-right tabular-nums">{b.year}</dd>
              <dt className="text-muted">{t("Claimed (kg CO2e)")}</dt>
              <dd className="text-right tabular-nums">{formatKg(b.claimed_kg_co2e)}</dd>
              <dt className="text-muted">{t("Computed range (kg CO2e)")}</dt>
              <dd className="text-right tabular-nums">{rangeText(b, t)}</dd>
              <dt className="text-muted">{t("Updated")}</dt>
              <dd className="text-right">{formatDate(b.updated_at)}</dd>
            </dl>
          </li>
        ))}
      </ul>
      <Card className="hidden overflow-x-auto md:block">
        <table className="w-full min-w-[640px] text-left text-sm">
          <caption className="sr-only">{t("Batches you can see, with state and computed range")}</caption>
          <thead className="text-xs text-muted">
            <tr>
              <th scope="col" className="py-2 pr-3 font-medium">{t("Batch")}</th>
              <th scope="col" className="py-2 pr-3 font-medium">{t("State")}</th>
              <th scope="col" className="py-2 pr-3 font-medium">{t("Year")}</th>
              <th scope="col" className="py-2 pr-3 text-right font-medium">{t("Claimed (kg CO2e)")}</th>
              <th scope="col" className="py-2 pr-3 text-right font-medium">{t("Computed range (kg CO2e)")}</th>
              <th scope="col" className="py-2 font-medium">{t("Updated")}</th>
            </tr>
          </thead>
          <tbody>
            {rows.map((b) => (
              <tr key={b.batch_id} className="border-t border-line">
                <th scope="row" className="py-2 pr-3 text-left font-mono text-xs font-normal"><Link href={`/batches/${b.batch_id}`} className="text-accent underline">{b.batch_id}</Link></th>
                <td className="py-2 pr-3"><StateBadge state={b.state} /></td>
                <td className="py-2 pr-3">{b.year}</td>
                <td className="py-2 pr-3 text-right tabular-nums">{formatKg(b.claimed_kg_co2e)}</td>
                <td className="py-2 pr-3 text-right tabular-nums">{rangeText(b, t)}</td>
                <td className="py-2">{formatDate(b.updated_at)}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </Card>
    </>
  );
}
