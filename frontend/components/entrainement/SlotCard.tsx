"use client";

/** Carte de slot d'exercice + formulaire d'ajout de série (extraits d'AujourdhuiTab, #522). */

import { useState } from "react";
import type { Seance, SlotToday } from "@/lib/entrainement";
import { useAddSet } from "@/lib/queries/entrainement";
import { Button } from "@/components/ui/button";

export function SlotCard({
  slot, seance, onRest,
}: {
  slot: SlotToday;
  seance: Seance | null;
  onRest: () => void;
}) {
  const setsForSlot = seance?.sets.filter((s) => s.exercice_id === slot.exercice_id) ?? [];
  const setsDone = setsForSlot.length;
  // Cible de la semaine si un mésocycle tourne (#110), sinon la cible de base.
  const setsTarget = slot.sets_target_semaine ?? slot.sets_target ?? null;
  const periodised = slot.sets_target_semaine != null && slot.sets_target_semaine !== slot.sets_target;
  const progress = setsTarget && setsTarget > 0
    ? Math.min(100, Math.round((setsDone / setsTarget) * 100))
    : 0;
  const noExercice = slot.exercice_id === null;
  const isWarmup = /warm-?up/i.test(slot.label);

  return (
    <div className="rounded-xl border border-[var(--border)] bg-[var(--card)] p-3 card-hover">
      <div className="flex flex-wrap items-baseline gap-2 text-sm">
        <span className="font-medium">{slot.label}</span>
        {setsTarget && (
          <span className="text-xs text-[var(--muted-foreground)]">
            cible {setsTarget}×{slot.reps_target ?? "?"}
            {periodised && <span className="text-[var(--ring)]"> · sem.</span>}
          </span>
        )}
        {slot.poids_suggere_kg !== null && slot.poids_suggere_kg > 0 && (
          <span className="text-xs text-[var(--muted-foreground)]">
            · sugg. <strong>{slot.poids_suggere_kg} kg</strong>
          </span>
        )}
        {slot.poids_suggere_kg === 0 && (
          <span className="text-xs text-[var(--muted-foreground)]">· poids du corps</span>
        )}
        {slot.note && <span className="text-xs italic opacity-60">{slot.note}</span>}
        {setsTarget && (
          <span className="ml-auto text-xs font-medium" style={{ color: "var(--ring)" }}>
            {setsDone}/{setsTarget}
          </span>
        )}
      </div>

      {slot.derniere_fois && (
        <p className="mt-1 text-xs text-[var(--muted-foreground)]">
          ↩︎ Dernière fois (
          {new Date(slot.derniere_fois.date + "T12:00:00").toLocaleDateString("fr-CA", {
            day: "numeric", month: "short",
          })}
          ) : <span className="text-[var(--foreground)]">{slot.derniere_fois.resume}</span>
        </p>
      )}

      {setsTarget && (
        <div className="mt-1 h-1 rounded-full bg-[var(--muted)] overflow-hidden">
          <div
            className="h-full bg-[var(--ring)] transition-all"
            style={{ width: `${progress}%` }}
          />
        </div>
      )}

      {setsForSlot.length > 0 && (
        <ul className="mt-2 text-xs space-y-0.5 text-[var(--muted-foreground)]">
          {setsForSlot.map((s, i) => (
            <li key={s.id}>
              Série {i + 1} : <strong className="text-[var(--foreground)]">{s.reps}</strong> reps
              × <strong className="text-[var(--foreground)]">{s.poids_kg}</strong> kg
              {s.rpe ? ` · RPE ${s.rpe}` : ""}
            </li>
          ))}
        </ul>
      )}

      {seance && !noExercice && !isWarmup && (
        <AddSetForm
          seanceId={seance.id}
          exerciceId={slot.exercice_id!}
          suggested={slot.poids_suggere_kg ?? 0}
          repsHint={typeof slot.reps_target === "number" ? slot.reps_target : 8}
          onRest={onRest}
        />
      )}

      {seance && noExercice && !isWarmup && (
        <p className="mt-2 text-xs text-[var(--warning)]">
          ⚠ Exercice « {slot.label} » introuvable dans le catalogue.
        </p>
      )}
    </div>
  );
}

function AddSetForm({
  seanceId, exerciceId, suggested, repsHint, onRest,
}: {
  seanceId: number;
  exerciceId: number;
  suggested: number;
  repsHint: number;
  onRest: () => void;
}) {
  const [reps, setReps] = useState<string>(String(repsHint));
  const [poids, setPoids] = useState<string>(suggested > 0 ? String(suggested) : "");
  const [rpe, setRpe] = useState<string>("");
  const addSetMutation = useAddSet();

  const submit = () => {
    if (!reps) return;
    addSetMutation.mutate(
      {
        seanceId,
        set: {
          exercice_id: exerciceId,
          reps: parseInt(reps, 10),
          poids_kg: poids ? parseFloat(poids) : 0,
          rpe: rpe ? parseFloat(rpe) : null,
        },
      },
      { onSuccess: onRest }, // démarre le minuteur de repos (#106)
    );
  };

  const inputCls = "mt-0.5 rounded-[var(--radius-sm)] border border-[var(--border)] bg-transparent px-1.5 py-0.5 text-xs focus:border-[var(--ring)] focus:outline-none";

  return (
    <div className="mt-2 flex flex-wrap items-end gap-2 text-xs">
      <label className="flex flex-col">
        Reps
        <input type="number" value={reps} onChange={(e) => setReps(e.target.value)} className={`${inputCls} w-16`} />
      </label>
      <label className="flex flex-col">
        Poids (kg)
        <input type="number" step="0.5" value={poids} onChange={(e) => setPoids(e.target.value)} className={`${inputCls} w-20`} />
      </label>
      <label className="flex flex-col">
        RPE
        <input type="number" step="0.5" min="6" max="10" value={rpe} onChange={(e) => setRpe(e.target.value)} className={`${inputCls} w-14`} />
      </label>
      <Button size="sm" onClick={submit} disabled={addSetMutation.isPending}>
        + Série
      </Button>
    </div>
  );
}
