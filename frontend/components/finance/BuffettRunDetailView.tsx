"use client";

/** Vue détail d'un run Buffett : allocation cible, backtest, exports (extrait de BuffettTab, #532). */

import { useState } from "react";
import { financeApi, type BuffettRunDetail, type BuffettResultOut } from "@/lib/finance";
import { Button } from "@/components/ui/button";
import { fmt, ScoreChip, StatusBadge, type OptProgress } from "./buffett-ui";
import { DeStarrChart } from "./DeStarrChart";

/** Abrège le nom du broker pour l'affichage compact. */
function brokerShort(b?: string): string {
  if (!b) return "";
  const c = b.toLowerCase().replace(/[^a-z0-9]/g, "");
  if (c.includes("trading212") || c === "t212") return "T212";
  if (c.includes("boursedirect") || c.includes("boursdirect")) return "Bourso";
  if (c.includes("ibkr")) return "IBKR";
  return b;
}

/** Montant total investi (€) sur un titre, tous brokers confondus. */
function investedEur(r: BuffettResultOut): number {
  return (r.allocations ?? []).reduce((s, a) => s + (a.eur ?? 0), 0);
}

const fmtEur = (v: number) =>
  `${Math.round(v).toLocaleString("fr-FR")} €`;

/** Allocation actionnable par titre : « X % pie (T212) » et/ou « N act. (broker) ». */
function AllocCell({ r }: { r: BuffettResultOut }) {
  const lines = (r.allocations ?? []).filter(a =>
    a.type === "pie" ? (a.pie_pct ?? 0) > 0 : (a.shares ?? 0) > 0,
  );
  if (lines.length === 0) {
    return <span>{r.allocation_pct ? `${fmt(r.allocation_pct)} %` : "—"}</span>;
  }
  return (
    <div className="flex flex-col items-end gap-0.5">
      {lines.map((a, i) => (
        <span key={i} className="whitespace-nowrap">
          {a.type === "pie" ? (
            <><span className="font-semibold">{a.pie_pct} %</span>{" "}
              <span className="text-[var(--muted-foreground)]">pie {brokerShort(a.broker)}</span></>
          ) : (
            <><span className="font-semibold">{a.shares}</span>{" "}
              <span className="text-[var(--muted-foreground)]">
                {a.shares === 1 ? "action" : "actions"} {brokerShort(a.broker)}
              </span></>
          )}
        </span>
      ))}
    </div>
  );
}

export function BuffettRunDetailView({
  selected, onBack, onError, optProgress = null,
}: {
  selected: BuffettRunDetail;
  onBack: () => void;
  onError: (msg: string) => void;
  /** Progression DE live (pollée par le parent) : affiche le graphe STARR ici
   *  aussi — avant, il n'existait que sur la vue liste de l'onglet, donc il
   *  « disparaissait » dès qu'on ouvrait le détail du run (#bug rapporté). */
  optProgress?: OptProgress | null;
}) {
  const [backtest, setBacktest] = useState<{
    rendement_pct: number;
    equity: number[];
    n_points: number;
    mode?: "walk_forward";
    n_runs?: number;
    n_rebalances?: number;
    turnover?: number;
    costs_pct?: number;
    max_drawdown_pct?: number;
    cvar_5_pct?: number;
    cagr_pct?: number;
    comparisons?: Record<string, {
      rendement_pct: number;
      cagr_pct: number;
      max_drawdown_pct: number;
    }>;
  } | null>(null);
  const [backtesting, setBacktesting] = useState(false);

  const runBacktest = async () => {
    setBacktesting(true); setBacktest(null);
    try {
      setBacktest(await financeApi.backtest("2y"));
    } catch (e: unknown) {
      onError(e instanceof Error ? e.message : "Erreur backtest");
    } finally {
      setBacktesting(false);
    }
  };

  const runWalkForward = async () => {
    setBacktesting(true); setBacktest(null);
    try {
      setBacktest(await financeApi.backtestWalkForward("5y", 10));
    } catch (e: unknown) {
      onError(e instanceof Error ? e.message : "Erreur backtest walk-forward");
    } finally {
      setBacktesting(false);
    }
  };

  const exportRun = async (runId: number, runDate: string, format: "xlsx" | "csv") => {
    try {
      const path = format === "csv" ? `export.csv` : `export`;
      const res = await fetch(`/api/finance/buffett/runs/${runId}/${path}`);
      if (!res.ok) throw new Error("Erreur export");
      const blob = await res.blob();
      const url = URL.createObjectURL(blob);
      const a = document.createElement("a");
      a.href = url; a.download = `buffett_run_${runId}_${runDate}.${format}`;
      a.click(); URL.revokeObjectURL(url);
    } catch (e: unknown) {
      onError(e instanceof Error ? e.message : `Erreur export ${format}`);
    }
  };

  // S'il existe une allocation cible : on affiche le portefeuille complet à
  // acheter (toutes les lignes allouées, pas seulement le top 50 par score),
  // trié par poids décroissant. Sinon : top scores MOAT.
  const allocated = [...selected.allocation_cible]
    .filter(r => (r.allocation_pct ?? 0) > 0)
    .sort((a, b) => investedEur(b) - investedEur(a));   // tri par montant investi décroissant
  const hasAlloc = allocated.length > 0;
  const displayRows = hasAlloc ? allocated : selected.top_results;
  const totalInvested = allocated.reduce((s, r) => s + investedEur(r), 0);
  const totalPct = allocated.reduce((s, r) => s + (r.allocation_pct ?? 0), 0);

  return (
    <div className="space-y-4">
      <div className="flex items-center gap-3 flex-wrap">
        <Button variant="ghost" size="sm" onClick={onBack}>← Retour</Button>
        <h2 className="text-base font-semibold">Run du {selected.run.run_date}</h2>
        <StatusBadge s={selected.run.statut} />
        <div className="ml-auto flex items-center gap-2">
          <Button variant="outline" size="sm" onClick={() => { void runBacktest(); }} loading={backtesting}>
            📈 Backtest 2 ans
          </Button>
          <Button variant="outline" size="sm" onClick={() => { void runWalkForward(); }} loading={backtesting}>
            🧭 Walk-forward
          </Button>
          <Button variant="outline" size="sm"
            onClick={() => { void exportRun(selected.run.id, selected.run.run_date, "xlsx"); }}>
            📊 Excel
          </Button>
          <Button variant="outline" size="sm"
            onClick={() => { void exportRun(selected.run.id, selected.run.run_date, "csv"); }}>
            📄 CSV
          </Button>
        </div>
      </div>
      {selected.run.statut === "en_cours" && (
        <p className="text-xs rounded-[var(--radius)] bg-[var(--info-muted)] text-[var(--info-foreground)] px-3 py-2">
          🔄 Optimisation en cours — recherche de meilleures allocations, actualisation automatique.
        </p>
      )}
      {optProgress?.active && optProgress.run_id === selected.run.id && (
        <DeStarrChart optProgress={optProgress} />
      )}
      {backtest && (
        <div className="rounded-xl border border-[var(--border)] bg-[var(--card)] px-4 py-3 text-sm flex items-center gap-3 flex-wrap">
          <span className="text-[var(--muted-foreground)]">
            {backtest.mode === "walk_forward"
              ? `Walk-forward trimestriel (${backtest.n_runs ?? 0} runs, frais 10 pb) :`
              : "Backtest buy-and-hold (2 ans) de l'allocation cible :"}
          </span>
          {backtest.n_points > 0 ? (
            <span className={`font-mono font-semibold ${backtest.rendement_pct >= 0 ? "text-[var(--success)]" : "text-[var(--destructive)]"}`}>
              {backtest.rendement_pct >= 0 ? "+" : ""}{backtest.rendement_pct.toFixed(2)} %
            </span>
          ) : (
            <span className="text-[var(--muted-foreground)]">données indisponibles</span>
          )}
          {backtest.mode === "walk_forward" && backtest.n_points > 0 && (
            <>
              <span className="text-xs text-[var(--muted-foreground)]">
                CAGR {fmt(backtest.cagr_pct)} % · drawdown {fmt(backtest.max_drawdown_pct)} % · CVaR 5 % {fmt(backtest.cvar_5_pct)} % · turnover {fmt((backtest.turnover ?? 0) * 100)} %
              </span>
              {backtest.comparisons && (
                <span className="basis-full text-xs text-[var(--muted-foreground)]">
                  Comparaison CAGR : optimisé {fmt(backtest.comparisons.optimized?.cagr_pct)} % · équipondéré {fmt(backtest.comparisons.equal_weight?.cagr_pct)} % · CW8 {fmt(backtest.comparisons["CW8.PA"]?.cagr_pct)} %
                </span>
              )}
            </>
          )}
        </div>
      )}
      {selected.run.resume && (
        <p className="text-sm text-[var(--muted-foreground)]">{selected.run.resume}</p>
      )}
      {selected.optimization && (
        <div className="space-y-3 rounded-xl border border-[var(--border)] bg-[var(--card)] px-4 py-3">
          <h3 className="text-sm font-semibold mb-2">Comparaison reproductible des stratégies</h3>
          <div className="grid gap-2 text-xs sm:grid-cols-2 lg:grid-cols-4">
            <div><span className="text-[var(--muted-foreground)]">Portefeuille réel</span><br /><strong>{fmt(selected.optimization.benchmarks.optimized, 4)}</strong></div>
            <div><span className="text-[var(--muted-foreground)]">Équipondéré ({selected.optimization.benchmarks.equal_weight_max_lines_per_broker} lignes/broker)</span><br /><strong>{fmt(selected.optimization.benchmarks.equal_weight, 4)}</strong></div>
            <div><span className="text-[var(--muted-foreground)]">Meilleur candidat simple (top {selected.optimization.benchmarks.best_single_candidates_tested})</span><br /><strong>{selected.optimization.benchmarks.best_single_ticker ?? "—"} · {fmt(selected.optimization.benchmarks.best_single, 4)}</strong></div>
            <div><span className="text-[var(--muted-foreground)]">Reproductibilité</span><br /><strong>seed {selected.optimization.seed} · {selected.optimization.termination.seeds_run} seed(s)</strong></div>
          </div>
          <p className="mt-2 text-xs text-[var(--muted-foreground)]">
            Score calculé en {selected.optimization.base_currency ?? "EUR"}, après budgets et disponibilités broker · arrêt après {selected.optimization.termination.stagnation_generations} générations sans amélioration.
          </p>
          {selected.optimization.regimes && (
            <div className="border-t border-[var(--border)] pt-3">
              <h4 className="text-xs font-semibold mb-2">Régimes historiques et stress</h4>
              <div className="flex flex-wrap gap-2">
                {selected.optimization.regimes.windows.map(window => (
                  <span key={window.label} className="rounded-full bg-[var(--muted)] px-2.5 py-1 text-xs">
                    {window.label} · {window.observations} j · {(window.weight * 100).toFixed(0)} %
                  </span>
                ))}
              </div>
            </div>
          )}
          {selected.optimization.etf_selection?.enabled && (
            <div className="border-t border-[var(--border)] pt-3">
              <h4 className="text-xs font-semibold mb-2">
                Présélection ETF · {selected.optimization.etf_selection.n_etf_before} → {selected.optimization.etf_selection.n_etf_after} dans l&apos;union
              </h4>
              <div className="grid gap-2 text-xs sm:grid-cols-2 lg:grid-cols-3">
                {Object.entries(selected.optimization.etf_selection.brokers).map(([broker, info]) => (
                  <div key={broker} className="rounded-lg bg-[var(--muted)] px-3 py-2">
                    <strong>{brokerShort(broker)}</strong><br />
                    <span className="text-[var(--muted-foreground)]">
                      {info.candidates_before} candidats → {info.selected} retenus
                    </span>
                  </div>
                ))}
              </div>
            </div>
          )}
          {(selected.optimization.estimation || selected.optimization.turnover) && (
            <div className="grid gap-2 border-t border-[var(--border)] pt-3 text-xs sm:grid-cols-2 lg:grid-cols-4">
              {selected.optimization.estimation && (
                <>
                  <div><span className="text-[var(--muted-foreground)]">Signal rendement propre</span><br /><strong>{(selected.optimization.estimation.mean_signal_weight * 100).toFixed(0)} %</strong></div>
                  <div><span className="text-[var(--muted-foreground)]">Shrinkage corrélations</span><br /><strong>{(selected.optimization.estimation.correlation_shrinkage * 100).toFixed(0)} %</strong></div>
                </>
              )}
              {selected.optimization.turnover && (
                <>
                  <div><span className="text-[var(--muted-foreground)]">Turnover estimé</span><br /><strong>{(selected.optimization.turnover.estimated_one_way * 100).toFixed(1)} %</strong></div>
                  <div><span className="text-[var(--muted-foreground)]">Bande sans intervention</span><br /><strong>{(selected.optimization.turnover.rebalance_band * 100).toFixed(1)} %</strong></div>
                </>
              )}
            </div>
          )}
          {selected.optimization.transaction_costs?.enabled && (
            <div className="border-t border-[var(--border)] pt-3 text-xs">
              <h4 className="mb-2 font-semibold">Frais intégrés à l’optimisation</h4>
              <div className="grid gap-2 sm:grid-cols-2 lg:grid-cols-4">
                <div><span className="text-[var(--muted-foreground)]">Prochain rebalancement</span><br /><strong>{selected.optimization.transaction_costs.trade_cost_eur.toFixed(2)} €</strong></div>
                <div><span className="text-[var(--muted-foreground)]">Coût annualisé</span><br /><strong>{selected.optimization.transaction_costs.annualized_cost_eur.toFixed(2)} €</strong></div>
                <div><span className="text-[var(--muted-foreground)]">Impact annuel</span><br /><strong>{(selected.optimization.transaction_costs.annualized_cost_pct * 100).toFixed(2)} %</strong></div>
                <div><span className="text-[var(--muted-foreground)]">Garde étrangère annuelle</span><br /><strong>{selected.optimization.transaction_costs.annual_custody_eur.toFixed(2)} €</strong></div>
              </div>
              <div className="mt-2 flex flex-wrap gap-2 text-[var(--muted-foreground)]">
                {selected.optimization.transaction_costs.brokers.map(info => (
                  <span key={info.broker} className="rounded-full border border-[var(--border)] px-2 py-1">
                    {brokerShort(info.broker)} · ordre {info.trade_cost_eur.toFixed(2)} €
                    {info.annual_custody_eur > 0 ? ` · garde ${info.annual_custody_eur.toFixed(2)} €` : ""}
                  </span>
                ))}
              </div>
            </div>
          )}
          {selected.optimization.regimes?.correlation_stability?.available && (
            <div className="border-t border-[var(--border)] pt-3 text-xs">
              <h4 className="font-semibold mb-1">Stabilité des corrélations</h4>
              <p className="text-[var(--muted-foreground)]">
                {selected.optimization.regimes.correlation_stability.unstable_pairs ?? 0} paires instables · {selected.optimization.regimes.correlation_stability.major_shift_pairs ?? 0} changements majeurs
              </p>
              <div className="mt-2 flex flex-wrap gap-2">
                {(selected.optimization.regimes.correlation_stability.top_pairs ?? []).slice(0, 5).map(pair => (
                  <span key={`${pair.ticker_a}-${pair.ticker_b}`} className="rounded-full border border-[var(--border)] px-2 py-1">
                    {pair.ticker_a}/{pair.ticker_b} · Δ {pair.max_delta.toFixed(2)}
                  </span>
                ))}
              </div>
            </div>
          )}
        </div>
      )}
      <div>
        <h3 className="text-sm font-semibold mb-2 flex items-baseline gap-2 flex-wrap">
          {hasAlloc ? "Allocation cible (par montant investi)" : "Top 50 scores MOAT"}
          {hasAlloc && (
            <span className="text-xs font-normal text-[var(--muted-foreground)]">
              — {fmtEur(totalInvested)} investis ({fmt(totalPct)} % du capital)
            </span>
          )}
        </h3>
        <div className="overflow-x-auto">
          <table className="w-full text-sm">
            <thead>
              <tr className="border-b border-[var(--border)] text-xs text-[var(--muted-foreground)] text-left">
                <th className="pb-1 pr-3">Ticker</th>
                <th className="pb-1 pr-3">Nom</th>
                <th className="pb-1 pr-3">Secteur</th>
                <th className="pb-1 pr-3 text-right">Score</th>
                {hasAlloc && <th className="pb-1 pr-3 text-right">Investi</th>}
                <th className="pb-1 text-right">{hasAlloc ? "À acheter" : "Alloc. cible"}</th>
              </tr>
            </thead>
            <tbody>
              {displayRows.map(r => (
                <tr key={r.id} className="border-b border-[var(--border)]">
                  <td className="py-1 pr-3 font-mono text-xs">{r.ticker}</td>
                  <td className="py-1 pr-3 text-xs">{r.nom ?? "—"}</td>
                  <td className="py-1 pr-3 text-xs text-[var(--muted-foreground)]">{r.secteur ?? "—"}</td>
                  <td className="py-1 pr-3 text-right"><ScoreChip score={r.score} /></td>
                  {hasAlloc && (
                    <td className="py-1 pr-3 text-right text-xs whitespace-nowrap">
                      <span className="font-semibold">{fmtEur(investedEur(r))}</span>
                      {r.allocation_pct != null && (
                        <span className="text-[var(--muted-foreground)]"> · {fmt(r.allocation_pct)} %</span>
                      )}
                    </td>
                  )}
                  <td className="py-1 text-right text-xs">
                    <AllocCell r={r} />
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </div>
    </div>
  );
}
