"use client";

/** Panneau des 3 actions Buffett : run complet, ticker unique, portefeuille optimal
 *  (extrait de BuffettTab, #532). */

import { useState } from "react";
import { financeApi } from "@/lib/finance";
import { Button } from "@/components/ui/button";
import { fmt, ScoreChip, DeProgressBar, type OptProgress } from "./buffett-ui";
import { DeStarrChart } from "./DeStarrChart";

function metricText(value: unknown): string {
  return typeof value === "string" || typeof value === "number"
    ? String(value)
    : "—";
}

export function BuffettActionsPanel({
  starting, progressActive, interrupted, optProgress, onStartRun,
  onOptimizationStarted, onStopOptimization, onError,
}: {
  starting: boolean;
  progressActive: boolean;
  interrupted: boolean;
  optProgress: OptProgress | null;
  onStartRun: () => void;
  onOptimizationStarted: (progress: OptProgress) => void;
  onStopOptimization: () => void;
  onError: (msg: string) => void;
}) {
  // Ticker unique
  const [tickerInput, setTickerInput] = useState("");
  const [tickerLoading, setTickerLoading] = useState(false);
  const [tickerResult, setTickerResult] = useState<{ ticker: string; score: number; metrics: Record<string, unknown> } | null>(null);
  const [creatingPortfolio, setCreatingPortfolio] = useState<"all" | "actions" | null>(null);

  const analyzeTicker = async () => {
    const t = tickerInput.trim().toUpperCase();
    if (!t) return;
    setTickerLoading(true); setTickerResult(null);
    try {
      const res = await financeApi.buffettAnalyzeTicker(t);
      setTickerResult(res);
    } catch (e: unknown) {
      onError(e instanceof Error ? e.message : `Impossible d'analyser ${t}`);
    } finally { setTickerLoading(false); }
  };

  const createPortfolio = async (includeEtfs: boolean) => {
    if (!confirm(
      `Créer le portefeuille optimal ${includeEtfs ? "" : "sans ETF "}?\n\n` +
      `• Filtre les ${includeEtfs ? "actions/ETF" : "actions uniquement"} éligibles du dernier run\n` +
      "• Re-vérifie chaque score\n" +
      "• Lance l'optimisation Differential Evolution\n\n" +
      "Durée estimée : 5-15 minutes selon la taille de l'univers."
    )) return;
    setCreatingPortfolio(includeEtfs ? "all" : "actions");
    try {
      const response = await financeApi.portfolioCreate(80, includeEtfs);
      onOptimizationStarted({ active: true, status: "running", termination_reason: null,
        phase: "preparation", seed_num: 0, completed_seeds: 0, iteration: 0,
        total_iterations: 0, initialization_attempt: 0, initialization_max: 0,
        convergence: 0, progress_pct: 0, message: "Démarrage…", run_id: response.run_id,
        optimization_id: null, optimization_started_at: null, stop_requested: false,
        best_score: null });
    } catch (e: unknown) {
      onError(e instanceof Error ? e.message : "Erreur création portefeuille");
    } finally { setCreatingPortfolio(null); }
  };

  return (
    <div className="rounded-[var(--radius-lg)] border border-[var(--border)] p-4 space-y-4">
      <p className="text-xs font-semibold text-[var(--muted-foreground)]">Actions</p>

      {/* Bouton 1 */}
      <div className="flex items-start gap-3">
        <div className="flex-1">
          <p className="text-sm font-medium">📋 Analyser tous les tickers</p>
          <p className="text-xs text-[var(--muted-foreground)] mt-0.5">
            Run complet — calcule les scores MOAT pour tous les tickers de tickers.csv (fenêtre 1-2 ans).
          </p>
        </div>
        <Button variant="default" onClick={onStartRun}
          disabled={starting || progressActive}>
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
              onKeyDown={e => { if (e.key === "Enter") void analyzeTicker(); }}
            />
            <Button variant="outline" size="sm" onClick={() => { void analyzeTicker(); }}
              disabled={tickerLoading || !tickerInput.trim()}>
              {tickerLoading ? "..." : "Analyser"}
            </Button>
          </div>
          {/* Résultat ticker unique */}
          {tickerResult && (
            <div className="mt-3 p-3 rounded-[var(--radius)] bg-[var(--muted)] text-sm space-y-1">
              <div className="flex items-center justify-between">
                <span className="font-mono font-semibold">{tickerResult.ticker}</span>
                <ScoreChip score={tickerResult.score} isEtf={tickerResult.metrics?.Secteur === "ETF"} />
              </div>
              <p className="text-xs text-[var(--muted-foreground)]">
                {metricText(tickerResult.metrics?.Nom)} · {metricText(tickerResult.metrics?.Secteur)} · {metricText(tickerResult.metrics?.Pays)}
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
            l&apos;allocation par broker avec Differential Evolution.
          </p>
          <p className="text-xs text-[var(--muted-foreground)] mt-1">
            « Sans ETF » conserve le même objectif STARR et les mêmes contraintes, en excluant uniquement les ETF.
          </p>
        </div>
        <div className="flex flex-wrap justify-end gap-2">
          <Button variant="outline" onClick={() => { void createPortfolio(true); }}
            disabled={!!creatingPortfolio || !!optProgress?.active}>
            {creatingPortfolio === "all" || optProgress?.active ? "En cours..." : "Optimiser"}
          </Button>
          <Button variant="outline" onClick={() => { void createPortfolio(false); }}
            disabled={!!creatingPortfolio || !!optProgress?.active}>
            {creatingPortfolio === "actions" ? "En cours..." : "Sans ETF"}
          </Button>
        </div>
      </div>

      {/* Barre de progression de l'optimisation DE */}
      {!progressActive && (
        <DeProgressBar optProgress={optProgress} onStop={onStopOptimization} />
      )}
      {!progressActive && optProgress?.active && <DeStarrChart optProgress={optProgress} />}
    </div>
  );
}
