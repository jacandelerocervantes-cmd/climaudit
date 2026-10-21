import { render, screen, waitFor, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import type { ReactNode } from "react";
import { afterEach, describe, expect, it, vi } from "vitest";
import { BatchWorkspace } from "@/components/batch-workspace";
import { CatalogProvider } from "@/lib/client/catalog";
import { PersonaProvider } from "@/lib/client/persona";
import { hashscanToken, hashscanTransaction } from "@/lib/hashscan";
import { I18nProvider } from "@/lib/i18n";
import type { Batch, Catalog, EvidenceItem, Finding, Report } from "@/lib/types";

vi.mock("next/navigation", () => ({ useSearchParams: () => new URLSearchParams(), usePathname: () => "/batches/b-1" }));
vi.mock("next/link", () => ({ default: ({ href, children }: { href: string; children: ReactNode }) => <a href={href}>{children}</a> }));

const catalog: Catalog = {
  findings: [], states: [], terminal_states: [], editable_states: [], permissions: {}, errors: {}, evidence_kinds: {},
  transitions: [
    { from: "DRAFT", to: "SUBMITTED", roles: ["owner", "admin"], reason_required: false },
    { from: "UNDER_REVIEW", to: "VERIFIED", roles: ["verifier"], reason_required: false },
    { from: "UNDER_REVIEW", to: "NEEDS_INFO", roles: ["verifier", "admin"], reason_required: true },
    { from: "UNDER_REVIEW", to: "REJECTED", roles: ["verifier", "admin"], reason_required: true },
    { from: "VERIFIED", to: "ISSUED", roles: ["registry"], reason_required: false },
    { from: "ISSUED", to: "RETIRED", roles: ["holder", "owner"], reason_required: false },
  ],
};

const finding = (over: Partial<Finding> = {}): Finding => ({ code: "PROVENANCE_SYNTHETIC", severity: "info", params: {}, source: "rule", blocks_calculation: false, blocks_verified: false, overridable: false, ...over });

const report = (findings: Finding[] = [finding()], status = "complete"): Report => ({
  report_id: "rep-1", evidence_hash: "f".repeat(64), batch_id: "b-1", status, recommendation: "human_review", kg_co2e: { low: 250728, central: 261067, high: 271614 },
  issuable_kg: 250728, findings, profile_id: "VM0044@1.2", profile_label: "Verra VM0044 v1.2", facility_class: "high", blocks_calculation: false, blocks_verified: false,
  pending_items: 0, narrative_en: null, grounding: null, overrides: [],
});

const pendingItem: EvidenceItem = {
  item_id: "i-9", kind: "pyrolysis_temp_c", value: "650", unit: "celsius", group: null, measured_at: null, source: "model", provenance: "synthetic",
  rel_uncertainty: null, document_ref: "doc-1", confirmation: "pending_confirmation", span: { quote: "pyrolysis at 650 C", page: 1 },
};

const batch = (state: string, evidence: EvidenceItem[] = []): Batch => ({
  batch_id: "b-1", project_id: "prj-1", facility_id: "fac-1", year: 2026, biochar_type: "agricultural_residue", application_type: "soil", profile_id: "VM0044@1.2",
  parcel_key: "P", cell_set: [], product_batch_id: null, period_start: "2026-01-01", period_end: "2026-07-01", claimed_kg_co2e: 300000, state, created_at: "t", updated_at: "t", evidence,
});

const json = (body: unknown, status = 200) => () => new Response(JSON.stringify(body), { status, headers: { "content-type": "application/json" } });

function serve(role: string, table: Record<string, () => Response>) {
  const base: Record<string, () => Response> = {
    "/api/persona": json({ role, configured: true }),
    "/api/cp/catalog": json(catalog),
    "/api/cp/config": json({ ledger_mode: "direct", network: "testnet", hashscan_base: "https://hashscan.io/testnet", provenance_mode: "synthetic" }),
    "/api/cp/me": json({ actor_id: role === "holder" ? "buyer-1" : `${role}-1`, role }),
    ...table,
  };
  return vi.spyOn(globalThis, "fetch").mockImplementation(async (input) => {
    const url = String(input);
    const hit = Object.keys(base).sort((a, b) => b.length - a.length).find((prefix) => url.startsWith(prefix));
    return hit ? (base[hit] as () => Response)() : new Response("{}", { status: 404 });
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

const calls = (spy: { mock: { calls: unknown[][] } }, suffix: string) => spy.mock.calls.filter((call) => String(call[0]).endsWith(suffix)) as unknown as [string, RequestInit][];

afterEach(() => vi.restoreAllMocks());

describe("decision tab", () => {
  it("offers a verifier the actions of the state, asks for confirmation and posts the transition", async () => {
    const moved = vi.fn(json({ ...batch("VERIFIED") }));
    const spy = serve("verifier", { "/api/cp/batches/b-1/transitions": moved, "/api/cp/batches/b-1/report": json(report()), "/api/cp/batches/b-1": json(batch("UNDER_REVIEW")) });
    mount();
    await userEvent.click(await screen.findByRole("tab", { name: "Decision" }));
    expect(await screen.findByText("A verifier must decide.")).toBeInTheDocument();
    expect(screen.getByRole("heading", { name: "Run the verification" })).toBeInTheDocument();
    expect(screen.getByRole("heading", { name: "Return to the owner" })).toBeInTheDocument();
    expect(screen.queryByRole("heading", { name: "Issue credits" })).not.toBeInTheDocument();
    await userEvent.click(screen.getByRole("button", { name: "Mark as verified" }));
    expect(screen.getByText("Confirm: mark as verified?")).toBeInTheDocument();
    expect(moved).not.toHaveBeenCalled();
    await userEvent.click(screen.getByRole("button", { name: "Confirm" }));
    await waitFor(() => expect(moved).toHaveBeenCalledTimes(1));
    const [, init] = calls(spy, "/transitions")[0] as [string, RequestInit];
    expect(JSON.parse(String(init.body))).toEqual({ to: "VERIFIED" });
    expect((init.headers as Record<string, string>)["Idempotency-Key"]).toBeTruthy();
    expect(await screen.findByText("Done. The batch is now Verified.")).toBeInTheDocument();
  });

  it("requires a written reason to return or reject, and sends it", async () => {
    const moved = vi.fn(json(batch("NEEDS_INFO")));
    const spy = serve("verifier", { "/api/cp/batches/b-1/transitions": moved, "/api/cp/batches/b-1/report": json(report()), "/api/cp/batches/b-1": json(batch("UNDER_REVIEW")) });
    mount();
    await userEvent.click(await screen.findByRole("tab", { name: "Decision" }));
    await userEvent.click(await screen.findByRole("button", { name: "Return to the owner" }));
    await userEvent.click(screen.getByRole("button", { name: "Confirm" }));
    expect(await screen.findByRole("alert")).toHaveTextContent("Enter a reason first.");
    expect(moved).not.toHaveBeenCalled();
    await userEvent.type(screen.getByLabelText("Reason (required, recorded in the audit trail)"), "Lab report is missing page 2");
    await userEvent.click(screen.getByRole("button", { name: "Confirm" }));
    await waitFor(() => expect(moved).toHaveBeenCalledTimes(1));
    expect(JSON.parse(String((calls(spy, "/transitions")[0] as [string, RequestInit])[1].body))).toEqual({ to: "NEEDS_INFO", reason: "Lab report is missing page 2" });
  });

  it("explains why verification is not possible yet instead of offering the button", async () => {
    serve("verifier", {
      "/api/cp/batches/b-1/report": json(report([finding({ code: "MASS_BALANCE_MISMATCH", severity: "high", blocks_calculation: true, blocks_verified: true })], "incomplete")),
      "/api/cp/batches/b-1": json(batch("UNDER_REVIEW", [pendingItem])),
    });
    mount();
    await userEvent.click(await screen.findByRole("tab", { name: "Decision" }));
    const card = (await screen.findByRole("heading", { name: "Mark as verified" })).closest("li") as HTMLElement;
    expect(within(card).getByText("Not available yet")).toBeInTheDocument();
    expect(within(card).getByText("The calculation is incomplete: resolve the blocking findings and run the verification again.")).toBeInTheDocument();
    expect(within(card).getByText("1 finding(s) block the next step.")).toBeInTheDocument();
    expect(within(card).getByText("1 evidence item(s) wait for a person to confirm them.")).toBeInTheDocument();
    expect(within(card).queryByRole("button")).not.toBeInTheDocument();
  });

  it("keeps the same idempotency key when the same action is retried after an outage", async () => {
    let attempt = 0;
    const flaky = vi.fn(() => (attempt++ === 0 ? new Response(JSON.stringify({ error: { code: "LEDGER_UNAVAILABLE", params: {}, correlation_id: "c" } }), { status: 503 }) : new Response(JSON.stringify({ credit_id: "cr-1", units: 250728, batch: { state: "ISSUED" } }), { status: 200 })));
    const spy = serve("registry", { "/api/cp/batches/b-1/issue": flaky, "/api/cp/batches/b-1/report": json(report()), "/api/cp/batches/b-1": json(batch("VERIFIED")) });
    mount();
    await userEvent.click(await screen.findByRole("tab", { name: "Decision" }));
    await userEvent.click(await screen.findByRole("button", { name: "Issue credits" }));
    expect(screen.getByText("Confirm: issue 250,728 credit units for this batch?")).toBeInTheDocument();
    await userEvent.click(screen.getByRole("button", { name: "Confirm" }));
    expect(await screen.findByRole("alert")).toHaveTextContent("The ledger isn't reachable right now");
    await userEvent.click(screen.getByRole("button", { name: "Confirm" }));
    expect(await screen.findByText("Issued 250,728 credit units (1 unit = 1 kg CO2e).")).toBeInTheDocument();
    const keys = calls(spy, "/issue").map(([, init]) => (init.headers as Record<string, string>)["Idempotency-Key"]);
    expect(keys).toHaveLength(2);
    expect(keys[0]).toBe(keys[1]);
    expect(screen.getByRole("button", { name: "Open the credit" })).toBeInTheDocument();
  });

  it("lets an owner submit a draft and tells a holder there is nothing to decide", async () => {
    serve("owner", { "/api/cp/batches/b-1/report": json({ error: { code: "NOT_FOUND", params: { resource: "report" }, correlation_id: "c" } }, 404), "/api/cp/batches/b-1": json(batch("DRAFT")) });
    const first = mount();
    await userEvent.click(await screen.findByRole("tab", { name: "Decision" }));
    expect(await screen.findByRole("button", { name: "Submit for review" })).toBeInTheDocument();
    first.unmount();
    vi.restoreAllMocks();
    serve("holder", { "/api/cp/batches/b-1/report": json(report()), "/api/cp/batches/b-1": json(batch("UNDER_REVIEW")) });
    mount();
    await userEvent.click(await screen.findByRole("tab", { name: "Decision" }));
    expect(await screen.findByText("As Credit holder you have nothing to do on this batch now.")).toBeInTheDocument();
  });
});

describe("evidence confirmation", () => {
  it("lets a verifier confirm or reject a proposed value", async () => {
    const confirmed = vi.fn(json({ ...pendingItem, confirmation: "confirmed" }));
    const spy = serve("verifier", {
      "/api/cp/batches/b-1/evidence/i-9/confirm": confirmed,
      "/api/cp/batches/b-1/report": json(report()),
      "/api/cp/batches/b-1/documents": json([]),
      "/api/cp/batches/b-1": json(batch("UNDER_REVIEW", [pendingItem])),
    });
    mount();
    await userEvent.click(await screen.findByRole("tab", { name: "Evidence" }));
    await userEvent.click(await screen.findByRole("button", { name: "Confirm the value" }));
    await waitFor(() => expect(confirmed).toHaveBeenCalledTimes(1));
    expect(JSON.parse(String((calls(spy, "/confirm")[0] as [string, RequestInit])[1].body))).toEqual({ decision: "confirmed" });
    expect(screen.getByRole("button", { name: "Reject the value" })).toBeInTheDocument();
  });
});

describe("credit tab", () => {
  const credit = {
    credit_id: "cr-1", batch_id: "b-1", token_id: "0.0.2222", tx_id: "0.0.9@1700000000.123456789", units: 250728, provenance: "synthetic", alternative_permanence_model: false,
    balances: { "buyer-1": 600, "owner-1": 250128 }, retirements: [{ retirement_id: "ret-1", holder: "buyer-1", units: 400, beneficiary_ref: "ben-1", reason_code: "voluntary_offset", tx_id: "0.0.9@1700000001.000000001", retired_at: "t" }],
  };

  it("shows balances, retirements and explorer links, and transfers to a recipient", async () => {
    const transferred = vi.fn(json({ credit_id: "cr-1", from: "buyer-1", to: "owner-1", units: 100, tx_id: "x" }));
    const spy = serve("holder", { "/api/cp/credits/cr-1/transfer": transferred, "/api/cp/credits": json([credit]), "/api/cp/batches/b-1/report": json(report()), "/api/cp/batches/b-1": json(batch("PARTIALLY_RETIRED")) });
    mount();
    await userEvent.click(await screen.findByRole("tab", { name: "Credit" }));
    expect(await screen.findByText("250,728 units (250.728 t CO2e)")).toBeInTheDocument();
    expect(screen.getByRole("link", { name: "0.0.2222" })).toHaveAttribute("href", "https://hashscan.io/testnet/token/0.0.2222");
    expect(screen.getByRole("link", { name: "0.0.9@1700000000.123456789" })).toHaveAttribute("href", "https://hashscan.io/testnet/transaction/0.0.9-1700000000-123456789");
    expect(screen.getByText("ben-1")).toBeInTheDocument();
    expect(screen.getByText("(you)")).toBeInTheDocument();
    expect(screen.getByText("You hold")).toBeInTheDocument();
    expect(screen.getByText("Your balance")).toBeInTheDocument();

    await userEvent.type(screen.getByLabelText("Recipient"), "owner-1");
    await userEvent.type(screen.getByLabelText("Units (you hold 600)", { selector: "#transfer-units" }), "9999");
    await userEvent.click(screen.getByRole("button", { name: "Transfer" }));
    expect(await screen.findByRole("alert")).toHaveTextContent("Enter a whole number of units between 1 and 600.");
    expect(transferred).not.toHaveBeenCalled();
    await userEvent.clear(screen.getByLabelText("Units (you hold 600)", { selector: "#transfer-units" }));
    await userEvent.type(screen.getByLabelText("Units (you hold 600)", { selector: "#transfer-units" }), "100");
    await userEvent.click(screen.getByRole("button", { name: "Transfer" }));
    await waitFor(() => expect(transferred).toHaveBeenCalledTimes(1));
    expect(JSON.parse(String((calls(spy, "/transfer")[0] as [string, RequestInit])[1].body))).toEqual({ to_holder: "owner-1", units: 100 });
    expect(await screen.findByText("Transferred 100 units to owner-1.")).toBeInTheDocument();
  });

  it("asks for confirmation before retiring and says what an unknown recipient means", async () => {
    const retired = vi.fn(json({ retirement_id: "ret-2", credit_id: "cr-1", units: 50, remaining_total_units: 1, tx_id: "x" }));
    const spy = serve("holder", { "/api/cp/credits/cr-1/retire": retired, "/api/cp/credits": json([credit]), "/api/cp/batches/b-1/report": json(report()), "/api/cp/batches/b-1": json(batch("PARTIALLY_RETIRED")) });
    mount();
    await userEvent.click(await screen.findByRole("tab", { name: "Credit" }));
    await userEvent.type(await screen.findByLabelText("Units (you hold 600)", { selector: "#retire-units" }), "50");
    await userEvent.type(screen.getByLabelText("Beneficiary", { selector: "#retire-who" }), "Acme Foods");
    await userEvent.click(screen.getByRole("button", { name: "Review retirement" }));
    expect(screen.getByText("Confirm: retire 50 units for Acme Foods? This can't be undone.")).toBeInTheDocument();
    expect(retired).not.toHaveBeenCalled();
    await userEvent.click(screen.getByRole("button", { name: "Confirm" }));
    await waitFor(() => expect(retired).toHaveBeenCalledTimes(1));
    expect(JSON.parse(String((calls(spy, "/retire")[0] as [string, RequestInit])[1].body))).toEqual({ units: 50, beneficiary_ref: "Acme Foods", reason_code: "voluntary_offset" });
    expect(await screen.findByText("Retired 50 units for Acme Foods.")).toBeInTheDocument();
  });

  it("says there are no credits before issuance and builds explorer links only for real transaction ids", async () => {
    serve("owner", { "/api/cp/credits": json([]), "/api/cp/batches/b-1/report": json(report()), "/api/cp/batches/b-1": json(batch("VERIFIED")) });
    mount();
    await userEvent.click(await screen.findByRole("tab", { name: "Credit" }));
    expect(await screen.findByText("No credits yet. They exist after the registry issues them.")).toBeInTheDocument();
    expect(hashscanTransaction("https://hashscan.io/testnet", "fake-tx-1")).toBeNull();
    expect(hashscanTransaction("https://hashscan.io/testnet", "custodial-abc")).toBeNull();
    expect(hashscanTransaction(null, "0.0.9@1.2")).toBeNull();
    expect(hashscanToken("https://hashscan.io/testnet", "fake-token-0")).toBeNull();
  });
});
