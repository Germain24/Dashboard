"use client";

/** Évolution EN DIRECT du meilleur score d'optimisation (STARR pénalisé)
 *  trouvé par le Differential Evolution, pendant qu'il tourne -- pas
 *  seulement affiché une fois terminé. Pas d'historique côté serveur : on
 *  accumule les valeurs polled via `optProgress` (déjà rafraîchi toutes les
 *  60s par le parent), persisté en sessionStorage par run_id pour survivre à
 *  un refresh de page / remount tant que le DE tourne toujours côté serveur. */

import { useEffect, useRef, useState } from "react";
import { fmt, type OptProgress } from "./buffett-ui";

const STORAGE_PREFIX = "buffett-de-history-";

function loadHistory(runId: number): number[] {
  try {
    const raw = sessionStorage.getItem(STORAGE_PREFIX + runId);
    return raw ? (JSON.parse(raw) as number[]) : [];
  } catch {
    return [];
  }
}

function saveHistory(runId: number, history: number[]): void {
  try {
    sessionStorage.setItem(STORAGE_PREFIX + runId, JSON.stringify(history));
  } catch {
    // sessionStorage indisponible (navigation privée, quota) -- best-effort.
  }
}

export function DeStarrChart({ optProgress }: { optProgress: OptProgress | null }) {
  const [history, setHistory] = useState<number[]>([]);
  const lastRunRef = useRef<number | null>(null);

  useEffect(() => {
    if (!optProgress?.active || optProgress.best_score == null || optProgress.run_id == null) return;
    const runId = optProgress.run_id;
    const score = optProgress.best_score;
    if (lastRunRef.current !== runId) {
      lastRunRef.current = runId;
      const restored = loadHistory(runId);
      const next = restored.length && restored[restored.length - 1] === score
        ? restored
        : [...restored, score];
      setHistory(next);
      saveHistory(runId, next);
      return;
    }
    setHistory((h) => {
      if (h[h.length - 1] === score) return h;
      const next = [...h, score];
      saveHistory(runId, next);
      return next;
    });
  }, [optProgress?.best_score, optProgress?.active, optProgress?.run_id]);

  if (history.length < 2) return null;

  const W = 100, H = 28;
  const min = Math.min(...history);
  const max = Math.max(...history);
  const span = max - min || 1;
  const coords = history
    .map((v, i) => `${((i / (history.length - 1)) * W).toFixed(2)},${(H - ((v - min) / span) * H).toFixed(2)}`)
    .join(" ");

  return (
    <div className="rounded-[var(--radius-lg)] border border-[var(--border)] p-4">
      <div className="mb-2 flex items-baseline justify-between gap-3">
        <p className="text-xs font-semibold text-[var(--muted-foreground)]">
          Meilleur score d&apos;optimisation (STARR pénalisé) — en direct
        </p>
        <span className="shrink-0 text-xs tabular-nums text-[var(--muted-foreground)]">
          {fmt(history[history.length - 1], 4)}
        </span>
      </div>
      <svg viewBox={`0 0 ${W} ${H}`} preserveAspectRatio="none" className="h-20 w-full"
           role="img" aria-label="Évolution du meilleur score d'optimisation en direct">
        <polyline points={coords} fill="none" stroke="var(--success)" strokeWidth={0.6}
                  vectorEffect="non-scaling-stroke" />
      </svg>
      <div className="mt-1 flex justify-between text-[10px] tabular-nums text-[var(--muted-foreground)]">
        <span>min {fmt(min, 4)}</span>
        <span>max {fmt(max, 4)}</span>
      </div>
    </div>
  );
}
