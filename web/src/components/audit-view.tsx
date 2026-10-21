"use client";

import { useI18n } from "@/lib/i18n";
import { VerifyPanel } from "@/components/verify-panel";
import { Card } from "@/components/ui";

export function AuditView() {
  const { t } = useI18n();
  return (
    <div className="flex flex-col gap-4">
      <h1 className="text-lg font-semibold">{t("Audit")}</h1>
      <Card>
        <p className="text-sm">{t("The audit trail is one chain of events across every batch. Only hashes and ids go to the public ledger; evidence documents and personal data stay in the system.")}</p>
        <p className="mt-2 text-sm text-muted">{t("Open a batch and its Audit tab to read its events. The check below covers the whole chain.")}</p>
      </Card>
      <VerifyPanel />
    </div>
  );
}
