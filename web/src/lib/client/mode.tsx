"use client";

import { createContext, useContext, useEffect, useState, type ReactNode } from "react";

export type Mode = { snapshot: boolean; generated_at: string | null; ledger_mode: string | null; network: string | null };
const LIVE: Mode = { snapshot: false, generated_at: null, ledger_mode: null, network: null };
const ModeContext = createContext<Mode>(LIVE);

/** Whether the app replays a recorded run (read-only) or talks to a live API. */
export function ModeProvider({ children }: { children: ReactNode }) {
  const [mode, setMode] = useState<Mode>(LIVE);
  useEffect(() => {
    let alive = true;
    fetch("/api/mode", { cache: "no-store" })
      .then((r) => r.json() as Promise<Partial<Mode>>)
      .then((body) => {
        if (alive) setMode({ snapshot: body.snapshot === true, generated_at: body.generated_at ?? null, ledger_mode: body.ledger_mode ?? null, network: body.network ?? null });
      })
      .catch(() => undefined);
    return () => {
      alive = false;
    };
  }, []);
  return <ModeContext.Provider value={mode}>{children}</ModeContext.Provider>;
}

export function useMode(): Mode {
  return useContext(ModeContext);
}
