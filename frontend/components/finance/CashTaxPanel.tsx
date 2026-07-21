"use client";

/** Liquidites, performance et revenus mobiliers nets du ledger. */

import { AlertTriangle, RefreshCw } from "lucide-react";
import { usePortfolioState } from "@/lib/queries/finance";
import { Button } from "@/components/ui/button";

const money = (value: number) =>
  value.toLocaleString("fr-FR", {
    style: "currency",
    currency: "EUR",
    minimumFractionDigits: 0,
    maximumFractionDigits: 2,
  });

export function CashTaxPanel() {
  const stateQuery = usePortfolioState();
  const state = stateQuery.data;

  if (stateQuery.isError) {
    return (
      <div
        role="alert"
        className="flex flex-wrap items-center justify-between gap-3 rounded-[var(--radius)] border border-[var(--destructive)]/30 p-4"
      >
        <span className="flex items-center gap-2 text-sm text-[var(--destructive)]">
          <AlertTriangle className="h-4 w-4" aria-hidden />
          Liquidités et performance indisponibles.
        </span>
        <Button size="sm" variant="ghost" onClick={() => void stateQuery.refetch()}>
          <RefreshCw className="h-3.5 w-3.5" aria-hidden />
          Réessayer
        </Button>
      </div>
    );
  }

  if (!state) {
    return (
      <div className="grid gap-3 md:grid-cols-2" aria-label="Chargement des données financières">
        <div className="skeleton-shimmer h-44 rounded-[var(--radius-lg)]" />
        <div className="skeleton-shimmer h-44 rounded-[var(--radius-lg)]" />
      </div>
    );
  }

  return (
    <div className="grid gap-3 md:grid-cols-2">
      <section className="glass-card rounded-[var(--radius-lg)] p-4">
        <div className="mb-3 flex items-center justify-between gap-3">
          <h3 className="text-sm font-semibold">Liquidités &amp; performance</h3>
          <span className="text-[10px] text-[var(--muted-foreground)]">Cumul du ledger</span>
        </div>
        <dl className="grid grid-cols-2 gap-x-4 gap-y-3 text-sm">
          <Stat label="Cash disponible" value={money(state.cash_total)} tone={state.cash_total < 0 ? "negative" : undefined} />
          <Stat label="Versements nets" value={money(state.investi_net)} />
          <Stat label="P&L latent" value={money(state.pl_latent_total)} tone={state.pl_latent_total >= 0 ? "positive" : "negative"} />
          <Stat label="P&L réalisé" value={money(state.pl_realise)} tone={state.pl_realise >= 0 ? "positive" : "negative"} />
        </dl>
        {Object.keys(state.cash_par_broker).length > 0 && (
          <div className="mt-3 flex flex-wrap gap-x-4 gap-y-1 border-t border-[var(--glass-border)] pt-2 text-xs text-[var(--muted-foreground)]">
            {Object.entries(state.cash_par_broker).map(([broker, value]) => (
              <span key={broker}>{broker} <strong className="font-mono font-medium text-[var(--foreground)]">{money(value)}</strong></span>
            ))}
          </div>
        )}
      </section>

      <section className="glass-card rounded-[var(--radius-lg)] p-4">
        <div className="mb-3 flex items-center justify-between gap-3">
          <h3 className="text-sm font-semibold">Revenus mobiliers</h3>
          <span className="text-[10px] text-[var(--muted-foreground)]">Toutes années</span>
        </div>
        <dl className="grid grid-cols-2 gap-x-4 gap-y-3 text-sm">
          <Stat label="Dividendes bruts" value={money(state.dividendes_bruts ?? state.dividendes_total)} />
          <Stat label="Retenue à la source" value={money(state.retenues_source ?? 0)} tone={(state.retenues_source ?? 0) > 0 ? "warning" : undefined} />
          <Stat label="Dividendes nets" value={money(state.dividendes_total)} />
          <Stat label="Intérêts nets" value={money(state.interets_total ?? 0)} />
          <Stat label="Total net encaissé" value={money(state.revenus_mobiliers_total ?? state.dividendes_total)} strong />
        </dl>
        <p className="mt-3 border-t border-[var(--glass-border)] pt-2 text-[11px] leading-relaxed text-[var(--muted-foreground)]">
          Les intérêts sont imposables sans abattement de 40 %. Les retenues étrangères restent séparées et leur crédit dépend de la convention applicable.
        </p>
      </section>
    </div>
  );
}

function Stat({
  label,
  value,
  tone,
  strong,
}: {
  label: string;
  value: string;
  tone?: "positive" | "negative" | "warning";
  strong?: boolean;
}) {
  const toneClass =
    tone === "positive"
      ? "text-[var(--success-foreground)]"
      : tone === "negative"
        ? "text-[var(--destructive)]"
        : tone === "warning"
          ? "text-[var(--warning-foreground)]"
          : "text-[var(--foreground)]";
  return (
    <div>
      <dt className="text-xs text-[var(--muted-foreground)]">{label}</dt>
      <dd className={`mt-0.5 font-mono tabular-nums ${strong ? "text-lg font-semibold" : "font-medium"} ${toneClass}`}>
        {value}
      </dd>
    </div>
  );
}
