"use client";

import { useState, type FormEvent } from "react";
import { useI18n } from "@/lib/i18n";
import { msg } from "@/lib/i18n-core";
import { useApi } from "@/lib/client/api";
import { useAction } from "@/lib/client/action";
import { useConfig } from "@/lib/client/catalog";
import { useMode } from "@/lib/client/mode";
import { usePersona } from "@/lib/client/persona";
import { formatKg } from "@/lib/format";
import { hashscanToken, hashscanTransaction } from "@/lib/hashscan";
import type { Batch } from "@/lib/types";
import { HashChip } from "@/components/hash-chip";
import { Badge, Card, ErrorBox, Loading } from "@/components/ui";

type Retirement = { retirement_id: string; holder: string; units: number; beneficiary_ref: string; reason_code: string; tx_id: string; retired_at: string };
type CreditRow = {
  credit_id: string;
  batch_id: string;
  token_id: string;
  tx_id: string;
  units: number;
  provenance: string;
  alternative_permanence_model: boolean;
  balances: Record<string, number>;
  retirements: Retirement[];
};

const REASONS: Record<string, string> = {
  voluntary_offset: msg("Voluntary offset"),
  corporate_reporting: msg("Corporate reporting"),
  research: msg("Research"),
  other: msg("Other"),
};

function Link({ href, children }: { href: string | null; children: string }) {
  return href ? <a href={href} target="_blank" rel="noreferrer" className="text-accent underline">{children}</a> : <span>{children}</span>;
}

export function BatchCredit({ batch, onChanged }: { batch: Batch; onChanged: () => void }) {
  const { t } = useI18n();
  const { role, version } = usePersona();
  const config = useConfig();
  const { snapshot } = useMode();
  const credits = useApi<CreditRow[]>("credits", version);
  const done = () => {
    credits.reload();
    onChanged();
  };
  const me = useApi<{ actor_id: string }>("me", version);
  const mine = credits.data?.find((c) => c.batch_id === batch.batch_id) ?? null;

  if (credits.error) return <ErrorBox failure={credits.error} onRetry={credits.reload} />;
  if (credits.loading || !credits.data) return <Loading label={t("Loading")} />;
  if (!mine) {
    return (
      <Card>
        <p className="text-sm">{["ISSUED", "PARTIALLY_RETIRED", "RETIRED"].includes(batch.state) ? t("You hold no credits from this batch.") : t("No credits yet. They exist after the registry issues them.")}</p>
      </Card>
    );
  }

  const actor = me.data?.actor_id ?? "";
  const balance = mine.balances[actor] ?? 0;
  const canMove = !snapshot && (role === "holder" || role === "owner") && balance > 0;
  // Holders and owners see only their own balance (the API scopes it); privileged roles see every holder.
  const seesAll = role !== "holder" && role !== "owner";
  const total = Object.values(mine.balances).reduce((a, b) => a + b, 0);
  const txLink = hashscanTransaction(config?.hashscan_base, mine.tx_id);
  const tokenLink = hashscanToken(config?.hashscan_base, mine.token_id);

  return (
    <div className="flex flex-col gap-4">
      <Card>
        <h2 className="mb-3 text-base font-semibold">{t("Credit")}</h2>
        <dl className="grid grid-cols-1 gap-x-6 gap-y-1 text-sm sm:grid-cols-2">
          <Row label={t("Issued")} value={`${formatKg(mine.units)} ${t("units")} (${(mine.units / 1000).toLocaleString("en-US", { maximumFractionDigits: 3 })} t CO2e)`} />
          <Row label={t("Credit")} value={<span className="font-mono text-xs">{mine.credit_id}</span>} />
          <Row label={t("Token")} value={<Link href={tokenLink}>{mine.token_id}</Link>} />
          <Row label={t("Mint transaction")} value={txLink ? <Link href={txLink}>{mine.tx_id}</Link> : <HashChip value={mine.tx_id} label={t("Mint transaction")} />} />
          <Row label={t("Provenance")} value={<Badge tone="synthetic">{t("Synthetic")}</Badge>} />
          <Row label={seesAll ? t("Still available") : t("You hold")} value={`${formatKg(seesAll ? total : balance)} ${t("units")}`} />
        </dl>
        <p className="mt-3 text-xs text-muted">{t("One unit is 1 kg CO2e. Transfers between holders are recorded in the audit trail; retirements are recorded on the ledger.")}</p>
      </Card>

      <Card>
        <h2 className="mb-3 text-base font-semibold">{seesAll ? t("Balances") : t("Your balance")}</h2>
        {Object.keys(mine.balances).length === 0 ? (
          <p className="text-sm text-muted">{t("No balances.")}</p>
        ) : (
          <table className="w-full text-left text-sm">
            <caption className="sr-only">{t("Balances")}</caption>
            <thead className="text-xs text-muted">
              <tr><th scope="col" className="py-2 pr-3 font-medium">{t("Holder")}</th><th scope="col" className="py-2 text-right font-medium">{t("Units")}</th></tr>
            </thead>
            <tbody>
              {Object.entries(mine.balances).map(([holder, units]) => (
                <tr key={holder} className="border-t border-line">
                  <th scope="row" className="py-2 pr-3 text-left font-normal">{holder}{holder === actor ? <span className="ml-2 text-xs text-muted">{t("(you)")}</span> : null}</th>
                  <td className="py-2 text-right tabular-nums">{formatKg(units)}</td>
                </tr>
              ))}
            </tbody>
          </table>
        )}
      </Card>

      {canMove ? (
        <div className="grid gap-4 md:grid-cols-2">
          <TransferForm creditId={mine.credit_id} balance={balance} onDone={done} />
          <RetireForm creditId={mine.credit_id} balance={balance} onDone={done} />
        </div>
      ) : !snapshot && (role === "holder" || role === "owner") ? (
        <Card><p className="text-sm text-muted">{t("You hold no units of this credit, so you can't transfer or retire any.")}</p></Card>
      ) : null}

      <Card>
        <h2 className="mb-3 text-base font-semibold">{t("Retirements")}</h2>
        {mine.retirements.length === 0 ? (
          <p className="text-sm text-muted">{t("Nothing has been retired yet.")}</p>
        ) : (
          <div className="overflow-x-auto">
            <table className="w-full min-w-[560px] text-left text-sm">
              <caption className="sr-only">{t("Retirements")}</caption>
              <thead className="text-xs text-muted">
                <tr>
                  <th scope="col" className="py-2 pr-3 font-medium">{t("Holder")}</th>
                  <th scope="col" className="py-2 pr-3 text-right font-medium">{t("Units")}</th>
                  <th scope="col" className="py-2 pr-3 font-medium">{t("Beneficiary")}</th>
                  <th scope="col" className="py-2 pr-3 font-medium">{t("Purpose")}</th>
                  <th scope="col" className="py-2 font-medium">{t("Transaction")}</th>
                </tr>
              </thead>
              <tbody>
                {mine.retirements.map((r) => (
                  <tr key={r.retirement_id} className="border-t border-line">
                    <th scope="row" className="py-2 pr-3 text-left font-normal">{r.holder}</th>
                    <td className="py-2 pr-3 text-right tabular-nums">{formatKg(r.units)}</td>
                    <td className="py-2 pr-3">{r.beneficiary_ref}</td>
                    <td className="py-2 pr-3">{t(REASONS[r.reason_code] ?? r.reason_code)}</td>
                    <td className="py-2 font-mono text-xs"><Link href={hashscanTransaction(config?.hashscan_base, r.tx_id)}>{r.tx_id}</Link></td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </Card>
    </div>
  );
}

function Row({ label, value }: { label: string; value: React.ReactNode }) {
  return (
    <div className="flex justify-between gap-3 border-b border-line py-1">
      <dt className="text-muted">{label}</dt>
      <dd className="text-right">{value}</dd>
    </div>
  );
}

function parseUnits(text: string, max: number): number | null {
  if (!/^[0-9]+$/.test(text.trim())) return null;
  const n = Number(text);
  return n >= 1 && n <= max ? n : null;
}

function TransferForm({ creditId, balance, onDone }: { creditId: string; balance: number; onDone: () => void }) {
  const { t } = useI18n();
  const { run, busy, error, clear } = useAction();
  const [to, setTo] = useState("");
  const [units, setUnits] = useState("");
  const [problem, setProblem] = useState<string | null>(null);
  const [done, setDone] = useState<string | null>(null);

  async function submit(event: FormEvent) {
    event.preventDefault();
    const n = parseUnits(units, balance);
    if (!/^[A-Za-z0-9._:@-]{1,128}$/.test(to.trim())) return setProblem(t("Enter the recipient's name."));
    if (n === null) return setProblem(t("Enter a whole number of units between 1 and {max}.", { max: formatKg(balance) }));
    setProblem(null);
    const result = await run<{ units: number }>(`credits/${creditId}/transfer`, { to_holder: to.trim(), units: n });
    if (result) {
      setDone(t("Transferred {units} units to {to}.", { units: formatKg(n), to: to.trim() }));
      setUnits("");
      onDone();
    }
  }

  return (
    <Card>
      <h2 className="mb-2 text-base font-semibold">{t("Transfer units")}</h2>
      <form className="flex flex-col gap-2" onSubmit={(e) => void submit(e)}>
        <label htmlFor="transfer-to" className="text-sm">{t("Recipient")}</label>
        <input id="transfer-to" value={to} onChange={(e) => { setTo(e.target.value); setProblem(null); clear(); setDone(null); }} className="rounded-md border border-line bg-canvas p-2 text-sm" autoComplete="off" />
        <label htmlFor="transfer-units" className="text-sm">{t("Units (you hold {n})", { n: formatKg(balance) })}</label>
        <input id="transfer-units" inputMode="numeric" value={units} onChange={(e) => { setUnits(e.target.value); setProblem(null); clear(); setDone(null); }} className="rounded-md border border-line bg-canvas p-2 text-sm" />
        {problem ? <p role="alert" className="text-sm text-bad-ink">{problem}</p> : null}
        {error ? <ErrorBox failure={error} /> : null}
        {done ? <p role="status" className="text-sm text-ok-ink">{done}</p> : null}
        <button type="submit" disabled={busy} className="self-start rounded-md border border-line px-3 py-1.5 text-sm hover:bg-sidebar disabled:opacity-60">{busy ? t("Saving") : t("Transfer")}</button>
      </form>
    </Card>
  );
}

function RetireForm({ creditId, balance, onDone }: { creditId: string; balance: number; onDone: () => void }) {
  const { t } = useI18n();
  const { run, busy, error, clear } = useAction();
  const [units, setUnits] = useState("");
  const [beneficiary, setBeneficiary] = useState("");
  const [reason, setReason] = useState("voluntary_offset");
  const [confirming, setConfirming] = useState(false);
  const [problem, setProblem] = useState<string | null>(null);
  const [done, setDone] = useState<string | null>(null);

  function review(event: FormEvent) {
    event.preventDefault();
    if (parseUnits(units, balance) === null) return setProblem(t("Enter a whole number of units between 1 and {max}.", { max: formatKg(balance) }));
    if (beneficiary.trim() === "") return setProblem(t("Enter who the retirement is for."));
    setProblem(null);
    setConfirming(true);
  }

  async function confirm() {
    const n = parseUnits(units, balance);
    if (n === null) return;
    const result = await run<{ remaining_total_units: number }>(`credits/${creditId}/retire`, { units: n, beneficiary_ref: beneficiary.trim(), reason_code: reason });
    if (result) {
      setDone(t("Retired {units} units for {who}.", { units: formatKg(n), who: beneficiary.trim() }));
      setConfirming(false);
      setUnits("");
      onDone();
    }
  }

  return (
    <Card>
      <h2 className="mb-2 text-base font-semibold">{t("Retire units")}</h2>
      <form className="flex flex-col gap-2" onSubmit={review}>
        <label htmlFor="retire-units" className="text-sm">{t("Units (you hold {n})", { n: formatKg(balance) })}</label>
        <input id="retire-units" inputMode="numeric" value={units} onChange={(e) => { setUnits(e.target.value); setProblem(null); setConfirming(false); clear(); setDone(null); }} className="rounded-md border border-line bg-canvas p-2 text-sm" />
        <label htmlFor="retire-who" className="text-sm">{t("Beneficiary")}</label>
        <input id="retire-who" value={beneficiary} maxLength={128} onChange={(e) => { setBeneficiary(e.target.value); setProblem(null); setConfirming(false); clear(); setDone(null); }} className="rounded-md border border-line bg-canvas p-2 text-sm" autoComplete="off" />
        <label htmlFor="retire-reason" className="text-sm">{t("Purpose")}</label>
        <select id="retire-reason" value={reason} onChange={(e) => { setReason(e.target.value); setConfirming(false); }} className="rounded-md border border-line bg-canvas p-2 text-sm">
          {Object.entries(REASONS).map(([code, label]) => <option key={code} value={code}>{t(label)}</option>)}
        </select>
        {problem ? <p role="alert" className="text-sm text-bad-ink">{problem}</p> : null}
        {!confirming ? <button type="submit" className="self-start rounded-md border border-line px-3 py-1.5 text-sm hover:bg-sidebar">{t("Review retirement")}</button> : null}
      </form>
      {confirming ? (
        <div className="mt-3 flex flex-col gap-2 rounded-lg border border-line bg-canvas p-3">
          <p className="text-sm font-medium">{t("Confirm: retire {units} units for {who}? This can't be undone.", { units: formatKg(Number(units)), who: beneficiary.trim() })}</p>
          {error ? <ErrorBox failure={error} /> : null}
          <div className="flex gap-2">
            <button type="button" disabled={busy} onClick={() => void confirm()} className="rounded-md bg-accent px-3 py-1.5 text-sm font-medium text-accent-ink disabled:opacity-60">{busy ? t("Saving") : t("Confirm")}</button>
            <button type="button" onClick={() => { setConfirming(false); clear(); }} className="rounded-md border border-line px-3 py-1.5 text-sm">{t("Cancel")}</button>
          </div>
        </div>
      ) : null}
      {done ? <p role="status" className="mt-2 text-sm text-ok-ink">{done}</p> : null}
    </Card>
  );
}
