"use client";

/** Widget d'hydratation : suivi de l'eau du jour + ajout rapide (#66). */

import { useAddWater, useWaterToday } from "@/lib/queries/sante";

export function WaterWidget() {
  const state = useWaterToday().data ?? null;
  const addMutation = useAddWater();

  const add = (ml: number) => addMutation.mutate(ml);

  if (!state) return null;
  const pct = Math.min(100, state.pct);

  return (
    <div className="rounded-[var(--radius-lg)] border border-[var(--border)] p-4 space-y-2">
      <div className="flex items-center justify-between">
        <h3 className="text-sm font-semibold">💧 Hydratation</h3>
        <span className="text-xs text-[var(--muted-foreground)] tabular-nums">
          {state.eau_ml} / {state.cible_ml} ml
        </span>
      </div>
      <div className="h-2 rounded-full bg-[var(--muted)] overflow-hidden">
        <div className="h-full rounded-full bg-[var(--ring)] transition-all" style={{ width: `${pct}%` }} />
      </div>
      <div className="flex gap-2">
        {[250, 500, 750].map((ml) => (
          <button
            key={ml}
            onClick={() => add(ml)}
            className="rounded-md border border-[var(--border)] px-2.5 py-1 text-xs hover:bg-[var(--muted)]"
          >
            +{ml} ml
          </button>
        ))}
        {state.pct >= 100 && <span className="ml-auto text-xs text-[var(--success)]">Objectif atteint ✓</span>}
      </div>
    </div>
  );
}
