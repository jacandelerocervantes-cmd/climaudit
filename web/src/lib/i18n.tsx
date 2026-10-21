"use client";

import { createContext, useCallback, useContext, useEffect, useMemo, useSyncExternalStore, type ReactNode } from "react";
import es from "@/lib/locales/es.json";
import { isLanguage, translate, translateEnglish, type Dict, type Language, type Params, type TFunction } from "@/lib/i18n-core";

const DICTIONARIES: Record<Language, Dict | undefined> = { en: undefined, es: es as Dict };
const STORAGE_KEY = "cp.settings.v1";

type I18nValue = { language: Language; setLanguage: (language: Language) => void; t: TFunction };
const I18nContext = createContext<I18nValue>({ language: "en", setLanguage: () => undefined, t: translateEnglish });

const listeners = new Set<() => void>();

function readStored(): Language {
  try {
    const parsed: unknown = JSON.parse(window.localStorage.getItem(STORAGE_KEY) ?? "{}");
    const value = typeof parsed === "object" && parsed !== null ? (parsed as { language?: unknown }).language : undefined;
    return isLanguage(value) ? value : "en";
  } catch {
    return "en";
  }
}

function subscribe(listener: () => void): () => void {
  listeners.add(listener);
  window.addEventListener("storage", listener);
  return () => {
    listeners.delete(listener);
    window.removeEventListener("storage", listener);
  };
}

export function I18nProvider({ children }: { children: ReactNode }) {
  // The stored choice is an external store: the server and the first client render show English, then the choice applies.
  const language = useSyncExternalStore(subscribe, readStored, () => "en" as Language);

  useEffect(() => {
    document.documentElement.lang = language;
  }, [language]);

  const setLanguage = useCallback((next: Language) => {
    try {
      window.localStorage.setItem(STORAGE_KEY, JSON.stringify({ language: next }));
    } catch {
      // storage can be blocked (private mode): the choice then lasts for this visit only
    }
    listeners.forEach((listener) => listener());
  }, []);

  const t = useCallback((key: string, params?: Params) => translate(DICTIONARIES[language], key, params), [language]);
  const value = useMemo(() => ({ language, setLanguage, t }), [language, setLanguage, t]);
  return <I18nContext.Provider value={value}>{children}</I18nContext.Provider>;
}

export function useI18n(): I18nValue {
  return useContext(I18nContext);
}
