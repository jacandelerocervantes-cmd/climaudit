import { readFileSync } from "node:fs";
import { join } from "node:path";
import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import axe from "axe-core";
import type { ReactNode } from "react";
import { afterEach, describe, expect, it, vi } from "vitest";
import { AboutView } from "@/components/about-view";
import { AppShell } from "@/components/app-shell";
import { AuditView } from "@/components/audit-view";
import { BatchWorkspace } from "@/components/batch-workspace";
import { BatchesView } from "@/components/batches-view";
import { LandingView } from "@/components/landing-view";
import { MethodView } from "@/components/method-view";
import { CatalogProvider } from "@/lib/client/catalog";
import { ModeProvider } from "@/lib/client/mode";
import { PersonaProvider } from "@/lib/client/persona";
import { I18nProvider } from "@/lib/i18n";

vi.mock("next/navigation", () => ({
  useSearchParams: () => new URLSearchParams(),
  usePathname: () => "/batches",
  useRouter: () => ({ push: vi.fn(), replace: vi.fn() }),
}));
vi.mock("next/link", () => ({ default: ({ href, children, ...rest }: { href: string; children: ReactNode }) => <a href={href} {...rest}>{children}</a> }));

// The screens are audited with the data of the real recorded run, so every tab has real content.
type Recorded = { status: number; body: unknown };
const snapshot = JSON.parse(readFileSync(join(process.cwd(), "snapshot", "snapshot.json"), "utf8")) as { meta: { batches: Record<string, string> }; roles: Record<string, Record<string, Recorded>> };
const VERIFIED = snapshot.meta.batches.verified as string;

function serve(role: string) {
  vi.spyOn(globalThis, "fetch").mockImplementation(async (input) => {
    const url = String(input);
    const json = (body: unknown, status = 200) => new Response(JSON.stringify(body), { status, headers: { "content-type": "application/json" } });
    if (url.startsWith("/api/persona")) return json({ role, configured: true });
    if (url.startsWith("/api/mode")) return json({ snapshot: false });
    const path = url.replace("/api/cp/", "").split("?")[0] as string;
    const hit = snapshot.roles[role]?.[path];
    return hit ? json(hit.body, hit.status) : json({}, 404);
  });
}

const wrap = (children: ReactNode) => (
  <I18nProvider>
    <ModeProvider>
      <PersonaProvider>
        <CatalogProvider>
          <AppShell>{children}</AppShell>
        </CatalogProvider>
      </PersonaProvider>
    </ModeProvider>
  </I18nProvider>
);

// jsdom has no layout, so colour contrast is checked by scripts/check-contrast.mjs instead.
async function violations(container: Element): Promise<string[]> {
  const result = await axe.run(container, { rules: { "color-contrast": { enabled: false } } });
  return result.violations.map((v) => `${v.id}: ${v.help} (${v.nodes.map((n) => n.target.join(" ")).join(", ")})`);
}

afterEach(() => vi.restoreAllMocks());

// Each test walks many screens and runs axe on every one, so it needs more than the default 5 seconds on a slow machine.
vi.setConfig({ testTimeout: 60_000 });

describe("accessibility (axe)", () => {
  it("has no violations on the start, batches, method, about and audit pages", async () => {
    serve("verifier");
    for (const page of [<LandingView key="l" />, <BatchesView key="b" />, <MethodView key="m" />, <AboutView key="a" />, <AuditView key="u" />]) {
      const { container, unmount } = render(wrap(page));
      await screen.findAllByRole("heading");
      await new Promise((r) => setTimeout(r, 50));
      expect(await violations(container)).toEqual([]);
      unmount();
    }
  });

  it("has no violations on any tab of a batch, for the verifier and the registry", async () => {
    for (const role of ["verifier", "registry"]) {
      serve(role);
      const { container, unmount } = render(wrap(<BatchWorkspace batchId={VERIFIED} />));
      const tabs = await screen.findAllByRole("tab");
      expect(tabs).toHaveLength(7);
      for (const tab of tabs) {
        await userEvent.click(tab);
        await new Promise((r) => setTimeout(r, 150));
        expect(screen.queryByText("Loading")).not.toBeInTheDocument();
        expect(await violations(container), `${role} / ${tab.textContent}`).toEqual([]);
      }
      unmount();
      vi.restoreAllMocks();
    }
  });

  it("the harness does catch a real violation", async () => {
    const { container } = render(<button type="button" />);
    expect((await violations(container)).join()).toContain("button-name");
  });
});
