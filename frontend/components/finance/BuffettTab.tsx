"use client";

import { useEffect, useState, useCallback, useRef } from "react";
import {
  financeApi, type BuffettRunOut, type BuffettRunDetail, type BuffettProgress,
} from "@/lib/finance";
import { Spinner } from "@/components/ui/spinner";
import { EmptyState } from "@/components/ui/empty-state";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";

function fmt(n?: number, dec = 1) {
  return n != null ? n.toLocaleString("fr-FR", { minimumFractionDigits: dec, maximumFractionDigits: dec }) : "—";
}

function StatusBadge({ s }: { s: string }) {
  const map: Record<string, "success" | "warning" | "destructive" | "info"> = {
    termine: "success", en_cours: "info", interrompu: "warning", erreur: "destructive",
  };
  return <Badge variant={map[s] ?? "outline"}>{s}</Badge>;
}

function ProgressBar({ pct }: { pct: number }) {
  return (
    <div className="w-full h-2 rounded-full bg-[var(--muted)] overflow-hidden">
      <div className="h-full rounded-full bg-[var(--ring)] transition-all"
        style={{ width: `${Math.min(100, pct)}%` }} />
    </div>
  );
}

function ScoreChip({ score }: { score?: number }) {
  if (score == null) return <span className="text-[var(--muted-foreground)]">—</span>;
  const color = score >= 200
    ? "text-[var(--info)]"
    : score >= 80 ? "text-[var(--success)]" : "";
  const label = score >= 200 ? "ETF" : fmt(score);
  return <span className={`font-medium ${color}`}>{label}</span>;
}

export function BuffettTab() {
  const [runs, setRuns] = useState<BuffettRunOut[]>([]);
  const [selected, setSelected] = useState<BuffettRunDetail | null>(null);
  const [progress, setProgress] = useState<BuffettProgress | null>(null);
  const [loading, setLoading] = useState(true);
  const [starting, setStarting] = useState(false);
  const [creatingPortfolio, setCreatingPortfolio] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [backtest, setBacktest] = useState<{ rendement_pct: number; equity: number[]; n_points: number } | null>(null);
  const [backtesting, setBacktesting] = useState(false);

  const runBacktest = async () => {
    setBacktesting(true); setBacktest(null);
    try {
      setBacktest(await financeApi.backtest("2y"));
    } catch (e: unknown) {
      setError(e instanceof Error ? e.message : "Erreur backtest");
    } finally {
      setBacktesting(false);
    }
  };

  // Ticker unique
  const [tickerInput, setTickerInput] = useState("");
  const [tickerLoading, setTickerLoading] = useState(false);
  const [tickerResult, setTickerResult] = useState<{ ticker: string; score: number; metrics: Record<string, unknown> } | null>(null);

  const pollRef = useRef<ReturnType<typeof setInterval> | null>(null);

  const loadRuns = useCallback(async () => {
    try {
      const [r, p] = await Promise.all([financeApi.buffettRuns(), financeApi.buffettProgress()]);
      setRuns(r); setProgress(p);
    } catch (e: unknown) { setError(e instanceof Error ? e.message : "Erreur"); }
    finally { setLoading(false); }
  }, []);

  useEffect(() => {
    loadRuns();
    return () => { if (pollRef.current) clearInterval(pollRef.current); };
  }, [loadRuns]);

  useEffect(() => {
    // On ne sonde que si une analyse tourne REELLEMENT (verrou backend actif).
    if (progress?.active) {
      pollRef.current = setInterval(async () => {
        const p = await financeApi.buffettProgress().catch(() => null);
        if (p) setProgress(p);
        if (!p?.active) {
          if (pollRef.current) clearInterval(pollRef.current);
          loadRuns();
        }
      }, 3000);
    }
    return () => { if (pollRef.current) clearInterval(pollRef.current); };
  }, [progress?.active, loadRuns]);

  const openRun = async (id: number) => {
    try { setSelected(await financeApi.buffettRun(id)); }
    catch (e: unknown) { setError(e instanceof Error ? e.message : "Erreur"); }
  };

  // Run interrompu (programme ferme en cours d'analyse) -> reprise possible
  const interrupted = progress?.statut === "interrompu"
    || (progress?.statut === "en_cours" && progress?.active === false);

  // En pause : plafond de l'API Yahoo atteint, l'analyse reprend automatiquement
  // (la barre n'est pas figée — #193). On affiche l'heure de reprise estimée.
  const paused = !!progress?.paused_until && progress.paused_until * 1000 > Date.now();
  const resumeAt = paused
    ? new Date(progress!.paused_until! * 1000).toLocaleTimeString("fr-CA", { hour: "2-digit", minute: "2-digit" })
    : null;

  // Bouton 1 — Analyser (ou reprendre) tous les tickers
  const startRun = async () => {
    const msg = interrupted
      ? "Reprendre l'analyse interrompue ? Les tickers déjà analysés ne seront pas refaits."
      : "Lancer une analyse complète de tous les tickers ? Durée : plusieurs heures.";
    if (!confirm(msg)) return;
    setStarting(true); setError(null);
    try {
      await financeApi.buffettStart();
      // Laisser le background task prendre le verrou, puis capter le passage à "actif"
      for (let i = 0; i < 5; i++) {
        await new Promise(r => setTimeout(r, 1000));
        const p = await financeApi.buffettProgress().catch(() => null);
        if (p) { setProgress(p); if (p.active) break; }
      }
      await loadRuns();
    }
    catch (e: unknown) { setError(e instanceof Error ? e.message : "Erreur démarrage"); }
    finally { setStarting(false); }
  };

  // Bouton 2 — Analyser un ticker précis
  const analyzeTicker = async () => {
    const t = tickerInput.trim().toUpperCase();
    if (!t) return;
    setTickerLoading(true); setTickerResult(null); setError(null);
    try {
      const res = await financeApi.buffettAnalyzeTicker(t);
      setTickerResult(res);
    } catch (e: unknown) {
      setError(e instanceof Error ? e.message : `Impossible d'analyser ${t}`);
    } finally { setTickerLoading(false); }
  };

  // Bouton 3 — Créer le portefeuille optimal
  const createPortfolio = async () => {
    if (!confirm(
      "Créer le portefeuille optimal ?\n\n" +
      "• Filtre les actions/ETF éligibles du dernier run\n" +
      "• Re-vérifie chaque score\n" +
      "• Lance l'optimisation Differential Evolution\n\n" +
      "Durée estimée : 5-15 minutes selon la taille de l'univers."
    )) return;
    setCreatingPortfolio(true); setError(null);
    try {
      const r = await financeApi.portfolioCreate();
      alert(`Optimisation lancée en arrière-plan (run #${r.run_id}).\nLe résultat sera visible dans l'onglet Rebalancing.`);
    } catch (e: unknown) {
      setError(e instanceof Error ? e.message : "Erreur création portefeuille");
    } finally { setCreatingPortfolio(false); }
  };

  const exportRun = async (runId: number, runDate: string, fmt: "xlsx" | "csv") => {
    try {
      const path = fmt === "csv" ? `export.csv` : `export`;
      const res = await fetch(`/api/finance/buffett/runs/${runId}/${path}`);
      if (!res.ok) throw new Error("Erreur export");
      const blob = await res.blob();
      const url = URL.createObjectURL(blob);
      const a = document.createElement("a");
      a.href = url; a.download = `buffett_run_${runId}_${runDate}.${fmt}`;
      a.click(); URL.revokeObjectURL(url);
    } catch (e: unknown) {
      setError(e instanceof Error ? e.message : `Erreur export ${fmt}`);
    }
  };

  if (loading) return <Spinner label="Chargement analyses Buffett..." />;

  // Vue détail d'un run
  if (selected) {
    return (
      <div className="space-y-4">
        <div className="flex items-center gap-3 flex-wrap">
          <Button variant="ghost" size="sm" onClick={() => setSelected(null)}>← Retour</Button>
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
        {(() => {
          // S'il existe des allocations : on affiche le portefeuille cible trié
          // par poids décroissant, sans les lignes à 0. Sinon : top scores MOAT.
          const allocated = selected.top_results
            .filter(r => (r.allocation_pct ?? 0) > 0)
            .sort((a, b) => (b.allocation_pct ?? 0) - (a.allocation_pct ?? 0));
          const hasAlloc = allocated.length > 0;
          const displayRows = hasAlloc ? allocated : selected.top_results;
          return (
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
          );
        })()}
      </div>
    );
  }

  return (
    <div className="space-y-4">
      {error && <p className="text-sm text-[var(--destructive)]">⚠ {error}</p>}

      {/* Progression (active) ou reprise (interrompue) */}
      {(progress?.active || interrupted) && (
        <div className={`rounded-[var(--radius-lg)] border p-4 space-y-2 ${
          interrupted ? "border-[var(--warning-muted)] bg-[var(--warning-muted)]" : "border-[var(--border)]"}`}>
          <div className="flex items-center justify-between">
            <span className="text-sm font-medium">
              {interrupted
                ? "⏸ Analyse interrompue"
                : paused
                  ? "⏳ En pause (limite API atteinte)"
                  : "Analyse en cours..."}
            </span>
            <Badge variant={interrupted || paused ? "warning" : "info"}>{fmt(progress?.progress_pct)}%</Badge>
          </div>
          <ProgressBar pct={progress?.progress_pct ?? 0} />
          {progress?.n_done != null && progress?.n_total != null && (
            <p className="text-xs text-[var(--muted-foreground)]">
              {progress.n_done} / {progress.n_total} tickers analysés
            </p>
          )}
          {paused && (
            <p className="text-xs text-[var(--warning-foreground)]">
              Limite de l'API Yahoo atteinte — l'analyse reprend automatiquement
              {resumeAt ? ` vers ${resumeAt}` : " sous peu"}. Aucune action requise.
            </p>
          )}
          {interrupted && (
            <p className="text-xs text-[var(--warning-foreground)]">
              Le programme s'est fermé pendant l'analyse. Cliquez « Reprendre » pour continuer
              sans refaire les tickers déjà analysés.
            </p>
          )}
        </div>
      )}

      {/* ── 3 boutons principaux ── */}
      <div className="rounded-[var(--radius-lg)] border border-[var(--border)] p-4 space-y-4">
        <p className="text-xs font-semibold text-[var(--muted-foreground)] uppercase tracking-wide">Actions</p>

        {/* Bouton 1 */}
        <div className="flex items-start gap-3">
          <div className="flex-1">
            <p className="text-sm font-medium">📋 Analyser tous les tickers</p>
            <p className="text-xs text-[var(--muted-foreground)] mt-0.5">
              Run complet — calcule les scores MOAT pour tous les tickers de tickers.csv (fenêtre 1-2 ans).
            </p>
          </div>
          <Button variant="default" onClick={startRun}
            disabled={starting || progress?.active === true}>
            {starting ? "..." : interrupted ? "Reprendre" : "Lancer"}
          </Button>
        </div>

        <hr className="border-[var(--border)]" />

        {/* Bouton 2 — ticker unique */}
        <div className="flex items-start gap-3">
          <div className="flex-1">
            <p className="text-sm font-medium">🔍 Analyser un ticker précis</p>
            <p className="text-xs text-[var(--muted-foreground)] mt-0.5">
              Résultat immédiat pour un seul ticker (ex : AAPL, MC.PA, CW8.PA).
            </p>
            <div className="flex gap-2 mt-2">
              <input
                className="flex-1 px-3 py-1.5 text-sm rounded-[var(--radius)] border border-[var(--border)]
                           bg-[var(--background)] focus:outline-none focus:ring-1 focus:ring-[var(--ring)]
                           uppercase placeholder:normal-case"
                placeholder="ex : AAPL"
                value={tickerInput}
                onChange={e => setTickerInput(e.target.value.toUpperCase())}
                onKeyDown={e => e.key === "Enter" && analyzeTicker()}
              />
              <Button variant="outline" size="sm" onClick={analyzeTicker}
                disabled={tickerLoading || !tickerInput.trim()}>
                {tickerLoading ? "..." : "Analyser"}
              </Button>
            </div>
            {/* Résultat ticker unique */}
            {tickerResult && (
              <div className="mt-3 p-3 rounded-[var(--radius)] bg-[var(--muted)] text-sm space-y-1">
                <div className="flex items-center justify-between">
                  <span className="font-mono font-semibold">{tickerResult.ticker}</span>
                  <ScoreChip score={tickerResult.score} />
                </div>
                <p className="text-xs text-[var(--muted-foreground)]">
                  {String(tickerResult.metrics?.Nom ?? "—")} · {String(tickerResult.metrics?.Secteur ?? "—")} · {String(tickerResult.metrics?.Pays ?? "—")}
                </p>
                <p className="text-xs">
                  Achat : <strong>{tickerResult.metrics?.Achat ? "✓ OUI" : "✗ NON"}</strong>
                  {tickerResult.metrics?.PER ? ` · PER ${fmt(tickerResult.metrics.PER as number)}` : ""}
                  {tickerResult.metrics?.PEG ? ` · PEG ${fmt(tickerResult.metrics.PEG as number, 2)}` : ""}
                </p>
              </div>
            )}
          </div>
        </div>

        <hr className="border-[var(--border)]" />

        {/* Bouton 3 — portefeuille optimal */}
        <div className="flex items-start gap-3">
          <div className="flex-1">
            <p className="text-sm font-medium">⚡ Créer le portefeuille optimal</p>
            <p className="text-xs text-[var(--muted-foreground)] mt-0.5">
              Filtre les éligibles du dernier run, re-vérifie les scores, puis optimise
              l'allocation par broker avec Differential Evolution.
            </p>
          </div>
          <Button variant="outline" onClick={createPortfolio} disabled={creatingPortfolio}>
            {creatingPortfolio ? "En cours..." : "Optimiser"}
          </Button>
        </div>
      </div>

      {/* Timeline des analyses mensuelles */}
      {!runs.length ? (
        <EmptyState title="Aucune analyse" description="Lancez votre première analyse Buffett." />
      ) : (
        <div>
          <h3 className="text-sm font-semibold mb-3">Historique des analyses</h3>
          <ol className="relative ml-3 border-l border-[var(--border)] space-y-2">
            {runs.map(r => (
              <li key={r.id} className="relative pl-5">
                <span
                  className={`absolute -left-[5px] top-3 h-2.5 w-2.5 rounded-full ring-2 ring-[var(--background)] ${
                    r.statut === "termine" ? "bg-[var(--success)]"
                      : r.statut === "erreur" ? "bg-[var(--destructive)]"
                      : "bg-[var(--ring)]"
                  }`}
                  aria-hidden="true"
                />
                <button onClick={() => openRun(r.id)}
                  className="w-full text-left rounded-[var(--radius-lg)] border border-[var(--border)]
                    p-3 hover:bg-[var(--muted)] transition-colors">
                  <div className="flex items-center justify-between">
                    <span className="text-sm font-medium">{r.run_date}</span>
                    <StatusBadge s={r.statut} />
                  </div>
                  <p className="text-xs text-[var(--muted-foreground)] mt-0.5">
                    {r.n_tickers_analyzed ?? 0} tickers analysés
                    {r.duree_sec ? ` · ${Math.round(r.duree_sec / 60)} min` : ""}
                  </p>
                  {r.resume && <p className="text-xs mt-1 text-[var(--foreground)]">{r.resume}</p>}
                </button>
              </li>
            ))}
          </ol>
        </div>
      )}
    </div>
  );
}
