"use client";

/** Petits composants partagés de l'onglet Buffett (extraits de BuffettTab, #532). */

import { financeApi } from "@/lib/finance";
import { Badge } from "@/components/ui/badge";

export function fmt(n?: number, dec = 1) {
  return n != null ? n.toLocaleString("fr-FR", { minimumFractionDigits: dec, maximumFractionDigits: dec }) : "—";
}

export function StatusBadge({ s }: { s: string }) {
  const map: Record<string, "success" | "warning" | "destructive" | "info"> = {
    termine: "success", en_cours: "info", interrompu: "warning", erreur: "destructive",
  };
  return <Badge variant={map[s] ?? "outline"}>{s}</Badge>;
}

export function ProgressBar({ pct }: { pct: number }) {
  return (
    <div className="w-full h-2 rounded-full bg-[var(--muted)] overflow-hidden">
      <div className="h-full rounded-full bg-[var(--ring)] bar-fill"
        style={{ width: `${Math.min(100, pct)}%` }} />
    </div>
  );
}

export function ScoreChip({ score }: { score?: number }) {
  if (score == null) return <span className="text-[var(--muted-foreground)]">—</span>;
  const color = score >= 200
    ? "text-[var(--info)]"
    : score >= 80 ? "text-[var(--success)]" : "";
  const label = score >= 200 ? "ETF" : fmt(score);
  return <span className={`font-medium ${color}`}>{label}</span>;
}

/** Progression de l'optimisation Differential Evolution (génération / convergence),
 *  partagée entre le bouton manuel "Créer le portefeuille optimal" et le run
 *  automatique une fois le scoring des tickers terminé. */
export type OptProgress = Awaited<ReturnType<typeof financeApi.portfolioProgress>>;

const PHASE_LABEL: Record<OptProgress["phase"], string> = {
  idle: "",
  preparation: "Préparation…",
  optimisation: "Optimisation (Differential Evolution)…",
  finalisation: "Finalisation…",
};

export function DeProgressBar({ optProgress }: { optProgress: OptProgress | null }) {
  if (!optProgress) return null;
  return (
    <div className="space-y-1.5">
      <div className="flex items-center justify-between text-xs">
        <span className="text-[var(--muted-foreground)]">
          {optProgress.active
            ? (PHASE_LABEL[optProgress.phase] || "En cours…")
            : (optProgress.message || "Terminé")}
          {optProgress.active && optProgress.phase === "optimisation" && optProgress.iteration > 0
            ? ` · génération ${optProgress.iteration}` : ""}
        </span>
        {optProgress.active && optProgress.phase === "optimisation" && (
          <span className="font-mono text-[var(--muted-foreground)]">
            {fmt(optProgress.progress_pct, 0)}%
          </span>
        )}
      </div>
      <div className="h-1.5 w-full overflow-hidden rounded-full bg-[var(--muted)]">
        <div
          className={`h-full rounded-full bg-[var(--primary)] transition-[width] duration-500 ${
            optProgress.active && optProgress.phase !== "optimisation" ? "animate-pulse" : ""
          }`}
          style={{
            width: !optProgress.active
              ? "100%"
              : optProgress.phase === "optimisation"
                ? `${Math.max(optProgress.progress_pct, 2)}%`
                : "100%",
          }}
        />
      </div>
    </div>
  );
}
