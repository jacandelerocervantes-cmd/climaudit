import { render, screen, waitFor, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import type { ReactNode } from "react";
import { afterEach, describe, expect, it, vi } from "vitest";
import { AppShell } from "@/components/app-shell";
import { BatchesView } from "@/components/batches-view";
import { RangeBar } from "@/components/range-bar";
import { StateBadge } from "@/components/ui";
import { I18nProvider } from "@/lib/i18n";
import { ApiFailure, api, parseFailure } from "@/lib/client/api";
import { PersonaProvider } from "@/lib/client/persona";
import { errorMessage } from "@/lib/messages";
import { translate, translateEnglish } from "@/lib/i18n-core";

vi.mock("next/navigation", () => ({ usePathname: () => "/", useRouter: () => ({ replace: vi.fn(), push: vi.fn() }) }));

function wrap(node: ReactNode) {
  return render(
    <I18nProvider>
      <PersonaProvider>{node}</PersonaProvider>
    </I18nProvider>,
  );
}

function route(table: Record<string, () => Response>) {
  return vi.spyOn(globalThis, "fetch").mockImplementation(async (input) => {
    const url = String(input);
    for (const [prefix, make] of Object.entries(table)) if (url.startsWith(prefix)) return make();
    return new Response("{}", { status: 404 });
  });
}
const json = (body: unknown, status = 200) => () => new Response(JSON.stringify(body), { status, headers: { "content-type": "application/json" } });

afterEach(() => vi.restoreAllMocks());

describe("api client", () => {
  it("sends an Idempotency-Key on writes only and reuses a given one", async () => {
    const spy = route({ "/api/cp/": json({ ok: true }) });
    await api("batches/b-1/issue", { method: "POST", body: {}, idempotencyKey: "fixed-key" });
    await api("batches");
    const [, post] = spy.mock.calls[0] as [string, RequestInit];
    const [, get] = spy.mock.calls[1] as [string, RequestInit];
    expect((post.headers as Record<string, string>)["Idempotency-Key"]).toBe("fixed-key");
    expect((get.headers as Record<string, string>)["Idempotency-Key"]).toBeUndefined();
  });

  it("turns the backend error envelope into a typed failure with a plain sentence", async () => {
    route({ "/api/cp/": json({ error: { code: "ROLE_NOT_AUTHORIZED", params: { required_role: ["registry"] }, correlation_id: "c-1" } }, 403) });
    const failure = await api("batches/b-1/issue", { method: "POST" }).catch((e: unknown) => e);
    expect(failure).toBeInstanceOf(ApiFailure);
    expect((failure as ApiFailure).code).toBe("ROLE_NOT_AUTHORIZED");
    expect(errorMessage(failure as ApiFailure, translateEnglish)).toContain("Needed: registry.");
    expect(parseFailure(502, "<html>").code).toBe("INTERNAL_ERROR");
  });
});

describe("components", () => {
  it("shows a state with a glyph and a word, not colour alone", () => {
    wrap(<StateBadge state="VERIFIED" />);
    expect(screen.getByText("Verified")).toBeInTheDocument();
    expect(screen.getByText("✓")).toHaveAttribute("aria-hidden", "true");
  });

  it("describes the range bar in words", () => {
    wrap(<RangeBar range={{ low: 250728, central: 261067, high: 271614 }} claimed={300000} />);
    expect(screen.getByRole("img")).toHaveAccessibleName("Range 250,728 to 271,614 kg CO2e, central 261,067, claim 300,000");
  });

  it("asks for a role first, then lists the batches of that role", async () => {
    let role: string | null = null;
    route({
      "/api/persona": () => new Response(JSON.stringify({ role, configured: role !== null }), { status: 200 }),
      "/api/cp/batches": json([{ batch_id: "b-1", project_id: "p-1", year: 2026, biochar_type: "x", application_type: "soil", state: "VERIFIED", claimed_kg_co2e: 300000, updated_at: "2026-10-17T10:00:00Z", report: { status: "complete", recommendation: "human_review", kg_co2e: { low: 250728, central: 261067, high: 271614 }, issuable_kg: 250728 } }]),
    });
    wrap(<BatchesView />);
    expect(await screen.findByText("Choose a role to start")).toBeInTheDocument();
    role = "verifier";
    wrap(<BatchesView />);
    expect((await screen.findAllByText("b-1")).length).toBe(2); // the mobile list and the table, one of them hidden by CSS
    expect(screen.getAllByText("250,728 to 271,614").length).toBe(2);
    expect(screen.getAllByText("Verified").length).toBe(2);
  });

  it("explains a failure and offers a retry", async () => {
    route({
      "/api/persona": json({ role: "verifier", configured: true }),
      "/api/cp/batches": json({ error: { code: "LEDGER_UNAVAILABLE", params: {}, correlation_id: "-" } }, 503),
    });
    wrap(<BatchesView />);
    expect(await screen.findByRole("alert")).toHaveTextContent("The ledger isn't reachable right now");
    expect(screen.getByRole("button", { name: "Try again" })).toBeInTheDocument();
  });

  it("is English by default, offers Spanish in a selector, and applies the choice", async () => {
    route({ "/api/persona": json({ role: null, configured: false }) });
    wrap(<AppShell><p>content</p></AppShell>);
    expect(document.documentElement.lang).toBe("en");
    const selector = screen.getByLabelText("Language");
    expect(within(selector).getAllByRole("option").map((o) => o.textContent)).toEqual(["English", "Español"]);
    await userEvent.selectOptions(selector, "es");
    await waitFor(() => expect(screen.getByLabelText("Idioma")).toBeInTheDocument());
    expect(document.documentElement.lang).toBe("es");
  });

  it("translates through a dictionary when a language is added, falling back to the English text", () => {
    expect(translate({ "Batches": "Lots", "{n} found": "{n} hallados" }, "{n} found", { n: 2 })).toBe("2 hallados");
    expect(translate({ "Batches": "Lots" }, "State")).toBe("State");
    expect(translate(undefined, "State")).toBe("State");
  });
});
