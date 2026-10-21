"use client";

import { useI18n } from "@/lib/i18n";
import { msg } from "@/lib/i18n-core";
import { useApi } from "@/lib/client/api";
import { useConfig } from "@/lib/client/catalog";
import { hashscanTopic, hashscanTransaction } from "@/lib/hashscan";
import type { AuditEvent } from "@/lib/types";
import { HashChip } from "@/components/hash-chip";
import { VerifyPanel } from "@/components/verify-panel";
import { Card, ErrorBox, Loading, ProvenanceDot } from "@/components/ui";

const EVENT_LABELS: Record<string, string> = {
  batch_submitted: msg("Batch submitted"),
  evidence_attached: msg("Evidence attached"),
  report_issued: msg("Report issued"),
  state_changed: msg("State changed"),
  credit_issued: msg("Credits issued"),
  credit_transferred: msg("Credits transferred"),
  credit_retired: msg("Credits retired"),
  correction: msg("Correction or accepted finding"),
};

function ExplorerLink({ href, children }: { href: string | null; children: string }) {
  return href ? <a href={href} target="_blank" rel="noreferrer" className="text-accent underline">{children}</a> : <span>{children}</span>;
}

export function BatchAudit({ batchId }: { batchId: string }) {
  const { t } = useI18n();
  const config = useConfig();
  const { data, error, loading, reload } = useApi<AuditEvent[]>(`audit/${batchId}`);
  if (error) return <ErrorBox failure={error} onRetry={reload} />;
  if (loading || !data) return <Loading label={t("Loading")} />;
  const topic = data.find((e) => e.ledger_ref)?.ledger_ref?.topic_id ?? null;
  const topicLink = hashscanTopic(config?.hashscan_base, topic);

  return (
    <div className="flex flex-col gap-4">
      <Card>
        <h2 className="mb-1 text-base font-semibold">{t("Audit trail")}</h2>
        <p className="text-sm text-muted">
          {t("Every step of this batch is an event. Each event carries the hash of the one before it, so changing the past breaks the chain. The hash, not the evidence, is published on the ledger.")}
        </p>
        {topic ? (
          <p className="mt-2 text-sm">
            {t("Ledger topic")}: <ExplorerLink href={topicLink}>{topic}</ExplorerLink>
          </p>
        ) : null}
      </Card>

      <Card>
        {data.length === 0 ? (
          <p className="text-sm text-muted">{t("No events yet.")}</p>
        ) : (
          <div className="overflow-x-auto">
            <table className="w-full min-w-[720px] text-left text-sm">
              <caption className="sr-only">{t("Audit events of the batch")}</caption>
              <thead className="text-xs text-muted">
                <tr>
                  <th scope="col" className="py-2 pr-3 font-medium">{t("No.")}</th>
                  <th scope="col" className="py-2 pr-3 font-medium">{t("Event")}</th>
                  <th scope="col" className="py-2 pr-3 font-medium">{t("Time (UTC)")}</th>
                  <th scope="col" className="py-2 pr-3 font-medium">{t("Event hash")}</th>
                  <th scope="col" className="py-2 pr-3 font-medium">{t("Previous hash")}</th>
                  <th scope="col" className="py-2 font-medium">{t("On the ledger")}</th>
                </tr>
              </thead>
              <tbody>
                {data.map((e) => (
                  <tr key={e.seq} className="border-t border-line align-top">
                    <td className="py-2 pr-3 tabular-nums">{e.seq}</td>
                    <th scope="row" className="py-2 pr-3 text-left font-normal">
                      {t(EVENT_LABELS[e.type] ?? e.type)}
                      <span className="block"><ProvenanceDot provenance={e.provenance} /></span>
                    </th>
                    <td className="py-2 pr-3 text-xs tabular-nums">{e.ts.replace("T", " ").replace("Z", "")}</td>
                    <td className="py-2 pr-3"><HashChip value={e.hash} label={t("Event hash")} /></td>
                    <td className="py-2 pr-3"><HashChip value={e.prev_hash} label={t("Previous hash")} /></td>
                    <td className="py-2 text-xs">
                      {e.ledger_ref ? (
                        <>
                          <span className="block">{t("Message {n}", { n: e.ledger_ref.sequence })}</span>
                          {e.ledger_ref.tx_id ? <ExplorerLink href={hashscanTransaction(config?.hashscan_base, e.ledger_ref.tx_id)}>{e.ledger_ref.tx_id}</ExplorerLink> : null}
                        </>
                      ) : (
                        "-"
                      )}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </Card>
      <VerifyPanel />
    </div>
  );
}
