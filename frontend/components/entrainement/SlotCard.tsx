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
  const setsForSlot = setsForExercise(seance, slot.exercice_id);
  const setsDone = setsForSlot.length;
  // Cible de la semaine si un mésocycle tourne (#110), sinon la cible de base.
  const setsTarget = slotTarget(slot);
  const periodised = isPeriodised(slot);
  const progress = targetProgress(setsDone, setsTarget);
  const noExercice = slot.exercice_id === null;
  const isWarmup = /warm-?up/i.test(slot.label);

  return (
    <div className="rounded-xl border border-[var(--border)] bg-[var(--card)] p-3 card-hover">
      <SlotHeading slot={slot} setsTarget={setsTarget} periodised={periodised} setsDone={setsDone} />
      <PreviousPerformance slot={slot} />
      <SlotProgress target={setsTarget} progress={progress} />
      <CompletedSets sets={setsForSlot} />
      <SlotActions slot={slot} seance={seance} noExercice={noExercice} isWarmup={isWarmup} onRest={onRest} />
    </div>
  );
}

function setsForExercise(seance: Seance | null, exerciceId: number | null) {
  if (!seance) return [];
  return seance.sets.filter((set) => set.exercice_id === exerciceId);
}

function slotTarget(slot: SlotToday): number | null {
  return slot.sets_target_semaine ?? slot.sets_target ?? null;
}

function isPeriodised(slot: SlotToday): boolean {
  return slot.sets_target_semaine != null && slot.sets_target_semaine !== slot.sets_target;
}

function targetProgress(done: number, target: number | null): number {
  if (!target || target <= 0) return 0;
  return Math.min(100, Math.round((done / target) * 100));
}

function SlotHeading({ slot, setsTarget, periodised, setsDone }: { slot: SlotToday; setsTarget: number | null; periodised: boolean; setsDone: number }) {
  return (
    <div className="flex flex-wrap items-baseline gap-2 text-sm">
      <span className="font-medium">{slot.label}</span>
      <SlotTarget slot={slot} target={setsTarget} periodised={periodised} />
      <SuggestedWeight value={slot.poids_suggere_kg} />
      {slot.note && <span className="text-xs italic opacity-60">{slot.note}</span>}
      {setsTarget && <span className="ml-auto text-xs font-medium" style={{ color: "var(--ring)" }}>{setsDone}/{setsTarget}</span>}
    </div>
  );
}

function SlotTarget({ slot, target, periodised }: { slot: SlotToday; target: number | null; periodised: boolean }) {
  if (!target) return null;
  return <span className="text-xs text-[var(--muted-foreground)]">cible {target}×{slot.reps_target ?? "?"}{periodised && <span className="text-[var(--ring)]"> · sem.</span>}</span>;
}

function SuggestedWeight({ value }: { value: number | null }) {
  if (value === null || value === undefined) return null;
  if (value === 0) return <span className="text-xs text-[var(--muted-foreground)]">· poids du corps</span>;
  return <span className="text-xs text-[var(--muted-foreground)]">· sugg. <strong>{value} kg</strong></span>;
}

function PreviousPerformance({ slot }: { slot: SlotToday }) {
  if (!slot.derniere_fois) return null;
  return <p className="mt-1 text-xs text-[var(--muted-foreground)]">↩︎ Dernière fois ({new Date(slot.derniere_fois.date + "T12:00:00").toLocaleDateString("fr-CA", { day: "numeric", month: "short" })}) : <span className="text-[var(--foreground)]">{slot.derniere_fois.resume}</span></p>;
}

function SlotProgress({ target, progress }: { target: number | null; progress: number }) {
  if (!target) return null;
  return <div className="mt-1 h-1 rounded-full bg-[var(--muted)] overflow-hidden"><div className="h-full bg-[var(--ring)] bar-fill" style={{ width: `${progress}%` }} /></div>;
}

function CompletedSets({ sets }: { sets: Seance["sets"] }) {
  if (sets.length === 0) return null;
  return <ul className="mt-2 text-xs space-y-0.5 text-[var(--muted-foreground)]">{sets.map((set, index) => <li key={set.id}>Série {index + 1} : <strong className="text-[var(--foreground)]">{set.reps}</strong> reps × <strong className="text-[var(--foreground)]">{set.poids_kg}</strong> kg{set.rpe ? ` · RPE ${set.rpe}` : ""}</li>)}</ul>;
}

function SlotActions({ slot, seance, noExercice, isWarmup, onRest }: { slot: SlotToday; seance: Seance | null; noExercice: boolean; isWarmup: boolean; onRest: () => void }) {
  if (!seance || isWarmup) return null;
  if (noExercice) return <p className="mt-2 text-xs text-[var(--warning)]">⚠ Exercice « {slot.label} » introuvable dans le catalogue.</p>;
  return <AddSetForm seanceId={seance.id} exerciceId={slot.exercice_id!} suggested={suggestedWeight(slot)} repsHint={repsHint(slot)} onRest={onRest} />;
}

function suggestedWeight(slot: SlotToday): number {
  return slot.poids_suggere_kg ?? 0;
}

function repsHint(slot: SlotToday): number {
  return typeof slot.reps_target === "number" ? slot.reps_target : 8;
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
