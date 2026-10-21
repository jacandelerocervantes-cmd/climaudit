"use client";

import { useI18n } from "@/lib/i18n";

export default function ErrorPage({ reset }: { error: Error; reset: () => void }) {
  const { t } = useI18n();
  return (
    <div role="alert" className="mx-auto max-w-md py-16 text-center">
      <h1 className="text-lg font-semibold">{t("Something went wrong")}</h1>
      <p className="mt-2 text-sm text-muted">{t("Try again. If it keeps happening, reload the page.")}</p>
      <button type="button" onClick={reset} className="mt-4 rounded-md border border-line px-3 py-1.5 text-sm">
        {t("Try again")}
      </button>
    </div>
  );
}
