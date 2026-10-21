"use client";

import { useI18n } from "@/lib/i18n";
import { humanize } from "@/lib/evidence-labels";
import { msg } from "@/lib/i18n-core";
import { formatKg } from "@/lib/format";
import { FINDING_TEXTS } from "@/lib/finding-texts";
import type { Batch, Report } from "@/lib/types";
import { HashChip } from "@/components/hash-chip";
import { RangeBar } from "@/components/range-bar";
import { Badge, Card } from "@/components/ui";

/** What each calculation step is called (VM0044 equation terms), with the unit of its value. */
const STEP_LABELS: Record<string, { label: string; unit: string }> = {
  CC: { label: msg("Organic carbon contained in the biochar"), unit: "t C" },
  gross_removal_tco2e: { label: msg("Gross removal"), unit: "t CO2e" },
  PE_P: { label: msg("Emissions from converting the biomass"), unit: "t CO2e" },
  PE_PS: { label: msg("Emissions at the production stage"), unit: "t CO2e" },
  ER_PS: { label: msg("Net removal at the production stage"), unit: "t CO2e" },
  PE_AS: { label: msg("Emissions at the application stage"), unit: "t CO2e" },
  LE: { label: msg("Leakage"), unit: "t CO2e" },
  ER_y: { label: msg("Net removals for the year"), unit: "t CO2e" },
};

const INPUT_LABELS: Record<string, string> = {
  dry_mass_t: msg("Dry mass of biochar (t)"),
  facility_total_dry_mass_t: msg("Facility total dry mass (t)"),
  organic_carbon_fraction: msg("Organic carbon fraction"),
  organic_carbon_fraction_source: msg("Where the carbon fraction comes from"),
  permanence_factor: msg("Permanence factor"),
  pe_d_tco2e: msg("Pre-treatment emissions (t CO2e)"),
  pe_c_tco2e: msg("Auxiliary energy emissions (t CO2e)"),
  e_p_tco2e: msg("Application-stage emissions (t CO2e)"),
  le_ts_tco2e: msg("Leakage from biomass transport (t CO2e)"),
  le_tap_tco2e: msg("Leakage from biochar transport (t CO2e)"),
};

const ADVISORY = new Set([
  "TRANSPORT_DISTANCE_IMPLAUSIBLE", "LAND_COVER_MISMATCH", "WEATHER_UNSUITABLE_FOR_APPLICATION", "REGISTRY_PROJECT_NOT_FOUND",
  "REGISTRY_METHODOLOGY_MISMATCH", "REGISTRY_VINTAGE_ALREADY_ISSUED", "REGISTRY_RECORD_FOUND", "REGISTRY_MANUAL_CHECK", "EXTERNAL_CHECK_UNAVAILABLE",
]);

type Calc = {
  equation_steps?: { name: string; formula: string; value: string }[];
  inputs?: Record<string, string>;
  legs?: { leg_id: string; counted: string; reason?: string; tco2?: string }[];
  params_used?: { name: string; value: string; page: number | null; profile_id: string; verified: boolean }[];
  uncertainty?: {
    method?: string;
    contributions?: { input: string; relative_uncertainty: string; delta_kg_low: number }[];
  };
};

/** Display only: a decimal string shown with up to four decimals. The calculation itself is done by the backend. */
function shown(value: string): string {
  const n = Number(value);
  return Number.isFinite(n) ? n.toLocaleString("en-US", { maximumFractionDigits: 4 }) : value;
}

export function BatchReport({ batch, report }: { batch: Batch; report: Report | null }) {
  const { t } = useI18n();
  if (!report) return <Card><p className="text-sm text-muted">{t("No report yet. The verification has not run for this batch.")}</p></Card>;
  const calc = (report.calc ?? {}) as Calc;
  const steps = calc.equation_steps ?? [];
  const params = (calc.params_used ?? []).filter((p, i, all) => all.findIndex((q) => q.name === p.name && q.value === p.value) === i);
  const advisories = report.findings.filter((f) => ADVISORY.has(f.code));

  return (
    <div className="flex flex-col gap-4">
      <Card>
        <h2 className="mb-3 text-base font-semibold">{t("Result")}</h2>
        {report.kg_co2e ? (
          <div className="flex flex-col gap-3">
            <RangeBar range={report.kg_co2e} claimed={batch.claimed_kg_co2e} />
            <p className="text-sm">
              {t("Issuable: {issuable} kg CO2e. It is the lower bound of the range and never exceeds the claim.", { issuable: formatKg(report.issuable_kg) })}
            </p>
          </div>
        ) : (
          <p className="text-sm text-muted">{t("The calculation could not finish yet: resolve the blocking findings and run the verification again.")}</p>
        )}
        <dl className="mt-3 grid grid-cols-1 gap-x-6 gap-y-1 text-sm sm:grid-cols-2">
          <div className="flex justify-between gap-3 border-b border-line py-1"><dt className="text-muted">{t("Methodology profile")}</dt><dd>{report.profile_label}</dd></div>
          <div className="flex justify-between gap-3 border-b border-line py-1"><dt className="text-muted">{t("Facility class")}</dt><dd>{report.facility_class ? humanize(report.facility_class) : "-"}</dd></div>
          <div className="flex justify-between gap-3 border-b border-line py-1"><dt className="text-muted">{t("Report")}</dt><dd className="font-mono text-xs">{report.report_id}</dd></div>
          <div className="flex justify-between gap-3 border-b border-line py-1"><dt className="text-muted">{t("Evidence hash")}</dt><dd><HashChip value={report.evidence_hash} label={t("Evidence hash")} /></dd></div>
        </dl>
      </Card>

      {steps.length > 0 ? (
        <Card>
          <h2 className="mb-1 text-base font-semibold">{t("How the number is built")}</h2>
          <p className="mb-3 text-sm text-muted">{t("Each step is computed by deterministic code from the evidence. The AI does no arithmetic.")}</p>
          <div className="overflow-x-auto">
            <table className="w-full min-w-[560px] text-left text-sm">
              <caption className="sr-only">{t("Calculation steps")}</caption>
              <thead className="text-xs text-muted">
                <tr>
                  <th scope="col" className="py-2 pr-3 font-medium">{t("Step")}</th>
                  <th scope="col" className="py-2 pr-3 font-medium">{t("Formula")}</th>
                  <th scope="col" className="py-2 text-right font-medium">{t("Value")}</th>
                </tr>
              </thead>
              <tbody>
                {steps.map((s) => {
                  const meta = STEP_LABELS[s.name];
                  return (
                    <tr key={s.name} className="border-t border-line">
                      <th scope="row" className="py-2 pr-3 text-left font-normal">{meta ? t(meta.label) : humanize(s.name)}</th>
                      <td className="py-2 pr-3 font-mono text-xs">{s.formula}</td>
                      <td className="py-2 text-right tabular-nums">{shown(s.value)}{meta ? ` ${meta.unit}` : ""}</td>
                    </tr>
                  );
                })}
              </tbody>
            </table>
          </div>
        </Card>
      ) : null}

      {calc.inputs ? (
        <Card>
          <h2 className="mb-3 text-base font-semibold">{t("Inputs of the calculation")}</h2>
          <dl className="grid grid-cols-1 gap-x-6 gap-y-1 text-sm sm:grid-cols-2">
            {Object.entries(calc.inputs).map(([key, value]) => (
              <div key={key} className="flex justify-between gap-3 border-b border-line py-1">
                <dt className="text-muted">{t(INPUT_LABELS[key] ?? humanize(key))}</dt>
                <dd className="tabular-nums">{shown(value)}</dd>
              </div>
            ))}
          </dl>
        </Card>
      ) : null}

      {params.length > 0 ? (
        <Card>
          <h2 className="mb-1 text-base font-semibold">{t("Methodology parameters used")}</h2>
          <p className="mb-3 text-sm text-muted">{t("Every factor comes from the methodology profile with its page. A parameter not confirmed against the source is marked.")}</p>
          <div className="overflow-x-auto">
            <table className="w-full min-w-[560px] text-left text-sm">
              <caption className="sr-only">{t("Methodology parameters used")}</caption>
              <thead className="text-xs text-muted">
                <tr>
                  <th scope="col" className="py-2 pr-3 font-medium">{t("Parameter")}</th>
                  <th scope="col" className="py-2 pr-3 text-right font-medium">{t("Value")}</th>
                  <th scope="col" className="py-2 pr-3 font-medium">{t("Profile and page")}</th>
                  <th scope="col" className="py-2 font-medium">{t("Checked")}</th>
                </tr>
              </thead>
              <tbody>
                {params.map((p) => (
                  <tr key={`${p.name}-${p.value}`} className="border-t border-line">
                    <th scope="row" className="py-2 pr-3 text-left font-mono text-xs font-normal">{p.name}</th>
                    <td className="py-2 pr-3 text-right tabular-nums">{p.value}</td>
                    <td className="py-2 pr-3 text-xs">{p.profile_id}{p.page ? `, ${t("page {page}", { page: p.page })}` : ""}</td>
                    <td className="py-2">{p.verified ? <Badge tone="ok">{t("Verified against the source")}</Badge> : <Badge tone="warn">{t("Not confirmed")}</Badge>}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </Card>
      ) : null}

      {calc.uncertainty?.contributions ? (
        <Card>
          <h2 className="mb-1 text-base font-semibold">{t("Where the range comes from")}</h2>
          <p className="mb-3 text-sm text-muted">{t("Every input is moved to its adverse and its favorable bound. This is a conservative interval, not a probability.")}</p>
          <table className="w-full text-left text-sm">
            <caption className="sr-only">{t("Uncertainty by input")}</caption>
            <thead className="text-xs text-muted">
              <tr>
                <th scope="col" className="py-2 pr-3 font-medium">{t("Input")}</th>
                <th scope="col" className="py-2 pr-3 text-right font-medium">{t("Relative uncertainty")}</th>
                <th scope="col" className="py-2 text-right font-medium">{t("Effect on the low value (kg CO2e)")}</th>
              </tr>
            </thead>
            <tbody>
              {calc.uncertainty.contributions.map((c) => (
                <tr key={c.input} className="border-t border-line">
                  <th scope="row" className="py-2 pr-3 text-left font-mono text-xs font-normal">{c.input}</th>
                  <td className="py-2 pr-3 text-right tabular-nums">±{c.relative_uncertainty}</td>
                  <td className="py-2 text-right tabular-nums">{formatKg(c.delta_kg_low)}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </Card>
      ) : null}

      {calc.legs && calc.legs.length > 0 ? (
        <Card>
          <h2 className="mb-3 text-base font-semibold">{t("Transport legs")}</h2>
          <ul className="flex flex-col gap-1 text-sm">
            {calc.legs.map((leg) => (
              <li key={leg.leg_id} className="flex flex-wrap items-center gap-2">
                <span className="font-mono text-xs">{leg.leg_id}</span>
                {leg.counted === "true" ? <Badge tone="warn">{t("Counted as leakage")}</Badge> : <Badge tone="neutral">{t("Not counted")}</Badge>}
                <span className="text-muted">{leg.reason ?? (leg.tco2 ? `${shown(leg.tco2)} t CO2` : "")}</span>
              </li>
            ))}
          </ul>
        </Card>
      ) : null}

      {advisories.length > 0 ? (
        <Card>
          <h2 className="mb-1 text-base font-semibold">{t("Public-data advisories")}</h2>
          <p className="mb-3 text-sm text-muted">{t("These checks use public datasets. They never change a number and never block a decision.")}</p>
          <ul className="flex flex-col gap-1 text-sm">
            {advisories.map((f, i) => (
              <li key={`${f.code}-${i}`}>{t((FINDING_TEXTS[f.code] ?? { title: f.code }).title)}</li>
            ))}
          </ul>
        </Card>
      ) : null}

      {report.narrative_en ? (
        <Card>
          <h2 className="mb-1 text-base font-semibold">{t("Summary text")}</h2>
          <p className="text-sm">{report.narrative_en}</p>
          {report.grounding ? (
            <p className="mt-2 text-xs text-muted">
              {report.grounding.passed
                ? t("Every number in this text matched a computed figure ({n} checked).", { n: report.grounding.numbers_checked })
                : t("A number in this text did not match a computed figure.")}
            </p>
          ) : null}
        </Card>
      ) : null}
    </div>
  );
}
