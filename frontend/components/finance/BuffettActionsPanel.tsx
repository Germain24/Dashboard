"use client";

/** Panneau des 3 actions Buffett : run complet, ticker unique, portefeuille optimal
 *  (extrait de BuffettTab, #532). */

import { useState } from "react";
import { financeApi } from "@/lib/finance";
import { Button } from "@/components/ui/button";
import { fmt, ScoreChip } from "./buffett-ui";

export function BuffettActionsPanel({
  starting, progressActive, interrupted, onStartRun, onError,
}: {
  starting: boolean;
  progressActive: boolean;
  interrupted: boolean;
  onStartRun: () => void;
  onError: (msg: string) => void;
}) {
  // Ticker unique
  const [tickerInput, setTickerInput] = useState("");
  const [tickerLoading, setTickerLoading] = useState(false);
  const [tickerResult, setTickerResult] = useState<{ ticker: string; score: number; metrics: Record<string, unknown> } | null>(null);
  const [creatingPortfolio, setCreatingPortfolio] = useState(false);

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

  const createPortfolio = async () => {
    if (!confirm(
      "Créer le portefeuille optimal ?\n\n" +
      "• Filtre les actions/ETF éligibles du dernier run\n" +
      "• Re-vérifie chaque score\n" +
      "• Lance l'optimisation Differential Evolution\n\n" +
      "Durée estimée : 5-15 minutes selon la taille de l'univers."
    )) return;
    setCreatingPortfolio(true);
    try {
      const r = await financeApi.portfolioCreate();
      alert(`Optimisation lancée en arrière-plan (run #${r.run_id}).\nLe résultat sera visible dans l'onglet Rebalancing.`);
    } catch (e: unknown) {
      onError(e instanceof Error ? e.message : "Erreur création portefeuille");
    } finally { setCreatingPortfolio(false); }
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
            l&apos;allocation par broker avec Differential Evolution.
          </p>
        </div>
        <Button variant="outline" onClick={createPortfolio} disabled={creatingPortfolio}>
          {creatingPortfolio ? "En cours..." : "Optimiser"}
        </Button>
      </div>
    </div>
  );
}
