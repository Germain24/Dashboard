"use client";

/** Onglet « Aujourd'hui » — vue opérationnelle de la séance du jour (#522 :
 *  migré TanStack Query ; SlotCard et widgets extraits). */

import { useCallback, useState } from "react";
import {
  useCreateSession,
  useEntrainementToday,
  usePatchSession,
  useStartMesocycle,
  useStopMesocycle,
} from "@/lib/queries/entrainement";
import { SlotCard } from "./SlotCard";
import { FinishBar, MesocycleBanner, RestTimer } from "./SeanceWidgets";
import { Button } from "@/components/ui/button";
import { Spinner } from "@/components/ui/spinner";
import { EmptyState } from "@/components/ui/empty-state";

export function AujourdhuiTab() {
  // Minuteur de repos entre séries (#106)
  const [restDuration, setRestDuration] = useState(90);
  const [restEndsAt, setRestEndsAt] = useState<number | null>(null);
  const startRest = useCallback((sec: number) => {
    setRestDuration(sec);
    setRestEndsAt(Date.now() + sec * 1000);
  }, []);

  const todayQ = useEntrainementToday();
  const today = todayQ.data ?? null;
  const createSession = useCreateSession();
  const patchSession = usePatchSession();
  const startMesoMutation = useStartMesocycle();
  const stopMesoMutation = useStopMesocycle();
  const [actionErr, setActionErr] = useState<string | null>(null);

  const handleStart = () => {
    if (!today) return;
    setActionErr(null);
    createSession.mutate(
      {
        date: new Date().toISOString(),
        type: today.jour_label.toLowerCase(),
        programme_jour_id: today.programme_jour_id,
      },
      { onError: (e) => setActionErr(e instanceof Error ? e.message : "Erreur création séance") },
    );
  };

  const handleFinish = (duree_min: number) => {
    if (!today?.seance_en_cours) return;
    patchSession.mutate(
      { id: today.seance_en_cours.id, patch: { duree_min } },
      { onError: (e) => setActionErr(e instanceof Error ? e.message : "Erreur") },
    );
  };

  const startMeso = () =>
    startMesoMutation.mutate(4, { onError: () => setActionErr("Erreur mésocycle") });
  const stopMeso = () =>
    stopMesoMutation.mutate(undefined, { onError: () => setActionErr("Erreur mésocycle") });

  if (todayQ.isLoading) return <Spinner label="Chargement…" />;
  const err = actionErr ?? (todayQ.isError ? (todayQ.error as Error).message : null);
  if (err) return <p className="text-sm text-[var(--destructive)]">⚠ {err}</p>;
  if (!today) return null;

  const isRest = today.jour_label.toLowerCase() === "repos";
  const seance = today.seance_en_cours;
  const dureeStarted = seance ? new Date(seance.date) : null;

  return (
    <div className="space-y-4 animate-fade-in-up">
      <div className="rounded-xl border border-[var(--border)] bg-[var(--card)] p-3 flex flex-wrap items-center gap-3 text-sm card-hover">
        <span className="font-medium">
          {new Date(today.date + "T12:00:00").toLocaleDateString("fr-CA", {
            weekday: "long", day: "numeric", month: "long",
          })}
        </span>
        <span className="rounded-[var(--radius-sm)] bg-[var(--muted)] px-2 py-0.5 text-xs font-medium">
          {today.jour_label}
        </span>
        <span className="text-xs text-[var(--muted-foreground)]">
          Poids : {today.poids_corps_kg.toFixed(1)} kg
        </span>
        {today.kcal_estimees > 0 && (
          <span className="ml-auto rounded-md bg-[color-mix(in_srgb,var(--success,#16a34a)_12%,transparent)] text-[var(--success,#16a34a)] px-2 py-0.5 text-xs">
            🔥 {today.kcal_estimees.toFixed(0)} kcal
          </span>
        )}
      </div>

      <MesocycleBanner meso={today.mesocycle} onStart={startMeso} onStop={stopMeso} />

      {isRest && (
        <EmptyState
          title="Jour de repos"
          description="Profite-en pour récupérer. 😴"
        />
      )}

      {!isRest && !seance && (
        <div className="rounded-[var(--radius)] border border-[var(--border)] p-4 flex flex-wrap items-center gap-3">
          <span className="text-sm">Prêt pour la séance {today.jour_label} ?</span>
          <Button onClick={handleStart} className="ml-auto" size="sm">
            ▶️ Commencer la séance
          </Button>
        </div>
      )}

      {!isRest && (
        <div className="space-y-2 stagger">
          {today.slots.map((slot, i) => (
            <SlotCard
              key={i}
              slot={slot}
              seance={seance}
              onRest={() => startRest(restDuration)}
            />
          ))}
          {today.slots.length === 0 && (
            <EmptyState
              title="Aucun slot configuré"
              description="Lance POST /entrainement/program/seed-garmin ou édite le jour dans l'onglet Programme."
            />
          )}
        </div>
      )}

      {seance && (
        <RestTimer
          endsAt={restEndsAt}
          duration={restDuration}
          onPreset={startRest}
          onSkip={() => setRestEndsAt(null)}
        />
      )}

      {seance && (
        <FinishBar startedAt={dureeStarted!} onFinish={handleFinish} />
      )}
    </div>
  );
}
