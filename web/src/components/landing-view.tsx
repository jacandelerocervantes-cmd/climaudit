"use client";

import { useRouter } from "next/navigation";
import { ROLES, type Role } from "@/lib/config";
import { useI18n } from "@/lib/i18n";
import { msg } from "@/lib/i18n-core";
import { usePersona } from "@/lib/client/persona";
import { ROLE_LABELS } from "@/lib/messages";
import { Card } from "@/components/ui";

const ROLE_ABOUT: Record<Role, string> = {
  owner: msg("Submits a biochar batch with its evidence and follows it to a decision."),
  verifier: msg("Reviews the evidence and the findings, then verifies, returns or rejects the batch."),
  registry: msg("Issues the credits of a verified batch and checks the audit trail against the ledger."),
  holder: msg("Holds credits, transfers them and retires them with a named beneficiary."),
  admin: msg("Sees everything and can act in any step. For the demo only."),
};

export function LandingView() {
  const { t } = useI18n();
  const router = useRouter();
  const { role, loading, setRole } = usePersona();

  async function enter(next: Role) {
    await setRole(next);
    router.push("/batches");
  }

  return (
    <div className="mx-auto flex max-w-3xl flex-col gap-4">
      <div>
        <h1 className="text-xl font-semibold">{t("Check the evidence behind a biochar carbon credit")}</h1>
        <p className="mt-2 text-sm text-muted">
          {t("ClimAudit checks a batch against Verra VM0044, computes the carbon dioxide removed as a range, and keeps a public audit trail. A person decides.")}
        </p>
      </div>
      <h2 className="text-base font-semibold">{t("Choose a role to start")}</h2>
      <ul className="grid gap-3 sm:grid-cols-2">
        {ROLES.map((r) => (
          <li key={r}>
            <Card>
              <h3 className="text-base font-semibold">{t(ROLE_LABELS[r] ?? r)}</h3>
              <p className="mt-1 min-h-10 text-sm text-muted">{t(ROLE_ABOUT[r])}</p>
              <button
                type="button"
                disabled={loading}
                onClick={() => void enter(r)}
                className="mt-3 rounded-md bg-accent px-3 py-1.5 text-sm font-medium text-accent-ink disabled:opacity-60"
              >
                {role === r ? t("Continue as {role}", { role: t(ROLE_LABELS[r] ?? r) }) : t("Enter as {role}", { role: t(ROLE_LABELS[r] ?? r) })}
              </button>
            </Card>
          </li>
        ))}
      </ul>
    </div>
  );
}
