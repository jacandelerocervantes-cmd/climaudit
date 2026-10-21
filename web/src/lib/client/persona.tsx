"use client";

import { createContext, useCallback, useContext, useEffect, useMemo, useState, type ReactNode } from "react";
import { isRole, type Role } from "@/lib/config";

type PersonaValue = {
  role: Role | null;
  /** False when the server holds no demo key for the chosen role. */
  configured: boolean;
  loading: boolean;
  /** Changes whenever the persona changes, so data hooks can refresh. */
  version: number;
  setRole: (role: Role) => Promise<void>;
};

const PersonaContext = createContext<PersonaValue>({ role: null, configured: false, loading: true, version: 0, setRole: async () => undefined });

type PersonaResponse = { role?: unknown; configured?: unknown };

function read(body: PersonaResponse): { role: Role | null; configured: boolean } {
  return { role: isRole(body.role) ? body.role : null, configured: body.configured === true };
}

export function PersonaProvider({ children }: { children: ReactNode }) {
  const [state, setState] = useState<{ role: Role | null; configured: boolean; loading: boolean; version: number }>({ role: null, configured: false, loading: true, version: 0 });

  useEffect(() => {
    let alive = true;
    fetch("/api/persona", { cache: "no-store" })
      .then((r) => r.json() as Promise<PersonaResponse>)
      .then((body) => {
        if (alive) setState((s) => ({ ...s, ...read(body), loading: false }));
      })
      .catch(() => {
        if (alive) setState((s) => ({ ...s, loading: false }));
      });
    return () => {
      alive = false;
    };
  }, []);

  const setRole = useCallback(async (role: Role) => {
    const response = await fetch("/api/persona", { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ role }) });
    const body = (await response.json()) as PersonaResponse;
    setState((s) => ({ ...s, ...read(body), loading: false, version: s.version + 1 }));
  }, []);

  const value = useMemo(() => ({ ...state, setRole }), [state, setRole]);
  return <PersonaContext.Provider value={value}>{children}</PersonaContext.Provider>;
}

export function usePersona(): PersonaValue {
  return useContext(PersonaContext);
}
