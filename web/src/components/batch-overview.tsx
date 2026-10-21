"use client";

import { useI18n } from "@/lib/i18n";
import { useCatalog } from "@/lib/client/catalog";
import { usePersona } from "@/lib/client/persona";
import { formatDate, formatKg } from "@/lib/format";
import { APPLICATION_LABELS, RECOMMENDATION_LABELS, ROLE_LABELS, SEVERITY_LABELS, STATE_LABELS } from "@/lib/messages";
import { humanize } from "@/lib/evidence-labels";
import type { Batch, Report } from "@/lib/types";
import { RangeBar } from "@/components/range-bar";
import { StateTimeline } from "@/components/state-timeline";
import { Badge, Card } from "@/components/ui";

const SEVERITY_ORDER = ["critical", "high", "medium", "low", "info"] as const;
const SEVERITY_TONE: Record<string, "bad" | "warn" | "info" | "neutral"> = { critical: "bad", high: "bad", medium: "warn", low: "info", info: "neutral" };

export function BatchOverview({ batch, report }: { batch: Batch; report: Report | null }) {
  const { t } = useI18n();
  const { role } = usePersona();
  const catalog = useCatalog();
  const nextStates = role && catalog ? catalog.transitions.filter((x) => x.from === batch.state && x.roles.includes(role)).map((x) => x.to) : [];
  const counts = report ? SEVERITY_ORDER.map((s) => ({ severity: s, n: report.findings.filter((f) => f.severity === s).length })).filter((c) => c.n > 0) : [];
  const blocking = report ? report.findings.filter((f) => f.blocks_calculation || f.blocks_verified).length : 0;
  const pending = batch.evidence.filter((e) => e.confirmation === "pending_confirmation").length;

  return (
    <div className="flex flex-col gap-4">
      <Card>
        <h2 className="mb-3 text-base font-semibold">{t("Progress")}</h2>
        <StateTimeline state={batch.state} />
      </Card>

      <Card>
        <h2 className="mb-3 text-base font-semibold">{t("Claim and computed range")}</h2>
        {report && report.kg_co2e ? (
          <div className="flex flex-col gap-3">
            <RangeBar range={report.kg_co2e} claimed={batch.claimed_kg_co2e} />
            <p className="text-sm">
              {t("At most {issuable} kg CO2e could be issued: the lower bound, and never above the claim of {claimed} kg.", {
                issuable: formatKg(report.issuable_kg),
                claimed: formatKg(batch.claimed_kg_co2e),
              })}
            </p>
            <p>
              <Badge tone={report.recommendation === "human_review" ? "ok" : report.recommendation === "return" ? "warn" : "bad"}>
                {t(RECOMMENDATION_LABELS[report.recommendation] ?? report.recommendation)}
              </Badge>
            </p>
            <p className="text-xs text-muted">{t("Computed with {profile}. A recommendation is not a ruling: a verifier decides.", { profile: report.profile_label })}</p>
          </div>
        ) : (
          <p className="text-sm text-muted">
            {report
              ? t("The calculation could not finish yet: resolve the blocking findings and run the verification again.")
              : t("No report yet. The verification has not run for this batch.")}
          </p>
        )}
      </Card>

      <div className="grid gap-4 md:grid-cols-2">
        <Card>
          <h2 className="mb-3 text-base font-semibold">{t("Findings")}</h2>
          {report ? (
            counts.length > 0 ? (
              <div className="flex flex-col gap-2">
                <ul className="flex flex-wrap gap-2">
                  {counts.map((c) => (
                    <li key={c.severity}>
                      <Badge tone={SEVERITY_TONE[c.severity] ?? "neutral"}>{t("{n} {severity}", { n: c.n, severity: t(SEVERITY_LABELS[c.severity] ?? c.severity) })}</Badge>
                    </li>
                  ))}
                </ul>
                <p className="text-sm">{blocking > 0 ? t("{n} finding(s) block the next step.", { n: blocking }) : t("No finding blocks the next step.")}</p>
              </div>
            ) : (
              <p className="text-sm">{t("No findings.")}</p>
            )
          ) : (
            <p className="text-sm text-muted">{t("Findings appear after the verification runs.")}</p>
          )}
          {pending > 0 ? <p className="mt-2 text-sm text-warn-ink">{t("{n} evidence item(s) wait for a person to confirm them.", { n: pending })}</p> : null}
        </Card>

        <Card>
          <h2 className="mb-3 text-base font-semibold">{t("Next steps for your role")}</h2>
          {!role ? (
            <p className="text-sm text-muted">{t("Choose a role to see what you can do.")}</p>
          ) : nextStates.length > 0 ? (
            <div className="flex flex-col gap-2 text-sm">
              <p>{t("As {role} you can move this batch to:", { role: t(ROLE_LABELS[role] ?? role) })}</p>
              <ul className="flex flex-wrap gap-2">
                {nextStates.map((s) => (
                  <li key={s}>
                    <Badge tone="neutral">{t(STATE_LABELS[s] ?? s)}</Badge>
                  </li>
                ))}
              </ul>
            </div>
          ) : (
            <p className="text-sm text-muted">{t("As {role} you have no state change available now.", { role: t(ROLE_LABELS[role] ?? role) })}</p>
          )}
        </Card>
      </div>

      <Card>
        <h2 className="mb-3 text-base font-semibold">{t("Batch details")}</h2>
        <dl className="grid grid-cols-1 gap-x-6 gap-y-2 text-sm sm:grid-cols-2">
          <Detail label={t("Application")} value={t(APPLICATION_LABELS[batch.application_type] ?? batch.application_type)} />
          <Detail label={t("Biochar type")} value={humanize(batch.biochar_type)} />
          <Detail label={t("Year")} value={String(batch.year)} />
          <Detail label={t("Period")} value={`${formatDate(batch.period_start)} → ${formatDate(batch.period_end)}`} />
          <Detail label={t("Parcel")} value={batch.parcel_key ?? "-"} />
          <Detail label={t("Parcel cells")} value={String(batch.cell_set.length)} />
          <Detail label={t("Project")} value={batch.project_id} mono />
          <Detail label={t("Facility")} value={batch.facility_id} mono />
          <Detail label={t("Methodology profile")} value={batch.profile_id} />
          <Detail label={t("Updated")} value={formatDate(batch.updated_at)} />
        </dl>
      </Card>
    </div>
  );
}

function Detail({ label, value, mono = false }: { label: string; value: string; mono?: boolean }) {
  return (
    <div className="flex justify-between gap-3 border-b border-line py-1">
      <dt className="text-muted">{label}</dt>
      <dd className={mono ? "font-mono text-xs" : ""}>{value}</dd>
    </div>
  );
}
