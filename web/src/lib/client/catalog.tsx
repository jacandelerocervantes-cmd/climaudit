"use client";

import { createContext, useContext, type ReactNode } from "react";
import { useApi } from "@/lib/client/api";
import { usePersona } from "@/lib/client/persona";
import type { Catalog } from "@/lib/types";

const CatalogContext = createContext<Catalog | null>(null);

export type PublicConfig = { ledger_mode: string; network: string | null; hashscan_base: string | null; provenance_mode: string };
const ConfigContext = createContext<PublicConfig | null>(null);

/** Loads the vocabulary of the backend once per persona (findings, states, transitions, evidence kinds). */
export function CatalogProvider({ children }: { children: ReactNode }) {
  const { role, configured, version } = usePersona();
  const ready = role !== null && configured;
  const { data } = useApi<Catalog>(ready ? "catalog" : null, version);
  const config = useApi<PublicConfig>(ready ? "config" : null, version);
  return (
    <CatalogContext.Provider value={data}>
      <ConfigContext.Provider value={config.data}>{children}</ConfigContext.Provider>
    </CatalogContext.Provider>
  );
}

export function useCatalog(): Catalog | null {
  return useContext(CatalogContext);
}

export function useConfig(): PublicConfig | null {
  return useContext(ConfigContext);
}
