"use client";

import { EmptyState } from "@/components/ui/empty-state";
import { Button } from "@/components/ui/button";
import { StaggerGroup, StaggerItem } from "@/lib/motion/Stagger";
import type { Seance, SlotToday, TodayResponse } from "@/lib/entrainement";
import { FinishBar, RestTimer } from "./SeanceWidgets";
import { SlotCard } from "./SlotCard";

export function TodaySummary({ today }: { today: TodayResponse }) {
  return (
    <div className="rounded-xl border border-[var(--border)] bg-[var(--card)] p-3 flex flex-wrap items-center gap-3 text-sm card-hover">
      <span className="font-medium">
        {new Date(today.date + "T12:00:00").toLocaleDateString("fr-CA", {
          weekday: "long", day: "numeric", month: "long",
        })}
      </span>
      <span className="rounded-[var(--radius-sm)] bg-[var(--muted)] px-2 py-0.5 text-xs font-medium">{today.jour_label}</span>
      <span className="text-xs text-[var(--muted-foreground)]">Poids : {today.poids_corps_kg.toFixed(1)} kg</span>
      {today.kcal_estimees > 0 && (
        <span className="ml-auto rounded-md bg-[var(--success-muted)] text-[var(--success-foreground)] px-2 py-0.5 text-xs">
          🔥 {today.kcal_estimees.toFixed(0)} kcal
        </span>
      )}
    </div>
  );
}

export function TodayWorkout({
  today,
  seance,
  onStart,
  onRest,
}: {
  today: TodayResponse;
  seance: Seance | null;
  onStart: () => void;
  onRest: () => void;
}) {
  if (today.jour_label.toLowerCase() === "repos") {
    return <EmptyState title="Jour de repos" description="Profite-en pour récupérer. 😴" />;
  }

  return (
    <>
      {!seance && (
        <div className="rounded-[var(--radius)] border border-[var(--border)] p-4 flex flex-wrap items-center gap-3">
          <span className="text-sm">Prêt pour la séance {today.jour_label} ?</span>
          <Button onClick={onStart} className="ml-auto" size="sm">▶️ Commencer la séance</Button>
        </div>
      )}
      <WorkoutSlots slots={today.slots} seance={seance} onRest={onRest} />
    </>
  );
}

function WorkoutSlots({ slots, seance, onRest }: { slots: SlotToday[]; seance: Seance | null; onRest: () => void }) {
  if (slots.length === 0) {
    return <EmptyState title="Aucun slot configuré" description="Lance POST /entrainement/program/seed-garmin ou édite le jour dans l'onglet Programme." />;
  }
  return (
    <StaggerGroup className="space-y-2">
      {slots.map((slot, index) => (
        <StaggerItem key={index}>
          <SlotCard slot={slot} seance={seance} onRest={onRest} />
        </StaggerItem>
      ))}
    </StaggerGroup>
  );
}

export function TodayTimers({
  seance,
  restEndsAt,
  restDuration,
  onPreset,
  onSkip,
  startedAt,
  onFinish,
}: {
  seance: Seance | null;
  restEndsAt: number | null;
  restDuration: number;
  onPreset: (seconds: number) => void;
  onSkip: () => void;
  startedAt: Date | null;
  onFinish: (minutes: number) => void;
}) {
  if (!seance) return null;
  return (
    <>
      <RestTimer endsAt={restEndsAt} duration={restDuration} onPreset={onPreset} onSkip={onSkip} />
      {startedAt && <FinishBar startedAt={startedAt} onFinish={onFinish} />}
    </>
  );
}
