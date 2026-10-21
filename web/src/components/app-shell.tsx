"use client";

import Link from "next/link";
import { usePathname, useRouter } from "next/navigation";
import { useEffect } from "react";
import type { ReactNode } from "react";
import { LANGUAGES, isLanguage, msg } from "@/lib/i18n-core";
import { useI18n } from "@/lib/i18n";
import { useConfig } from "@/lib/client/catalog";
import { useMode } from "@/lib/client/mode";
import { usePersona } from "@/lib/client/persona";
import { ROLE_LABELS } from "@/lib/messages";
import { Badge } from "@/components/ui";

const NAV = [
  { href: "/batches", label: msg("Batches") },
  { href: "/audit", label: msg("Audit") },
  { href: "/method", label: msg("Method") },
  { href: "/about", label: msg("About") },
];

function PersonaSwitcher() {
  const { t } = useI18n();
  const { role, configured, loading } = usePersona();
  return (
    <div className="rounded-lg border border-line bg-surface p-2 text-xs">
      <p className="text-muted">{t("Acting as (demo)")}</p>
      <p className="mt-1 text-sm font-medium text-ink">{role ? t(ROLE_LABELS[role] ?? role) : loading ? "" : t("No role chosen")}</p>
      <Link href="/" className="mt-1 inline-block text-accent underline">
        {role ? t("Change role") : t("Choose a role")}
      </Link>
      {role && !configured ? <p className="mt-1 text-warn-ink">{t("This role has no demo key on the server.")}</p> : null}
    </div>
  );
}

// A language is named in its own language, so a reader can always find theirs.
const LANGUAGE_NAMES: Record<string, string> = { en: "English", es: "Español" };
const HAS_LANGUAGES = LANGUAGES.length > 1;

function LanguageSwitcher() {
  const { language, setLanguage, t } = useI18n();
  return (
    <div className="text-xs">
      <label htmlFor="language" className="block text-muted">
        {t("Language")}
      </label>
      <select
        id="language"
        value={language}
        onChange={(e) => {
          if (isLanguage(e.target.value)) setLanguage(e.target.value);
        }}
        className="mt-1 w-full rounded-md border border-line bg-canvas px-2 py-1 text-sm text-ink"
      >
        {LANGUAGES.map((code) => (
          <option key={code} value={code}>
            {LANGUAGE_NAMES[code]}
          </option>
        ))}
      </select>
    </div>
  );
}

function LedgerBadge() {
  const { t } = useI18n();
  const data = useConfig();
  if (!data) return null;
  return data.network ? <Badge tone="info">{t("Test network ({network})", { network: data.network })}</Badge> : <Badge tone="neutral">{t("In-memory ledger")}</Badge>;
}

function SnapshotBanner() {
  const { t } = useI18n();
  const mode = useMode();
  if (!mode.snapshot) return null;
  const date = mode.generated_at ? mode.generated_at.slice(0, 10) : "-";
  return (
    <div role="note" className="border-b border-line bg-info-bg px-4 py-2 text-sm text-info-ink">
      {mode.network
        ? t("Recorded run, read-only. A real run on the {network} test network, recorded on {date}. Run the app locally to try the actions.", { network: mode.network, date })
        : t("Recorded run, read-only, recorded on {date}. Run the app locally to try the actions.", { date })}
    </div>
  );
}

export function AppShell({ children }: { children: ReactNode }) {
  const { t } = useI18n();
  const pathname = usePathname();
  const router = useRouter();
  const { role, loading } = usePersona();
  // Without a role every screen is empty, so the visitor goes back to the role choice (About reads nothing from the API).
  useEffect(() => {
    if (!loading && role === null && pathname !== "/" && pathname !== "/about") router.replace("/");
  }, [loading, role, pathname, router]);
  return (
    <div className="flex min-h-screen flex-col md:flex-row">
      <aside className="grid shrink-0 grid-cols-[3fr_2fr] gap-3 border-b border-line bg-sidebar p-4 md:flex md:w-60 md:flex-col md:gap-4 md:border-b-0 md:border-r">
        <Link href="/" className="col-span-2 text-lg font-semibold text-ink md:col-auto">
          ClimAudit
        </Link>
        <div className={`order-2 md:order-none ${HAS_LANGUAGES ? "" : "col-span-2"}`}>
          <PersonaSwitcher />
        </div>
        <nav aria-label={t("Main")} className="order-4 col-span-2 flex flex-row gap-1 md:order-none md:col-auto md:flex-col">
          {NAV.map((item) => {
            const active = pathname.startsWith(item.href) || (item.href === "/batches" && pathname.startsWith("/batches"));
            return (
              <Link
                key={item.href}
                href={item.href}
                aria-current={active ? "page" : undefined}
                className={`rounded-md px-3 py-2 text-sm ${active ? "bg-surface font-medium text-ink" : "text-muted hover:bg-surface"}`}
              >
                {t(item.label)}
              </Link>
            );
          })}
        </nav>
        {HAS_LANGUAGES ? (
          <div className="order-3 md:order-none md:mt-auto">
            <LanguageSwitcher />
          </div>
        ) : null}
      </aside>
      <div className="flex min-w-0 flex-1 flex-col">
        <SnapshotBanner />
        <main className="flex-1 p-4 md:p-6">{children}</main>
        <footer className="flex flex-wrap items-center justify-center gap-2 border-t border-line px-4 py-3 text-xs text-muted">
          <LedgerBadge />
        </footer>
      </div>
    </div>
  );
}
