"use client";

/** Vue détail d'un run Buffett : allocation cible, backtest, exports (extrait de BuffettTab, #532). */

import { useState } from "react";
import { financeApi, type BuffettRunDetail } from "@/lib/finance";
import { Button } from "@/components/ui/button";
import { fmt, ScoreChip, StatusBadge } from "./buffett-ui";

export function BuffettRunDetailView({
  selected, onBack, onError,
}: {
  selected: BuffettRunDetail;
  onBack: () => void;
  onError: (msg: string) => void;
}) {
  const [backtest, setBacktest] = useState<{ rendement_pct: number; equity: number[]; n_points: number } | null>(null);
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

  // S'il existe des allocations : on affiche le portefeuille cible trié
  // par poids décroissant, sans les lignes à 0. Sinon : top scores MOAT.
  const allocated = selected.top_results
    .filter(r => (r.allocation_pct ?? 0) > 0)
    .sort((a, b) => (b.allocation_pct ?? 0) - (a.allocation_pct ?? 0));
  const hasAlloc = allocated.length > 0;
  const displayRows = hasAlloc ? allocated : selected.top_results;

  return (
    <div className="space-y-4">
      <div className="flex items-center gap-3 flex-wrap">
        <Button variant="ghost" size="sm" onClick={onBack}>← Retour</Button>
        <h2 className="text-base font-semibold">Run du {selected.run.run_date}</h2>
        <StatusBadge s={selected.run.statut} />
        <div className="ml-auto flex items-center gap-2">
          <Button variant="outline" size="sm" onClick={runBacktest} loading={backtesting}>
            📈 Backtest 2 ans
          </Button>
          <Button variant="outline" size="sm"
            onClick={() => exportRun(selected.run.id, selected.run.run_date, "xlsx")}>
            📊 Excel
          </Button>
          <Button variant="outline" size="sm"
            onClick={() => exportRun(selected.run.id, selected.run.run_date, "csv")}>
            📄 CSV
          </Button>
        </div>
      </div>
      {backtest && (
        <div className="rounded-xl border border-[var(--border)] bg-[var(--card)] px-4 py-3 text-sm flex items-center gap-3 flex-wrap">
          <span className="text-[var(--muted-foreground)]">Backtest buy-and-hold (2 ans) de l&apos;allocation cible :</span>
          {backtest.n_points > 0 ? (
            <span className={`font-mono font-semibold ${backtest.rendement_pct >= 0 ? "text-[var(--success)]" : "text-[var(--destructive)]"}`}>
              {backtest.rendement_pct >= 0 ? "+" : ""}{backtest.rendement_pct.toFixed(2)} %
            </span>
          ) : (
            <span className="text-[var(--muted-foreground)]">données indisponibles</span>
          )}
        </div>
      )}
      {selected.run.resume && (
        <p className="text-sm text-[var(--muted-foreground)]">{selected.run.resume}</p>
      )}
      <div>
        <h3 className="text-sm font-semibold mb-2">
          {hasAlloc ? "Allocation cible (par poids décroissant)" : "Top 50 scores MOAT"}
        </h3>
        <div className="overflow-x-auto">
          <table className="w-full text-sm">
            <thead>
              <tr className="border-b border-[var(--border)] text-xs text-[var(--muted-foreground)] text-left">
                <th className="pb-1 pr-3">Ticker</th>
                <th className="pb-1 pr-3">Nom</th>
                <th className="pb-1 pr-3">Secteur</th>
                <th className="pb-1 pr-3 text-right">Score</th>
                <th className="pb-1 text-right">Alloc. cible</th>
              </tr>
            </thead>
            <tbody>
              {displayRows.map(r => (
                <tr key={r.id} className="border-b border-[var(--border)]">
                  <td className="py-1 pr-3 font-mono text-xs">{r.ticker}</td>
                  <td className="py-1 pr-3 text-xs">{r.nom ?? "—"}</td>
                  <td className="py-1 pr-3 text-xs text-[var(--muted-foreground)]">{r.secteur ?? "—"}</td>
                  <td className="py-1 pr-3 text-right"><ScoreChip score={r.score} /></td>
                  <td className="py-1 text-right text-xs">
                    {r.allocation_pct ? `${fmt(r.allocation_pct)}%` : "—"}
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
