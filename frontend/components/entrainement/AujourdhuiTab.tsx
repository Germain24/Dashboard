"use client";

/** Onglet « Aujourd'hui » — vue opérationnelle de la séance du jour (#522 :
 *  migré TanStack Query ; SlotCard et widgets extraits). */

import { useCallback, useState } from "react";
import { useEntrainementToday } from "@/lib/queries/entrainement";
import { Spinner } from "@/components/ui/spinner";
import { MesocycleBanner } from "./SeanceWidgets";
import { TodaySummary, TodayTimers, TodayWorkout } from "./AujourdhuiTabParts";
import { queryError, useTodayActions } from "./AujourdhuiTabController";

export function AujourdhuiTab() {
  // Minuteur de repos entre séries (#106)
  const [restDuration, setRestDuration] = useState(90);
  const [restEndsAt, setRestEndsAt] = useState<number | null>(null);
  const startRest = useCallback((sec: number) => {
    setRestDuration(sec);
    setRestEndsAt(Date.now() + sec * 1000);
  }, []);

  const todayQ = useEntrainementToday();
  const today = todayQ.data;
  const { actionErr, handleStart, handleFinish, startMeso, stopMeso } = useTodayActions(today);

  return <AujourdhuiState query={todayQ} actionErr={actionErr} actions={{ handleStart, handleFinish, startMeso, stopMeso }} timer={{ restEndsAt, restDuration, startRest, setRestEndsAt }} />;
}

function AujourdhuiState({ query, actionErr, actions, timer }: {
  query: ReturnType<typeof useEntrainementToday>;
  actionErr: string | null;
  actions: { handleStart: () => void; handleFinish: (minutes: number) => void; startMeso: () => void; stopMeso: () => void };
  timer: { restEndsAt: number | null; restDuration: number; startRest: (seconds: number) => void; setRestEndsAt: (value: number | null) => void };
}) {
  if (query.isLoading) return <Spinner label="Chargement…" />;
  const err = todayError(actionErr, query.error, query.isError);
  if (err) return <p className="text-sm text-[var(--destructive)]">⚠ {err}</p>;
  if (!query.data) return null;
  return <LoadedToday today={query.data} actions={actions} timer={timer} />;
}

function todayError(actionErr: string | null, queryErr: unknown, isError: boolean): string | null {
  if (actionErr) return actionErr;
  return queryError(queryErr, isError);
}

function LoadedToday({ today, actions, timer }: {
  today: NonNullable<ReturnType<typeof useEntrainementToday>["data"]>;
  actions: { handleStart: () => void; handleFinish: (minutes: number) => void; startMeso: () => void; stopMeso: () => void };
  timer: { restEndsAt: number | null; restDuration: number; startRest: (seconds: number) => void; setRestEndsAt: (value: number | null) => void };
}) {
  const seance = today.seance_en_cours;
  return (
    <div className="space-y-4 animate-fade-in-up">
      <TodaySummary today={today} />
      <MesocycleBanner meso={today.mesocycle} onStart={actions.startMeso} onStop={actions.stopMeso} />
      <TodayWorkout today={today} seance={seance} onStart={actions.handleStart} onRest={() => timer.startRest(timer.restDuration)} />
      <TodayTimers
        seance={seance}
        restEndsAt={timer.restEndsAt}
        restDuration={timer.restDuration}
        onPreset={timer.startRest}
        onSkip={() => timer.setRestEndsAt(null)}
        startedAt={sessionStart(seance)}
        onFinish={actions.handleFinish}
      />
    </div>
  );
}

function sessionStart(seance: NonNullable<ReturnType<typeof useEntrainementToday>["data"]>["seance_en_cours"]): Date | null {
  if (!seance) return null;
  return new Date(seance.date);
}
