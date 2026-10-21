import { render, screen, waitFor, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { readFileSync } from "node:fs";
import type { ReactNode } from "react";
import { afterEach, describe, expect, it, vi } from "vitest";
import { BatchWorkspace } from "@/components/batch-workspace";
import { CatalogProvider } from "@/lib/client/catalog";
import { PersonaProvider } from "@/lib/client/persona";
import { FINDING_TEXTS } from "@/lib/finding-texts";
import { I18nProvider } from "@/lib/i18n";
import type { Batch, Catalog, Finding, Report } from "@/lib/types";

vi.mock("next/navigation", () => ({ useSearchParams: () => new URLSearchParams(), usePathname: () => "/batches/b-1" }));
vi.mock("next/link", () => ({ default: ({ href, children }: { href: string; children: ReactNode }) => <a href={href}>{children}</a> }));

const finding = (over: Partial<Finding>): Finding => ({
  code: "PROVENANCE_SYNTHETIC", severity: "info", params: {}, source: "rule", blocks_calculation: false, blocks_verified: false, overridable: false, ...over,
});

const batch = (state: string): Batch => ({
  batch_id: "b-1", project_id: "prj-1", facility_id: "fac-1", year: 2026, biochar_type: "agricultural_residue", application_type: "soil",
  profile_id: "VM0044@1.2", parcel_key: "P", cell_set: [], product_batch_id: null, period_start: "2026-01-01", period_end: "2026-07-01",
  claimed_kg_co2e: 300000, state, created_at: "t", updated_at: "t", evidence: [],
});

const calc = {
  equation_steps: [
    { name: "CC", formula: "M * FC * PR_de", value: "71.200" },
    { name: "ER_y", formula: "ER_SS + ER_PS - PE_AS - LE", value: "261.0666666666666666666666667" },
  ],
  inputs: { dry_mass_t: "100", organic_carbon_fraction_source: "laboratory" },
  legs: [{ leg_id: "leg-1", counted: "false", reason: "distance below the 200 km threshold" }],
  params_used: [
    { name: "permanence.high_gt_600", page: 22, profile_id: "VM0044@1.2", value: "0.89", verified: true },
    { name: "permanence.high_gt_600", page: 22, profile_id: "VM0044@1.2", value: "0.89", verified: true },
    { name: "rules.some_limit", page: 30, profile_id: "VM0044@1.2", value: "0.7", verified: false },
  ],
  uncertainty: { contributions: [{ input: "dry_mass_t", relative_uncertainty: "0.02", delta_kg_low: -5221 }] },
};

const report = (findings: Finding[], overrides: Report["overrides"] = []): Report => ({
  report_id: "rep-1", evidence_hash: "f".repeat(64), batch_id: "b-1", status: "complete", recommendation: "human_review",
  kg_co2e: { low: 250728, central: 261067, high: 271614 }, issuable_kg: 250728, findings, profile_id: "VM0044@1.2", profile_label: "Verra VM0044 v1.2",
  facility_class: "high", blocks_calculation: false, blocks_verified: false, pending_items: 0, narrative_en: "The central estimate is 261067 kg CO2e.",
  grounding: { passed: true, numbers_checked: 9, discrepancies: [] }, overrides, calc,
});

const catalog: Catalog = { findings: [], states: [], terminal_states: [], editable_states: [], permissions: {}, errors: {}, evidence_kinds: {}, transitions: [] };
const json = (body: unknown, status = 200) => () => new Response(JSON.stringify(body), { status, headers: { "content-type": "application/json" } });

function serve(role: string, state: string, rep: Report, extra: Record<string, () => Response> = {}) {
  const table: Record<string, () => Response> = {
    "/api/persona": json({ role, configured: true }),
    "/api/cp/catalog": json(catalog),
    "/api/cp/batches/b-1/report": json(rep),
    "/api/cp/batches/b-1": json(batch(state)),
    ...extra,
  };
  return vi.spyOn(globalThis, "fetch").mockImplementation(async (input) => {
    const url = String(input);
    const hit = Object.keys(table).sort((a, b) => b.length - a.length).find((prefix) => url.startsWith(prefix));
    return hit ? (table[hit] as () => Response)() : new Response("{}", { status: 404 });
  });
}

function mount() {
  return render(
    <I18nProvider>
      <PersonaProvider>
        <CatalogProvider>
          <BatchWorkspace batchId="b-1" />
        </CatalogProvider>
      </PersonaProvider>
    </I18nProvider>,
  );
}

afterEach(() => vi.restoreAllMocks());

const rows: Finding[] = [
  finding({}),
  finding({ code: "TRANSPORT_DISTANCE_AT_THRESHOLD", severity: "low", overridable: true, params: { distance_km: "200", leg_id: "leg-2" } }),
  finding({ code: "MASS_BALANCE_MISMATCH", severity: "high", blocks_calculation: true, blocks_verified: true, params: { expected_t: "100", found_t: "200" } }),
];

describe("findings tab", () => {
  it("sorts by severity and states what each finding blocks, with its parameters", async () => {
    serve("verifier", "UNDER_REVIEW", report(rows));
    mount();
    await userEvent.click(await screen.findByRole("tab", { name: "Findings" }));
    const titles = (await screen.findAllByRole("heading", { level: 3 })).map((h) => h.textContent);
    expect(titles).toEqual(["Masses do not add up", "Transport distance is exactly at the threshold", "Synthetic data"]);
    expect(screen.getByText("Blocks the calculation")).toBeInTheDocument();
    expect(screen.getByText("Blocks verification")).toBeInTheDocument();
    expect(screen.getAllByText("Does not block").length).toBe(2);
    expect(screen.getByText("1 finding(s) block the next step.")).toBeInTheDocument();
    expect(screen.getByText("Expected t")).toBeInTheDocument();
    expect(screen.getAllByText("200", { selector: "dd" })).toHaveLength(2); // found_t and distance_km
  });

  it("lets a verifier accept an overridable finding with a reason, and asks for the reason first", async () => {
    const posted = vi.fn(json({ batch_id: "b-1", code: "TRANSPORT_DISTANCE_AT_THRESHOLD", report_id: "rep-1", actor_id: "verifier-1" }));
    const spy = serve("verifier", "UNDER_REVIEW", report(rows), { "/api/cp/batches/b-1/findings/override": posted });
    mount();
    await userEvent.click(await screen.findByRole("tab", { name: "Findings" }));
    await userEvent.click(await screen.findByRole("button", { name: "Accept with a reason" }));
    await userEvent.click(screen.getByRole("button", { name: "Accept finding" }));
    expect(await screen.findByRole("alert")).toHaveTextContent("Enter a reason first.");
    expect(posted).not.toHaveBeenCalled();
    await userEvent.type(screen.getByLabelText("Reason (required, recorded in the audit trail)"), "Checked the freight invoice");
    await userEvent.click(screen.getByRole("button", { name: "Accept finding" }));
    await waitFor(() => expect(posted).toHaveBeenCalledTimes(1));
    const call = spy.mock.calls.find(([url]) => String(url).endsWith("/findings/override")) as [string, RequestInit];
    expect(JSON.parse(String(call[1].body))).toEqual({ code: "TRANSPORT_DISTANCE_AT_THRESHOLD", reason: "Checked the freight invoice" });
    expect((call[1].headers as Record<string, string>)["Idempotency-Key"]).toBeTruthy();
  });

  it("shows no accept button to an owner or outside review, and shows who accepted a finding", async () => {
    serve("owner", "UNDER_REVIEW", report(rows));
    const first = mount();
    await userEvent.click(await screen.findByRole("tab", { name: "Findings" }));
    await screen.findAllByRole("heading", { level: 3 });
    expect(screen.queryByRole("button", { name: "Accept with a reason" })).not.toBeInTheDocument();
    first.unmount();

    const accepted = [{ code: "TRANSPORT_DISTANCE_AT_THRESHOLD", actor_id: "verifier-1", reason: "Checked the freight invoice", created_at: "t" }];
    vi.restoreAllMocks();
    serve("verifier", "UNDER_REVIEW", report(rows, accepted));
    mount();
    await userEvent.click(await screen.findByRole("tab", { name: "Findings" }));
    expect(await screen.findByText("Accepted by verifier-1")).toBeInTheDocument();
    expect(screen.getByText("Reason: Checked the freight invoice")).toBeInTheDocument();
    expect(screen.queryByRole("button", { name: "Accept with a reason" })).not.toBeInTheDocument();
  });
});

describe("report tab", () => {
  it("lays out the calculation, parameters with their check, uncertainty and the grounded summary", async () => {
    serve("verifier", "UNDER_REVIEW", report([finding({}), finding({ code: "REGISTRY_RECORD_FOUND", severity: "info", params: {} })]));
    mount();
    await userEvent.click(await screen.findByRole("tab", { name: "Report" }));
    expect(await screen.findByText("Organic carbon contained in the biochar")).toBeInTheDocument();
    expect(screen.getByText("71.2 t C")).toBeInTheDocument();
    expect(screen.getByText("261.0667 t CO2e")).toBeInTheDocument();
    expect(screen.getAllByText("permanence.high_gt_600")).toHaveLength(1); // duplicate parameter references are shown once
    expect(screen.getByText("Verified against the source")).toBeInTheDocument();
    expect(screen.getByText("Not confirmed")).toBeInTheDocument();
    expect(screen.getByText("±0.02")).toBeInTheDocument();
    expect(screen.getByText("Not counted")).toBeInTheDocument();
    const advisories = screen.getByText("Public-data advisories").closest("section") as HTMLElement;
    expect(within(advisories).getByText("Registry record found")).toBeInTheDocument();
    expect(screen.getByText("Every number in this text matched a computed figure (9 checked).")).toBeInTheDocument();
  });
});

describe("finding vocabulary", () => {
  it("has a title and a meaning for every finding code of the backend", () => {
    const source = readFileSync("../backend/src/climaudit/findings.py", "utf8");
    const codes = [...source.matchAll(/^ {4}"([A-Z_0-9]+)": _r\(/gm)].map((m) => m[1] as string);
    expect(codes.length).toBeGreaterThan(35);
    expect(codes.filter((c) => !(c in FINDING_TEXTS))).toEqual([]);
    expect(Object.keys(FINDING_TEXTS).filter((c) => !codes.includes(c))).toEqual([]);
  });
});
