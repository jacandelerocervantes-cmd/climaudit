"use client";

import { useState } from "react";
import { useI18n } from "@/lib/i18n";
import { api, ApiFailure } from "@/lib/client/api";
import { useMode } from "@/lib/client/mode";
import { usePersona } from "@/lib/client/persona";
import { ROLE_LABELS } from "@/lib/messages";
import type { VerifyResult } from "@/lib/types";
import { Badge, Card, ErrorBox } from "@/components/ui";

const ALLOWED = ["verifier", "registry", "admin"];

/** Recomputes the hash chain of every audit event and compares it with what the public ledger holds. */
export function VerifyPanel() {
  const { t } = useI18n();
  const { role } = usePersona();
  const { snapshot } = useMode();
  const [result, setResult] = useState<VerifyResult | null>(null);
  const [error, setError] = useState<ApiFailure | null>(null);
  const [busy, setBusy] = useState(false);

  async function check() {
    setBusy(true);
    setError(null);
    try {
      setResult(await api<VerifyResult>("audit/verify"));
    } catch (failure) {
      setResult(null);
      setError(failure instanceof ApiFailure ? failure : new ApiFailure("INTERNAL_ERROR", 0));
    } finally {
      setBusy(false);
    }
  }

  const allowed = role !== null && ALLOWED.includes(role);
  return (
    <Card>
      <h2 className="mb-1 text-base font-semibold">{t("Check against the public ledger")}</h2>
      <p className="text-sm text-muted">{t("Recomputes the hash of every audit event, walks the chain from the first event, and compares it with the hashes published on the ledger. A gap, a reordered event or a foreign message is reported.")}</p>
      {!allowed ? (
        <p className="mt-3 text-sm">{t("This check is available to the verifier, registry and admin roles. You are acting as {role}.", { role: role ? t(ROLE_LABELS[role] ?? role) : "-" })}</p>
      ) : (
        <button type="button" onClick={() => void check()} disabled={busy} className="mt-3 rounded-md bg-accent px-3 py-1.5 text-sm font-medium text-accent-ink disabled:opacity-60">
          {busy ? t("Checking") : t("Run the check")}
        </button>
      )}
      {error ? <div className="mt-3"><ErrorBox failure={error} /></div> : null}
      {result ? (
        <div role="status" className="mt-3 flex flex-col gap-2">
          <p className="flex flex-wrap items-center gap-2 text-sm">
            <Badge tone={result.chain_ok ? "ok" : "bad"}><span aria-hidden="true">{result.chain_ok ? "✓" : "✕"}</span>{result.chain_ok ? t("Hash chain intact") : t("Hash chain broken")}</Badge>
            <Badge tone={result.ledger_matches ? "ok" : "bad"}><span aria-hidden="true">{result.ledger_matches ? "✓" : "✕"}</span>{result.ledger_matches ? t("Ledger matches") : t("Ledger does not match")}</Badge>
          </p>
          <p className="text-sm">{t("{events} audit events here, {published} messages on the ledger.", { events: result.event_count, published: result.ledger_count })}</p>
          {snapshot ? <p className="text-xs text-muted">{t("This result was recorded when the run was made. Run the app locally to check again.")}</p> : null}
          {!result.chain_ok && result.first_broken_seq !== null ? <p className="text-sm text-bad-ink">{t("The chain first breaks at event {seq}.", { seq: result.first_broken_seq })}</p> : null}
          {result.chain_ok && !result.ledger_matches ? <p className="text-sm text-warn-ink">{t("The ledger can lag by a few seconds. If it keeps differing, something was published that this system did not record, or the other way round.")}</p> : null}
        </div>
      ) : null}
    </Card>
  );
}

