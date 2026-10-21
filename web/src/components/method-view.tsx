"use client";

import { useI18n } from "@/lib/i18n";
import { useApi } from "@/lib/client/api";
import { usePersona } from "@/lib/client/persona";
import { collectParameters } from "@/lib/profile-rows";
import type { ProfileDoc } from "@/lib/types";
import { Badge, Card, EmptyState, ErrorBox, Loading } from "@/components/ui";

export function MethodView() {
  const { t } = useI18n();
  const { role, configured, loading: personaLoading, version } = usePersona();
  const ready = !personaLoading && role !== null && configured;
  const ids = useApi<string[]>(ready ? "profiles" : null, version);
  const first = ids.data?.find((id) => id.startsWith("VM0044")) ?? null;
  const profile = useApi<ProfileDoc>(first ? `profiles/${first}` : null, version);
  const rows = profile.data ? collectParameters(profile.data) : [];
  const unverified = rows.filter((r) => !r.verified).length;

  return (
    <div className="flex flex-col gap-4">
      <h1 className="text-lg font-semibold">{t("Method")}</h1>

      <Card>
        <h2 className="mb-2 text-base font-semibold">{t("What is computed")}</h2>
        <p className="text-sm">{t("ClimAudit checks the evidence of a biochar batch against Verra methodology VM0044 v1.2 and computes the carbon dioxide removed, as a range.")}</p>
        <ol className="mt-3 list-decimal space-y-1 pl-5 text-sm">
          <li>{t("The organic carbon in the biochar is its dry mass times its carbon fraction times a permanence factor that depends on the pyrolysis temperature.")}</li>
          <li>{t("That carbon is converted to carbon dioxide by the factor 44/12.")}</li>
          <li>{t("Emissions from producing the biochar, applying it and moving it more than 200 km are subtracted.")}</li>
          <li>{t("Every input is moved to its adverse and its favorable bound to get the low and high values. Only the low value can be issued, and never more than the claim.")}</li>
        </ol>
        <p className="mt-3 text-sm text-muted">{t("The arithmetic is done by deterministic code with exact decimals. The AI assistant, when used, only proposes values from documents and a person confirms them.")}</p>
      </Card>

      {!ready ? (
        <EmptyState title={t("Choose a role to see the parameters")}>{t("The methodology parameters are read from the server. Choose a role on the start page.")}</EmptyState>
      ) : ids.error ? (
        <ErrorBox failure={ids.error} onRetry={ids.reload} />
      ) : profile.error ? (
        <ErrorBox failure={profile.error} onRetry={profile.reload} />
      ) : !profile.data ? (
        <Loading label={t("Loading")} />
      ) : (
        <Card>
          <h2 className="mb-1 text-base font-semibold">{profile.data.label}</h2>
          <p className="mb-3 text-sm text-muted">
            {t("Every number the calculation takes from the methodology, with its page in the source document ({document}, read on {date}). {n} of {total} are not confirmed against the source.", {
              document: profile.data.source?.document ?? "-",
              date: profile.data.source?.retrieved ?? "-",
              n: unverified,
              total: rows.length,
            })}
          </p>
          <div className="overflow-x-auto">
            <table className="w-full min-w-[640px] text-left text-sm">
              <caption className="sr-only">{t("Methodology parameters")}</caption>
              <thead className="text-xs text-muted">
                <tr>
                  <th scope="col" className="py-2 pr-3 font-medium">{t("Parameter")}</th>
                  <th scope="col" className="py-2 pr-3 text-right font-medium">{t("Value")}</th>
                  <th scope="col" className="py-2 pr-3 font-medium">{t("Page")}</th>
                  <th scope="col" className="py-2 pr-3 font-medium">{t("Checked")}</th>
                  <th scope="col" className="py-2 font-medium">{t("Note")}</th>
                </tr>
              </thead>
              <tbody>
                {rows.map((r) => (
                  <tr key={r.name} className="border-t border-line align-top">
                    <th scope="row" className="py-2 pr-3 text-left font-mono text-xs font-normal">{r.name}</th>
                    <td className="py-2 pr-3 text-right tabular-nums">{r.value}</td>
                    <td className="py-2 pr-3 tabular-nums">{r.page ?? "-"}</td>
                    <td className="py-2 pr-3">{r.verified ? <Badge tone="ok">{t("Verified against the source")}</Badge> : <Badge tone="warn">{t("Not confirmed")}</Badge>}</td>
                    <td className="py-2 text-xs text-muted">{r.note ?? ""}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </Card>
      )}
    </div>
  );
}
