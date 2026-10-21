"use client";

import { useI18n } from "@/lib/i18n";
import { msg } from "@/lib/i18n-core";
import { Card } from "@/components/ui";

const SOURCES: { name: string; use: string; licence: string }[] = [
  { name: msg("Berkeley Voluntary Registry Offsets Database"), use: msg("Registry cross-check (advisory)"), licence: msg("CC BY 4.0") },
  { name: msg("ESA WorldCover 2021"), use: msg("Land cover cross-check (advisory)"), licence: msg("CC BY 4.0") },
  { name: msg("Open-Meteo historical weather (ERA5)"), use: msg("Weather cross-check (advisory)"), licence: msg("CC BY 4.0, non-commercial use") },
  { name: msg("Hedera network and the HashScan explorer"), use: msg("Audit hashes and the credit token on a test network"), licence: msg("Public network") },
  { name: msg("Hedera Guardian and its Hello World tutorial policy"), use: msg("Audit policy anchored through Guardian"), licence: msg("Apache-2.0") },
  { name: msg("Verra VM0044 v1.2 and CDM tools 03, 05, 07, 12 and 16"), use: msg("Methodology equations and defaults"), licence: msg("Read from the published documents") },
];

export function AboutView() {
  const { t } = useI18n();
  return (
    <div className="flex flex-col gap-4">
      <h1 className="text-lg font-semibold">{t("About")}</h1>

      <Card>
        <h2 className="mb-2 text-base font-semibold">{t("What you are looking at")}</h2>
        <p className="text-sm">{t("ClimAudit is a hackathon prototype for checking the evidence behind biochar carbon credits. Everything shown is synthetic demonstration data, and the ledger is a test network. No credit here is real.")}</p>
      </Card>

      <Card>
        <h2 className="mb-2 text-base font-semibold">{t("How AI is used")}</h2>
        <ul className="list-disc space-y-1 pl-5 text-sm">
          <li>{t("An optional AI assistant can read documents and propose values with a quote. It cannot approve, issue, sign or calculate.")}</li>
          <li>{t("A value counts only if its quote is really in the document and a person confirms it.")}</li>
          <li>{t("All numbers come from deterministic code. A human verifier decides.")}</li>
          <li>{t("The software was written with the help of an AI coding assistant.")}</li>
        </ul>
      </Card>

      <Card>
        <h2 className="mb-2 text-base font-semibold">{t("Data and software")}</h2>
        <div className="overflow-x-auto">
          <table className="w-full min-w-[560px] text-left text-sm">
            <caption className="sr-only">{t("Data and software sources")}</caption>
            <thead className="text-xs text-muted">
              <tr>
                <th scope="col" className="py-2 pr-3 font-medium">{t("Source")}</th>
                <th scope="col" className="py-2 pr-3 font-medium">{t("Used for")}</th>
                <th scope="col" className="py-2 font-medium">{t("Licence")}</th>
              </tr>
            </thead>
            <tbody>
              {SOURCES.map((s) => (
                <tr key={s.name} className="border-t border-line align-top">
                  <th scope="row" className="py-2 pr-3 text-left font-normal">{t(s.name)}</th>
                  <td className="py-2 pr-3">{t(s.use)}</td>
                  <td className="py-2">{t(s.licence)}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
        <p className="mt-3 text-xs text-muted">{t("Registry data: Quartson, Haya, Bernard, Abayo, Rong, So and Elias, Voluntary Registry Offsets Database, Berkeley Carbon Trading Project, University of California, Berkeley.")}</p>
      </Card>
    </div>
  );
}
