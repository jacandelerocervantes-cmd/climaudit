import type { Metadata } from "next";
import type { ReactNode } from "react";
import { AppShell } from "@/components/app-shell";
import { I18nProvider } from "@/lib/i18n";
import { CatalogProvider } from "@/lib/client/catalog";
import { ModeProvider } from "@/lib/client/mode";
import { PersonaProvider } from "@/lib/client/persona";
import "./globals.css";

export const metadata: Metadata = {
  title: "ClimAudit",
  description: "Evidence checking for biochar carbon credits, with a public audit trail. Synthetic data, testnet only.",
};

export default function RootLayout({ children }: { children: ReactNode }) {
  return (
    <html lang="en">
      <body>
        <I18nProvider>
          <ModeProvider>
            <PersonaProvider>
              <CatalogProvider>
                <AppShell>{children}</AppShell>
              </CatalogProvider>
            </PersonaProvider>
          </ModeProvider>
        </I18nProvider>
      </body>
    </html>
  );
}
