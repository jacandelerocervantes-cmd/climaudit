import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import type { ReactNode } from "react";
import { afterEach, describe, expect, it, vi } from "vitest";
import { AboutView } from "@/components/about-view";
import { BatchWorkspace } from "@/components/batch-workspace";
import { MethodView } from "@/components/method-view";
import { CatalogProvider } from "@/lib/client/catalog";
import { ModeProvider } from "@/lib/client/mode";
import { PersonaProvider } from "@/lib/client/persona";
import { I18nProvider } from "@/lib/i18n";
import type { Batch, Catalog, Report } from "@/lib/types";

vi.mock("next/navigation", () => ({ useSearchParams: () => new URLSearchParams(), usePathname: () => "/batches/b-1" }));
vi.mock("next/link", () => ({ default: ({ href, children }: { href: string; children: ReactNode }) => <a href={href}>{children}</a> }));

const catalog: Catalog = {
  findings: [], states: [], terminal_states: [], editable_states: [], permissions: {}, errors: {}, evidence_kinds: {},
  transitions: [{ from: "UNDER_REVIEW", to: "VERIFIED", roles: ["verifier"], reason_required: false }],
};
const batch: Batch = {
  batch_id: "b-1", project_id: "prj-1", facility_id: "fac-1", year: 2026, biochar_type: "agricultural_residue", application_type: "soil", profile_id: "VM0044@1.2",
  parcel_key: "P", cell_set: [], product_batch_id: null, period_start: "2026-01-01", period_end: "2026-07-01", claimed_kg_co2e: 300000, state: "UNDER_REVIEW", created_at: "t", updated_at: "t", evidence: [],
};
const report = {
  report_id: "rep-1", evidence_hash: "f".repeat(64), batch_id: "b-1", status: "complete", recommendation: "human_review", kg_co2e: { low: 1, central: 2, high: 3 }, issuable_kg: 1,
  findings: [], profile_id: "VM0044@1.2", profile_label: "Verra VM0044 v1.2", facility_class: "high", blocks_calculation: false, blocks_verified: false, pending_items: 0, narrative_en: null, grounding: null, overrides: [],
} as unknown as Report;

const json = (body: unknown) => () => new Response(JSON.stringify(body), { status: 200, headers: { "content-type": "application/json" } });

function serve(snapshot: boolean) {
  const base: Record<string, () => Response> = {
    "/api/mode": json(snapshot ? { snapshot: true, generated_at: "2026-10-18T12:00:00Z", ledger_mode: "direct", network: "testnet" } : { snapshot: false }),
    "/api/persona": json({ role: "verifier", configured: true }),
    "/api/cp/catalog": json(catalog),
    "/api/cp/config": json({ ledger_mode: "direct", network: "testnet", hashscan_base: "https://hashscan.io/testnet", provenance_mode: "synthetic" }),
    "/api/cp/me": json({ actor_id: "verifier-1", role: "verifier" }),
    "/api/cp/batches/b-1/report": json(report),
    "/api/cp/batches/b-1": json(batch),
    "/api/cp/profiles": json([]),
  };
  vi.spyOn(globalThis, "fetch").mockImplementation(async (input) => {
    const url = String(input);
    const hit = Object.keys(base).sort((a, b) => b.length - a.length).find((prefix) => url.startsWith(prefix));
    return hit ? (base[hit] as () => Response)() : new Response("{}", { status: 404 });
  });
}

const wrap = (children: ReactNode) => (
  <I18nProvider>
    <ModeProvider>
      <PersonaProvider>
        <CatalogProvider>{children}</CatalogProvider>
      </PersonaProvider>
    </ModeProvider>
  </I18nProvider>
);

afterEach(() => vi.restoreAllMocks());

describe("recorded run", () => {
  it("switches the decision actions off and says why", async () => {
    serve(true);
    render(wrap(<BatchWorkspace batchId="b-1" />));
    await userEvent.click(await screen.findByRole("tab", { name: "Decision" }));
    expect(await screen.findByText("This is a recorded run, so the actions are switched off. Run the app locally to take them.")).toBeInTheDocument();
    expect(screen.queryByRole("button", { name: "Mark as verified" })).not.toBeInTheDocument();
  });

  it("keeps the actions in a live run", async () => {
    serve(false);
    render(wrap(<BatchWorkspace batchId="b-1" />));
    await userEvent.click(await screen.findByRole("tab", { name: "Decision" }));
    expect(await screen.findByRole("button", { name: "Mark as verified" })).toBeInTheDocument();
  });
});

describe("static pages", () => {
  it("shows the method explanation", async () => {
    serve(false);
    render(wrap(<MethodView />));
    expect(await screen.findByRole("heading", { name: "What is computed" })).toBeInTheDocument();
  });

  it("shows the about page with the synthetic-data statement", async () => {
    serve(false);
    render(wrap(<AboutView />));
    expect(await screen.findByText(/Everything shown is synthetic demonstration data/)).toBeInTheDocument();
  });
});
