"use client";

/** Onglet Buffett — orchestrateur : runs, progression, timeline (#532 :
 *  vue détail et panneau d'actions extraits). */

import { useEffect, useState, useCallback, useRef } from "react";
import { Trash2 } from "lucide-react";
import {
  financeApi, type BuffettRunOut, type BuffettRunDetail, type BuffettProgress,
} from "@/lib/finance";
import { Spinner } from "@/components/ui/spinner";
import { EmptyState } from "@/components/ui/empty-state";
import { Badge } from "@/components/ui/badge";
import { fmt, ProgressBar, StatusBadge } from "./buffett-ui";
import { BuffettRunDetailView } from "./BuffettRunDetailView";
import { BuffettActionsPanel } from "./BuffettActionsPanel";

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

  // Supprimer une analyse (ex. run bloqué/interrompu) + ses résultats.
  const deleteRun = async (id: number) => {
    if (!confirm("Supprimer cette analyse et ses résultats ?")) return;
    try {
      await financeApi.buffettDeleteRun(id);
      if (selected?.run.id === id) setSelected(null);
      setProgress(null);
      await loadRuns();
    } catch (e: unknown) { setError(e instanceof Error ? e.message : "Erreur suppression"); }
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

  if (loading) return <Spinner label="Chargement analyses Buffett..." />;

  // Vue détail d'un run
  if (selected) {
    return (
      <BuffettRunDetailView
        selected={selected}
        onBack={() => setSelected(null)}
        onError={setError}
      />
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
              Limite de l&apos;API Yahoo atteinte — l&apos;analyse reprend automatiquement
              {resumeAt ? ` vers ${resumeAt}` : " sous peu"}. Aucune action requise.
            </p>
          )}
          {interrupted && (
            <p className="text-xs text-[var(--warning-foreground)]">
              Le programme s&apos;est fermé pendant l&apos;analyse. Cliquez « Reprendre » pour continuer
              sans refaire les tickers déjà analysés.
            </p>
          )}
        </div>
      )}

      <BuffettActionsPanel
        starting={starting}
        progressActive={progress?.active === true}
        interrupted={interrupted}
        onStartRun={startRun}
        onError={setError}
      />

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
                <div className="flex items-start gap-2">
                  <button onClick={() => openRun(r.id)}
                    className="flex-1 text-left rounded-[var(--radius-lg)] border border-[var(--border)]
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
                  <button onClick={() => deleteRun(r.id)} aria-label="Supprimer l'analyse"
                    className="mt-1 rounded-md p-2 text-[var(--muted-foreground)] hover:bg-[var(--muted)] hover:text-[var(--destructive)] transition-colors">
                    <Trash2 size={14} aria-hidden="true" />
                  </button>
                </div>
              </li>
            ))}
          </ol>
        </div>
      )}
    </div>
  );
}
