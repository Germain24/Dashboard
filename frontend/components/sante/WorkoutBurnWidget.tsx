"use client";

/** Calories dépensées en séance ce jour — intégration Entraînement (#67). */

import type { WorkoutBurn } from "@/lib/sante";
import { useWorkoutBurn } from "@/lib/queries/sante";

type Props = {
  /** Calories consommées aujourd'hui (depuis plan.consumed), si connues. */
  consumedCalories?: number | null;
};

function BurnBreakdown({ burn }: { burn: WorkoutBurn }) {
  if (burn.kcal_cardio <= 0) return null;
  return <span className="ml-1 text-xs">(muscu {Math.round(burn.kcal_muscu)} · cardio {Math.round(burn.kcal_cardio)})</span>;
}

function NetCalories({ consumed, total }: { consumed?: number | null; total: number }) {
  if (consumed == null) return null;
  return <span className="ml-auto tabular-nums text-[var(--muted-foreground)]">Apport net : <strong className="text-[var(--foreground)]">{Math.round(consumed - total)}</strong> kcal</span>;
}

function activeBurn(burn?: WorkoutBurn): WorkoutBurn | null {
  if (!burn || !burn.available || burn.total_kcal <= 0) return null;
  return burn;
}

export function WorkoutBurnWidget({ consumedCalories }: Props) {
  const burn = activeBurn(useWorkoutBurn().data);

  if (!burn) return null;

  return (
    <div className="rounded-[var(--radius-lg)] border border-[var(--border)] p-4 flex flex-wrap items-center gap-x-4 gap-y-1 text-sm">
      <span className="font-semibold">🏋️ Séance du jour</span>
      <span className="text-[var(--muted-foreground)] tabular-nums">
        Dépensé : <strong className="text-[var(--foreground)]">{Math.round(burn.total_kcal)}</strong> kcal
        <BurnBreakdown burn={burn} />
      </span>
      <NetCalories consumed={consumedCalories} total={burn.total_kcal} />
    </div>
  );
}
