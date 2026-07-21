"use client";

/** Évolution en direct du meilleur score STARR pénalisé.
 *
 * Le backend conserve uniquement les améliorations strictes. Le frontend les
 * garde en session pour survivre à un remount sans répéter les plateaux.
 */

import { useEffect, useRef, useState } from "react";
import { fmt, type OptProgress } from "./buffett-ui";

type ScorePoint = NonNullable<OptProgress["score_history"]>[number];

const STORAGE_PREFIX = "buffett-de-history-";
const STORAGE_LIMIT = 20_000;

function isScorePoint(value: unknown): value is ScorePoint {
  if (!value || typeof value !== "object") return false;
  const point = value as Record<string, unknown>;
  return typeof point.iteration === "number"
    && typeof point.seed_num === "number"
    && typeof point.seed_iteration === "number"
    && typeof point.score === "number"
    && point.score > 0;
}

function loadHistory(runId: number): ScorePoint[] {
  try {
    const raw = sessionStorage.getItem(STORAGE_PREFIX + runId);
    if (!raw) return [];
    const parsed: unknown = JSON.parse(raw);
    if (!Array.isArray(parsed)) return [];
    return parsed.filter(isScorePoint);
  } catch {
    return [];
  }
}

function saveHistory(runId: number, history: ScorePoint[]): void {
  try {
    sessionStorage.setItem(
      STORAGE_PREFIX + runId,
      JSON.stringify(history.slice(-STORAGE_LIMIT)),
    );
  } catch {
    // sessionStorage indisponible ou quota dépassé: le graphe courant reste valide.
  }
}

export function DeStarrChart({ optProgress }: { optProgress: OptProgress | null }) {
  const [history, setHistory] = useState<ScorePoint[]>([]);
  const lastRunRef = useRef<number | null>(null);

  useEffect(() => {
    if (!optProgress?.active || optProgress.run_id == null) return;
    const runId = optProgress.run_id;
    const runChanged = lastRunRef.current !== runId;
    if (runChanged) lastRunRef.current = runId;

    const incoming = (optProgress.score_history ?? []).filter((point) => point.score > 0);
    setHistory((current) => {
      const base = runChanged ? loadHistory(runId) : current;
      const merged = new Map(base.map((point) => [point.iteration, point]));
      for (const point of incoming) merged.set(point.iteration, point);
      const next = [...merged.values()].sort((a, b) => a.iteration - b.iteration);
      saveHistory(runId, next);
      return next;
    });
  }, [
    optProgress?.active,
    optProgress?.best_score,
    optProgress?.iteration,
    optProgress?.phase,
    optProgress?.run_id,
    optProgress?.score_history,
    optProgress?.seed_num,
    optProgress?.total_iterations,
  ]);

  if (history.length < 2) return null;

  const W = 100;
  const H = 28;
  let min = Number.POSITIVE_INFINITY;
  let max = Number.NEGATIVE_INFINITY;
  for (const point of history) {
    min = Math.min(min, point.score);
    max = Math.max(max, point.score);
  }
  const span = max - min || 1;
  const coords = history
    .map((point, index) => {
      const x = (index / (history.length - 1)) * W;
      const y = H - ((point.score - min) / span) * H;
      return `${x.toFixed(2)},${y.toFixed(2)}`;
    })
    .join(" ");
  const latest = history[history.length - 1];
  const latestY = H - ((latest.score - min) / span) * H;

  return (
    <div className="rounded-[var(--radius-lg)] border border-[var(--border)] p-4">
      <div className="mb-2 flex items-baseline justify-between gap-3">
        <p className="text-xs font-semibold text-[var(--muted-foreground)]">
          Meilleur score d&apos;optimisation, un point par amélioration
        </p>
        <span className="shrink-0 text-xs tabular-nums text-[var(--muted-foreground)]">
          {fmt(latest.score, 4)}
        </span>
      </div>
      <svg
        viewBox={`0 0 ${W} ${H}`}
        preserveAspectRatio="none"
        className="h-20 w-full"
        role="img"
        aria-label={`Évolution du score sur ${history.length} générations`}
      >
        <polyline
          points={coords}
          fill="none"
          stroke="var(--success)"
          strokeWidth={0.6}
          vectorEffect="non-scaling-stroke"
        />
        <circle cx={W} cy={latestY} r={1.1} fill="var(--success)" />
      </svg>
      <div className="mt-1 flex justify-between text-[10px] tabular-nums text-[var(--muted-foreground)]">
        <span>{history.length.toLocaleString("fr-CA")} itérations</span>
        <span>min {fmt(min, 4)} · max {fmt(max, 4)}</span>
      </div>
    </div>
  );
}
