"use client";

/** Petits composants partagés de l'onglet Buffett (extraits de BuffettTab, #532). */

import { useEffect, useState } from "react";
import { financeApi } from "@/lib/finance";
import { Badge } from "@/components/ui/badge";

export function fmt(n?: number, dec = 1) {
  return n != null
    ? n.toLocaleString("fr-FR", { minimumFractionDigits: dec, maximumFractionDigits: dec })
    : "—";
}

export function StatusBadge({ s }: { s: string }) {
  const map: Record<string, "success" | "warning" | "destructive" | "info"> = {
    termine: "success",
    en_cours: "info",
    interrompu: "warning",
    erreur: "destructive",
  };
  return <Badge variant={map[s] ?? "outline"}>{s}</Badge>;
}

export function ProgressBar({ pct }: { pct: number }) {
  return (
    <div
      className="w-full h-2 rounded-full bg-[var(--muted)] overflow-hidden"
      role="progressbar"
      aria-label="Progression de l'analyse"
      aria-valuemin={0}
      aria-valuemax={100}
      aria-valuenow={Math.min(100, pct)}
    >
      <div
        className="h-full rounded-full bg-[var(--ring)] bar-fill"
        style={{ width: `${Math.min(100, pct)}%` }}
      />
    </div>
  );
}

export function ScoreChip({ score, isEtf = false }: { score?: number; isEtf?: boolean }) {
  if (isEtf) return <span className="font-medium text-[var(--info)]">ETF</span>;
  if (score == null) return <span className="text-[var(--muted-foreground)]">—</span>;
  const color = score >= 80 ? "text-[var(--success)]" : "";
  const label = fmt(score);
  return <span className={`font-medium ${color}`}>{label}</span>;
}

/** Progression de l'optimisation Differential Evolution (génération / convergence),
 *  partagée entre le bouton manuel "Créer le portefeuille optimal" et le run
 *  automatique une fois le scoring des tickers terminé. */
export type OptProgress = Awaited<ReturnType<typeof financeApi.portfolioProgress>>;

const PHASE_LABEL: Record<OptProgress["phase"], string> = {
  idle: "",
  preparation: "Préparation…",
  initialisation: "Recherche aléatoire d’un portefeuille admissible…",
  optimisation: "Optimisation (Differential Evolution)…",
  finalisation: "Finalisation…",
};

export function DeProgressBar({
  optProgress,
  onStop,
}: {
  optProgress: OptProgress | null;
  onStop?: () => void;
}) {
  // "Arrêt demandé" doit venir du serveur (`stop_requested`, persistant) et pas
  // d'un seul state local : sinon un changement de page démonte le composant,
  // l'état local retombe à false et le bouton réapparaît comme si le clic
  // précédent n'avait jamais eu lieu (l'utilisateur croit devoir recliquer).
  const [clickedLocally, setClickedLocally] = useState(false);
  const stopping = clickedLocally || !!optProgress?.stop_requested;

  useEffect(() => {
    // Réinitialise l'état local lorsque l'événement de fin arrive.
    if (!optProgress?.active) setClickedLocally(false);
  }, [optProgress?.active]);

  if (!optProgress) return null;

  // Compatibilité avec un backend déjà lancé avant l'ajout de phase_done /
  // phase_total : le message historique contient néanmoins "750/2920".
  const messageProgress = optProgress.message.match(/(\d+)\s*\/\s*(\d+)/);
  const messageDone = Number(messageProgress?.[1] ?? 0);
  const messageTotal = Number(messageProgress?.[2] ?? 0);
  const structuredProgress = (optProgress.phase_total ?? 0) > 0;
  const messageIsMeasurable = !structuredProgress && messageTotal > 0;
  const measuredProgress = structuredProgress
    ? optProgress.progress_pct
    : messageIsMeasurable
      ? (messageDone / messageTotal) * 100
      : null;
  const displayedProgress = Math.min(
    100,
    Math.max(0, measuredProgress ?? optProgress.progress_pct),
  );

  const handleStop = () => {
    if (!onStop || stopping) return;
    setClickedLocally(true);
    onStop();
  };

  return (
    <div className="space-y-1.5">
      <div className="flex items-center justify-between text-xs">
        <span className="text-[var(--muted-foreground)]">
          {optProgress.active
            ? // Le message serveur est plus précis que le libellé de phase :
              // "Téléchargement des cours… 850/2898 titres", "Déduplication…"
              optProgress.message || PHASE_LABEL[optProgress.phase] || "En cours…"
            : optProgress.message ||
              (optProgress.status === "stopped" ? "Arrêté par l’utilisateur" : "Terminé")}
          {optProgress.active && optProgress.phase === "optimisation"
            ? ` · seed ${optProgress.seed_num || 1}${
                optProgress.iteration > 0 ? ` · génération ${optProgress.iteration}` : ""
              }${
                optProgress.seed_score != null
                  ? ` · meilleur seed ${fmt(optProgress.seed_score, 4)}`
                  : ""
              }${
                optProgress.best_score != null
                  ? ` · meilleur global ${fmt(optProgress.best_score, 4)}`
                  : ""
              }`
            : ""}
        </span>
        <div className="flex items-center gap-2">
          {optProgress.active && onStop && (
            <button
              type="button"
              onClick={handleStop}
              disabled={stopping}
              className="text-[var(--destructive)] hover:underline disabled:opacity-50 disabled:no-underline"
            >
              {stopping ? "Arrêt demandé…" : "⏹ Arrêter"}
            </button>
          )}
          {optProgress.active &&
            (optProgress.phase === "initialisation" ||
              optProgress.phase === "optimisation" ||
              structuredProgress ||
              messageIsMeasurable) && (
              <span className="font-mono text-[var(--muted-foreground)]">
                {fmt(displayedProgress, 0)}%
              </span>
            )}
        </div>
      </div>
      <div
        className="h-1.5 w-full overflow-hidden rounded-full bg-[var(--muted)]"
        role="progressbar"
        aria-label="Progression de l'optimisation"
        aria-valuemin={0}
        aria-valuemax={100}
        aria-valuenow={displayedProgress}
      >
        <div
          className={`h-full rounded-full bg-[var(--primary)] transition-[width] duration-500 ${
            optProgress.active && optProgress.phase !== "optimisation" && measuredProgress == null
              ? "animate-pulse"
              : ""
          }`}
          style={{
            width: !optProgress.active
              ? "100%"
              : optProgress.phase === "optimisation" ||
                  optProgress.phase === "initialisation" ||
                  structuredProgress ||
                  messageIsMeasurable
                ? `${Math.max(displayedProgress, 2)}%`
                : "100%",
          }}
        />
      </div>
      {optProgress.active && optProgress.last_activity_at != null && (
        <p
          className={`text-[11px] ${
            optProgress.stalled
              ? "text-[var(--warning-foreground)]"
              : "text-[var(--muted-foreground)]"
          }`}
          role={optProgress.stalled ? "status" : undefined}
        >
          {optProgress.stalled
            ? "Aucune nouvelle activité depuis plus de 2 minutes — le calcul est peut-être ralenti."
            : `Dernière activité il y a ${Math.max(0, Math.round(optProgress.seconds_since_activity ?? 0))} s.`}
        </p>
      )}
    </div>
  );
}
