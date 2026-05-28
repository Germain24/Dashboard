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
    termine: "success", en_cours: "info", erreur: "destructive",
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

export function BuffettTab() {
  const [runs, setRuns] = useState<BuffettRunOut[]>([]);
  const [selected, setSelected] = useState<BuffettRunDetail | null>(null);
  const [progress, setProgress] = useState<BuffettProgress | null>(null);
  const [loading, setLoading] = useState(true);
  const [starting, setStarting] = useState(false);
  const [error, setError] = useState<string | null>(null);
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

  // Poll progress when a run is active
  useEffect(() => {
    if (progress?.statut === "en_cours") {
      pollRef.current = setInterval(async () => {
        const p = await financeApi.buffettProgress().catch(() => null);
        if (p) setProgress(p);
        if (p?.statut !== "en_cours") {
          if (pollRef.current) clearInterval(pollRef.current);
          loadRuns();
        }
      }, 3000);
    }
    return () => { if (pollRef.current) clearInterval(pollRef.current); };
  }, [progress?.statut, loadRuns]);

  const openRun = async (id: number) => {
    try { setSelected(await financeApi.buffettRun(id)); }
    catch (e: unknown) { setError(e instanceof Error ? e.message : "Erreur"); }
  };

  const startRun = async () => {
    if (!confirm("Lancer une analyse Buffett ? Durée estimée : plusieurs heures.")) return;
    setStarting(true);
    try { await financeApi.buffettStart(); await loadRuns(); }
    catch (e: unknown) { setError(e instanceof Error ? e.message : "Erreur démarrage"); }
    finally { setStarting(false); }
  };

  if (loading) return <Spinner label="Chargement analyses Buffett..." />;

  // Detail view
  if (selected) {
    return (
      <div className="space-y-4">
        <div className="flex items-center gap-3">
          <Button variant="ghost" size="sm" onClick={() => setSelected(null)}>← Retour</Button>
          <h2 className="text-base font-semibold">Run du {selected.run.run_date}</h2>
          <StatusBadge s={selected.run.statut} />
        </div>
        {selected.run.resume && (
          <p className="text-sm text-[var(--muted-foreground)]">{selected.run.resume}</p>
        )}
        <div>
          <h3 className="text-sm font-semibold mb-2">Top 50 scores MOAT</h3>
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
                {selected.top_results.map(r => (
                  <tr key={r.id} className="border-b border-[var(--border)]">
                    <td className="py-1 pr-3 font-mono text-xs">{r.ticker}</td>
                    <td className="py-1 pr-3 text-xs">{r.nom ?? "—"}</td>
                    <td className="py-1 pr-3 text-xs text-[var(--muted-foreground)]">{r.secteur ?? "—"}</td>
                    <td className="py-1 pr-3 text-right">
                      <span className={`font-medium ${(r.score ?? 0) >= 80 ? "text-[var(--success)]" : ""}`}>
                        {fmt(r.score)}
                      </span>
                    </td>
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

  return (
    <div className="space-y-4">
      {error && <p className="text-sm text-[var(--destructive)]">⚠ {error}</p>}

      {/* Active run progress */}
      {progress?.statut === "en_cours" && (
        <div className="rounded-[var(--radius-lg)] border border-[var(--border)] p-4 space-y-2">
          <div className="flex items-center justify-between">
            <span className="text-sm font-medium">Analyse en cours...</span>
            <Badge variant="info">{fmt(progress.progress_pct)}%</Badge>
          </div>
          <ProgressBar pct={progress.progress_pct} />
          {progress.n_done != null && progress.n_total != null && (
            <p className="text-xs text-[var(--muted-foreground)]">
              {progress.n_done} / {progress.n_total} tickers analysés
            </p>
          )}
        </div>
      )}

      {/* Launch button */}
      <div className="flex justify-end">
        <Button variant="default" onClick={startRun}
          disabled={starting || progress?.statut === "en_cours"}>
          {starting ? "Démarrage..." : "🚀 Lancer un nouveau run"}
        </Button>
      </div>

      {/* Run list */}
      {!runs.length ? (
        <EmptyState title="Aucune analyse" description="Lancez votre première analyse Buffett." />
      ) : (
        <div className="space-y-2">
          {runs.map(r => (
            <button key={r.id} onClick={() => openRun(r.id)}
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
          ))}
        </div>
      )}
    </div>
  );
}
