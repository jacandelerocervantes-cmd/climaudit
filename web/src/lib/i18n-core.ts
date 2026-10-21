/**
 * Pure helpers of the interface language (no React, importable from server and client code).
 * The key of every text is the English text itself: `t("Batches")`. A language without that key (or English) shows the
 * key, so a missing translation is readable English and never blank. Backend texts are shown as they are (English).
 */
export type Dict = Record<string, string>;
export type Params = Record<string, string | number>;
export type TFunction = (key: string, params?: Params) => string;

/**
 * English is the default and the language of the code, the documents and the demo (decision D-195). Other languages are
 * selectable in the interface: put a dictionary in `src/lib/locales`, list its code here and in `scripts/i18n.mjs`.
 * English needs no dictionary. Catalogs are machine-drafted and agent-audited (LANGUAGES.md).
 */
export const LANGUAGES = ["en", "es"] as const;
export type Language = (typeof LANGUAGES)[number];

export function isLanguage(value: unknown): value is Language {
  return typeof value === "string" && (LANGUAGES as readonly string[]).includes(value);
}

/** Marks a text for extraction without translating it where it is declared; translate it at render time with `t()`. */
export function msg(text: string): string {
  return text;
}

export function interpolate(template: string, params?: Params): string {
  if (!params) return template;
  return template.replace(/\{(\w+)\}/g, (whole, name: string) => (name in params ? String(params[name]) : whole));
}

export function translate(dict: Dict | undefined, key: string, params?: Params): string {
  return interpolate(dict?.[key] ?? key, params);
}

/** `t` for English: used where no provider is available (tests, error boundaries). */
export const translateEnglish: TFunction = (key, params) => interpolate(key, params);
