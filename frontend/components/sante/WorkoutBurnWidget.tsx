"use client";

/** Calories dépensées en séance ce jour — intégration Entraînement (#67). */

import type { WorkoutBurn } from "@/lib/sante";
import { useWorkoutBurn } from "@/lib/queries/sante";

type Props = {
  /** Calories consommées aujourd'hui (depuis plan.consumed), si connues. */
  consumedCalories?: number | null;
};

export function WorkoutBurnWidget({ consumedCalories }: Props) {
  const burn: WorkoutBurn | null = useWorkoutBurn().data ?? null;

  if (!burn || !burn.available || burn.total_kcal <= 0) return null;

  const net =
    consumedCalories != null ? Math.round(consumedCalories - burn.total_kcal) : null;

  return (
    <div className="rounded-[var(--radius-lg)] border border-[var(--border)] p-4 flex flex-wrap items-center gap-x-4 gap-y-1 text-sm">
      <span className="font-semibold">🏋️ Séance du jour</span>
      <span className="text-[var(--muted-foreground)] tabular-nums">
        Dépensé : <strong className="text-[var(--foreground)]">{Math.round(burn.total_kcal)}</strong> kcal
        {burn.kcal_cardio > 0 && (
          <span className="ml-1 text-xs">
            (muscu {Math.round(burn.kcal_muscu)} · cardio {Math.round(burn.kcal_cardio)})
          </span>
        )}
      </span>
      {net != null && (
        <span className="ml-auto text-[var(--muted-foreground)] tabular-nums">
          Apport net : <strong className="text-[var(--foreground)]">{net}</strong> kcal
        </span>
      )}
    </div>
  );
}
