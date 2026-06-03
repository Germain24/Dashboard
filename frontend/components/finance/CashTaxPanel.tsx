"use client";

/** Cash + fiscalité : liquidités, plus-value réalisée/latente, taxes estimées (taux éditables). */

import { useCallback, useEffect, useState } from "react";
import { financeApi, type PortfolioStateOut, type FinanceSettingsOut } from "@/lib/finance";

const money = (v: number) =>
  v.toLocaleString("fr-CA", { style: "currency", currency: "EUR", maximumFractionDigits: 0 });

export function CashTaxPanel() {
  const [state, setState] = useState<PortfolioStateOut | null>(null);
  const [settings, setSettings] = useState<FinanceSettingsOut | null>(null);
  const [saving, setSaving] = useState(false);

  const load = useCallback(async () => {
    try {
      const [st, se] = await Promise.all([financeApi.state(), financeApi.settings()]);
      setState(st);
      setSettings(se);
    } catch { /* toast global */ }
  }, []);

  useEffect(() => { load(); }, [load]);

  const saveRate = async (key: "taux_plus_value_pct" | "taux_dividende_pct", value: number) => {
    if (!settings) return;
    setSaving(true);
    try {
      const updated = await financeApi.patchSettings({ [key]: value });
      setSettings(updated);
      setState(await financeApi.state()); // taxes recalculées
    } catch { /* toast global */ }
    finally { setSaving(false); }
  };

  if (!state || !settings) return null;

  return (
    <div className="grid gap-3 md:grid-cols-2">
      {/* Cash & P&L */}
      <div className="rounded-[var(--radius-lg)] border border-[var(--border)] p-4 space-y-2">
        <h3 className="text-sm font-semibold">Liquidités &amp; performance</h3>
        <div className="grid grid-cols-2 gap-2 text-sm">
          <Stat label="Cash total" value={money(state.cash_total)} />
          <Stat label="Investi net" value={money(state.investi_net)} />
          <Stat label="P&L latent" value={money(state.pl_latent_total)} positive={state.pl_latent_total >= 0} />
          <Stat label="P&L réalisé" value={money(state.pl_realise)} positive={state.pl_realise >= 0} />
        </div>
        {Object.keys(state.cash_par_broker).length > 0 && (
          <ul className="text-xs text-[var(--muted-foreground)] pt-1">
            {Object.entries(state.cash_par_broker).map(([b, v]) => (
              <li key={b}>{b} : <span className="font-mono">{money(v)}</span></li>
            ))}
          </ul>
        )}
      </div>

      {/* Taxes estimées */}
      <div className="rounded-[var(--radius-lg)] border border-[var(--border)] p-4 space-y-2">
        <h3 className="text-sm font-semibold">Taxes estimées</h3>
        <div className="grid grid-cols-2 gap-2 text-sm">
          <Stat label="Impôt plus-value" value={money(state.taxes.impot_pv)} />
          <Stat label="Impôt dividendes" value={money(state.taxes.impot_div)} />
          <Stat label="Total estimé" value={money(state.taxes.total)} />
        </div>
        <div className="flex flex-wrap items-end gap-3 pt-1">
          <RateInput label="Taux plus-value %" value={settings.taux_plus_value_pct}
            disabled={saving} onCommit={(v) => saveRate("taux_plus_value_pct", v)} />
          <RateInput label="Taux dividendes %" value={settings.taux_dividende_pct}
            disabled={saving} onCommit={(v) => saveRate("taux_dividende_pct", v)} />
        </div>
        <p className="text-[10px] text-[var(--muted-foreground)]">Estimation indicative (taux effectif), pas un calcul fiscal officiel.</p>
      </div>
    </div>
  );
}

function Stat({ label, value, positive }: { label: string; value: string; positive?: boolean }) {
  return (
    <div>
      <p className="text-xs text-[var(--muted-foreground)]">{label}</p>
      <p className={`font-mono font-semibold ${positive === undefined ? "" : positive ? "text-[var(--success)]" : "text-[var(--destructive)]"}`}>{value}</p>
    </div>
  );
}

function RateInput({ label, value, disabled, onCommit }: { label: string; value: number; disabled: boolean; onCommit: (v: number) => void }) {
  const [v, setV] = useState(String(value));
  useEffect(() => setV(String(value)), [value]);
  return (
    <label className="flex flex-col gap-0.5">
      <span className="text-xs text-[var(--muted-foreground)]">{label}</span>
      <input
        type="number" value={v} disabled={disabled}
        onChange={(e) => setV(e.target.value)}
        onBlur={() => { const n = parseFloat(v); if (!Number.isNaN(n) && n !== value) onCommit(n); }}
        className="w-24 px-2 py-1.5 text-sm rounded-md border border-[var(--border)] bg-[var(--background)]"
      />
    </label>
  );
}
