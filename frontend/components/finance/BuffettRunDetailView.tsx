"use client";

/** Vue détail d'un run Buffett : allocation cible, backtest, exports (extrait de BuffettTab, #532). */

import { useState } from "react";
import { financeApi, type BuffettRunDetail, type BuffettResultOut } from "@/lib/finance";
import { Button } from "@/components/ui/button";
import { fmt, ScoreChip, StatusBadge } from "./buffett-ui";

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
