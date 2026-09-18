"use client";

import { useCallback, useState } from "react";
import type { TodayResponse } from "@/lib/entrainement";
import {
  useCreateSession,
  usePatchSession,
  useStartMesocycle,
  useStopMesocycle,
} from "@/lib/queries/entrainement";

export function useTodayActions(today: TodayResponse | undefined) {
  const createSession = useCreateSession();
  const patchSession = usePatchSession();
  const { mutate: startMeso } = useStartMesocycle();
  const { mutate: stopMeso } = useStopMesocycle();
  const [actionErr, setActionErr] = useState<string | null>(null);

  return {
    actionErr,
    handleStart: useCallback(() => startSession(today, createSession.mutate, setActionErr), [today, createSession.mutate]),
    handleFinish: useCallback((minutes: number) => finishSession(today, patchSession.mutate, setActionErr, minutes), [today, patchSession.mutate]),
    startMeso: useCallback(() => startMeso(4, { onError: () => setActionErr("Erreur mésocycle") }), [startMeso]),
    stopMeso: useCallback(() => stopMeso(undefined, { onError: () => setActionErr("Erreur mésocycle") }), [stopMeso]),
  };
}

function startSession(
  today: TodayResponse | undefined,
  mutate: ReturnType<typeof useCreateSession>["mutate"],
  report: (message: string | null) => void,
) {
  if (!today) return;
  report(null);
  mutate(
    { date: new Date().toISOString(), type: today.jour_label.toLowerCase(), programme_jour_id: today.programme_jour_id },
    { onError: (error) => report(error instanceof Error ? error.message : "Erreur création séance") },
  );
}

function finishSession(
  today: TodayResponse | undefined,
  mutate: ReturnType<typeof usePatchSession>["mutate"],
  report: (message: string | null) => void,
  minutes: number,
) {
  const session = today?.seance_en_cours;
  if (!session) return;
  mutate({ id: session.id, patch: { duree_min: minutes } }, { onError: (error) => report(error instanceof Error ? error.message : "Erreur") });
}

export function queryError(error: unknown, isError: boolean): string | null {
  if (!isError) return null;
  return error instanceof Error ? error.message : "Erreur de chargement";
}
