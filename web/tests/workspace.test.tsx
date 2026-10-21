import { render, screen, waitFor, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import type { ReactNode } from "react";
import { afterEach, describe, expect, it, vi } from "vitest";
import { BatchWorkspace } from "@/components/batch-workspace";
import { StateTimeline } from "@/components/state-timeline";
import { CatalogProvider } from "@/lib/client/catalog";
import { PersonaProvider } from "@/lib/client/persona";
import { I18nProvider } from "@/lib/i18n";
import type { Batch, Catalog, EvidenceItem, Report } from "@/lib/types";

vi.mock("next/navigation", () => ({ useSearchParams: () => new URLSearchParams(), usePathname: () => "/batches/b-1" }));
vi.mock("next/link", () => ({ default: ({ href, children }: { href: string; children: ReactNode }) => <a href={href}>{children}</a> }));

const item = (over: Partial<EvidenceItem>): EvidenceItem => ({
  item_id: "i-1", kind: "dry_mass_biochar", value: "100", unit: "t", group: null, measured_at: null, source: "owner", provenance: "synthetic",
  rel_uncertainty: "0.02", document_ref: "lab-1", confirmation: "confirmed", span: null, ...over,
});

const batch = (state: string, evidence: EvidenceItem[]): Batch => ({
  batch_id: "b-1", project_id: "prj-1", facility_id: "fac-1", year: 2026, biochar_type: "agricultural_residue", application_type: "soil",
  profile_id: "VM0044@1.2", parcel_key: "PARCEL-A", cell_set: ["a", "b"], product_batch_id: null, period_start: "2026-01-01", period_end: "2026-07-01",
  claimed_kg_co2e: 300000, state, created_at: "2026-10-18T00:00:00Z", updated_at: "2026-10-18T00:00:00Z", evidence,
});

const report: Report = {
  report_id: "rep-1", evidence_hash: "abc", batch_id: "b-1", status: "complete", recommendation: "human_review",
  kg_co2e: { low: 250728, central: 261067, high: 271614 }, issuable_kg: 250728,
  findings: [{ code: "PROVENANCE_SYNTHETIC", severity: "info", params: {}, source: "rule", blocks_calculation: false, blocks_verified: false, overridable: false }],
  profile_id: "VM0044@1.2", profile_label: "Verra VM0044 v1.2", facility_class: "high", blocks_calculation: false, blocks_verified: false, pending_items: 0, narrative_en: null, grounding: null,
};

const catalog: Catalog = {
  findings: [], states: [], terminal_states: [], editable_states: [], permissions: {}, errors: {}, evidence_kinds: {},
  transitions: [
    { from: "UNDER_REVIEW", to: "VERIFIED", roles: ["verifier"], reason_required: false },
    { from: "UNDER_REVIEW", to: "REJECTED", roles: ["verifier", "admin"], reason_required: true },
    { from: "VERIFIED", to: "ISSUED", roles: ["registry"], reason_required: false },
  ],
};

const json = (body: unknown, status = 200) => () => new Response(JSON.stringify(body), { status, headers: { "content-type": "application/json" } });

function serve(table: Record<string, () => Response>) {
  return vi.spyOn(globalThis, "fetch").mockImplementation(async (input) => {
    const url = String(input);
    const hit = Object.keys(table).sort((a, b) => b.length - a.length).find((prefix) => url.startsWith(prefix));
    return hit ? (table[hit] as () => Response)() : new Response("{}", { status: 404 });
  });
}

function mount(node: ReactNode) {
  return render(
    <I18nProvider>
      <PersonaProvider>
        <CatalogProvider>{node}</CatalogProvider>
      </PersonaProvider>
    </I18nProvider>,
  );
}

afterEach(() => vi.restoreAllMocks());

describe("batch workspace", () => {
  it("shows progress, the range against the claim, the recommendation and the next steps of the persona", async () => {
    serve({
      "/api/persona": json({ role: "verifier", configured: true }),
      "/api/cp/catalog": json(catalog),
      "/api/cp/batches/b-1/report": json(report),
      "/api/cp/batches/b-1": json(batch("UNDER_REVIEW", [item({})])),
    });
    mount(<BatchWorkspace batchId="b-1" />);
    expect(await screen.findByRole("heading", { name: "b-1" })).toBeInTheDocument();
    expect(await screen.findByRole("img", { name: /Range 250,728 to 271,614 kg CO2e/ })).toBeInTheDocument();
    expect(screen.getByText(/At most 250,728 kg CO2e could be issued/)).toBeInTheDocument();
    expect(screen.getByText("Recommended: send for human review")).toBeInTheDocument();
    expect(screen.getByText("1 Info")).toBeInTheDocument();
    expect(screen.getByText("No finding blocks the next step.")).toBeInTheDocument();
    await waitFor(() => expect(screen.getByText("As Verifier you can move this batch to:")).toBeInTheDocument());
    const next = screen.getByText("As Verifier you can move this batch to:").parentElement as HTMLElement;
    expect(within(next).getByText("Verified")).toBeInTheDocument();
    expect(within(next).getByText("Rejected")).toBeInTheDocument();
    expect(within(next).queryByText("Issued")).not.toBeInTheDocument();
  });

  it("treats a missing report as a normal state, not an error", async () => {
    serve({
      "/api/persona": json({ role: "owner", configured: true }),
      "/api/cp/catalog": json(catalog),
      "/api/cp/batches/b-1/report": json({ error: { code: "NOT_FOUND", params: { resource: "report" }, correlation_id: "c" } }, 404),
      "/api/cp/batches/b-1": json(batch("DRAFT", [])),
    });
    mount(<BatchWorkspace batchId="b-1" />);
    expect(await screen.findByText("No report yet. The verification has not run for this batch.")).toBeInTheDocument();
    expect(screen.queryByRole("alert")).not.toBeInTheDocument();
  });

  it("explains a batch that cannot be read", async () => {
    serve({
      "/api/persona": json({ role: "owner", configured: true }),
      "/api/cp/catalog": json(catalog),
      "/api/cp/batches/b-9": json({ error: { code: "BATCH_NOT_FOUND", params: {}, correlation_id: "c" } }, 404),
    });
    mount(<BatchWorkspace batchId="b-9" />);
    expect(await screen.findByRole("alert")).toHaveTextContent("That batch doesn't exist, or you can't see it.");
  });

  it("lists evidence with provenance and status, separates pending proposals and loads the sanitized text on demand", async () => {
    const evidence = [
      item({ item_id: "i-1" }),
      item({ item_id: "i-2", kind: "h_corg_molar", value: "0.2", unit: "ratio", provenance: "measured", rel_uncertainty: null }),
      item({ item_id: "i-3", kind: "transport_distance_km_return", value: "35", unit: "km", group: "leg-1" }),
      item({ item_id: "i-4", kind: "pyrolysis_temp_c", value: "650", unit: "celsius", source: "model", confirmation: "pending_confirmation", span: { quote: "pyrolysis at 650 C", page: 1 } }),
      item({ item_id: "i-5", kind: "lab_accredited", value: "true", unit: "" }),
    ];
    const text = vi.fn(json({ document_ref: "doc-1", text: "Laboratory report H/Corg 0.2" }));
    serve({
      "/api/persona": json({ role: "verifier", configured: true }),
      "/api/cp/catalog": json(catalog),
      "/api/cp/batches/b-1/report": json(report),
      "/api/cp/batches/b-1/documents": json([{ document_ref: "doc-1", filename: "lab.pdf", media_type: "application/pdf", size: 650, sha256: "a".repeat(64), findings: [] }]),
      "/api/cp/documents/doc-1/text": text,
      "/api/cp/batches/b-1": json(batch("UNDER_REVIEW", evidence)),
    });
    mount(<BatchWorkspace batchId="b-1" />);
    await userEvent.click(await screen.findByRole("tab", { name: "Evidence" }));

    expect(await screen.findByText("Waiting for confirmation", { selector: "h2" })).toBeInTheDocument();
    expect(screen.getByText("Quoted: “pyrolysis at 650 C”")).toBeInTheDocument();
    expect(screen.getAllByText("650 °C").length).toBeGreaterThan(0);
    expect(screen.getByText("Biochar mass, dry basis")).toBeInTheDocument();
    expect(screen.getByText("100 t")).toBeInTheDocument();
    expect(screen.getByText("Yes")).toBeInTheDocument();
    expect(screen.getByText("Group: leg-1")).toBeInTheDocument();
    expect(screen.getAllByText("Measured").length).toBeGreaterThan(0);

    expect(await screen.findByText("lab.pdf")).toBeInTheDocument();
    expect(screen.getByText("No issues found")).toBeInTheDocument();
    expect(text).not.toHaveBeenCalled();
    await userEvent.click(screen.getByText("Show the text a model would read"));
    expect(await screen.findByText("Laboratory report H/Corg 0.2")).toBeInTheDocument();
  });

  it("moves between tabs with the arrow keys", async () => {
    serve({
      "/api/persona": json({ role: "verifier", configured: true }),
      "/api/cp/catalog": json(catalog),
      "/api/cp/batches/b-1/report": json(report),
      "/api/cp/batches/b-1/documents": json([]),
      "/api/cp/batches/b-1": json(batch("UNDER_REVIEW", [])),
    });
    mount(<BatchWorkspace batchId="b-1" />);
    const overview = await screen.findByRole("tab", { name: "Overview" });
    overview.focus();
    await userEvent.keyboard("{ArrowRight}");
    expect(screen.getByRole("tab", { name: "Evidence" })).toHaveAttribute("aria-selected", "true");
    expect(await screen.findByText("No evidence entered yet.")).toBeInTheDocument();
  });
});

describe("state timeline", () => {
  it("marks earlier steps done and shows a side state where it interrupts", () => {
    render(
      <I18nProvider>
        <StateTimeline state="NEEDS_INFO" />
      </I18nProvider>,
    );
    expect(screen.getByText("Currently: Needs info")).toBeInTheDocument();
    const steps = screen.getAllByRole("listitem");
    expect(steps).toHaveLength(6);
    expect(steps[1]).toHaveAttribute("aria-current", "step");
    expect(within(steps[0] as HTMLElement).getByText("✓")).toBeInTheDocument();
  });
});
