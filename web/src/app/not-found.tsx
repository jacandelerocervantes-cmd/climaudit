"use client";

import Link from "next/link";
import { useI18n } from "@/lib/i18n";

export default function NotFound() {
  const { t } = useI18n();
  return (
    <div className="mx-auto max-w-md py-16 text-center">
      <h1 className="text-lg font-semibold">{t("Page not found")}</h1>
      <p className="mt-2 text-sm text-muted">{t("That page doesn't exist.")}</p>
      <Link href="/batches" className="mt-4 inline-block rounded-md border border-line px-3 py-1.5 text-sm">
        {t("Back to batches")}
      </Link>
    </div>
  );
}
