import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { afterEach, describe, expect, it, vi } from "vitest";
import { LandingView } from "@/components/landing-view";
import { PersonaProvider } from "@/lib/client/persona";
import { I18nProvider } from "@/lib/i18n";

const push = vi.fn();
vi.mock("next/navigation", () => ({ useRouter: () => ({ push, replace: vi.fn() }) }));

afterEach(() => {
  vi.restoreAllMocks();
  push.mockClear();
});

describe("landing page", () => {
  it("offers every role, sets the chosen one and goes to the batches", async () => {
    const spy = vi.spyOn(globalThis, "fetch").mockImplementation(async (_input, init) => {
      const body = init?.body ? JSON.parse(String(init.body)) : { role: null };
      return new Response(JSON.stringify({ role: body.role ?? null, configured: true }), { status: 200 });
    });
    render(<I18nProvider><PersonaProvider><LandingView /></PersonaProvider></I18nProvider>);
    expect(await screen.findAllByRole("button", { name: /^Enter as / })).toHaveLength(5);
    await userEvent.click(screen.getByRole("button", { name: "Enter as Verifier" }));
    await waitFor(() => expect(push).toHaveBeenCalledWith("/batches"));
    const post = spy.mock.calls.find((c) => (c[1] as RequestInit | undefined)?.method === "POST");
    expect(JSON.parse(String((post?.[1] as RequestInit).body))).toEqual({ role: "verifier" });
  });
});
