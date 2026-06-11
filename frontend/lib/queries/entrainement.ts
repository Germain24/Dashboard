"use client";

/** Couche TanStack Query du module Entraînement (#522) — modèle : lib/queries/finance.ts. */

import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import {
  entrainementApi,
  type CourseCardioCreate,
  type SeanceCreate,
  type SetSerieCreate,
} from "@/lib/entrainement";

export const entrainementKeys = {
  all: ["entrainement"] as const,
  today: () => [...entrainementKeys.all, "today"] as const,
  program: () => [...entrainementKeys.all, "program"] as const,
  exercices: (categorie?: string) =>
    [...entrainementKeys.all, "exercices", categorie ?? "all"] as const,
  sessions: (params?: { from?: string; to?: string }) =>
    [...entrainementKeys.all, "sessions", params ?? {}] as const,
  session: (id: number) => [...entrainementKeys.all, "session", id] as const,
  intensityToday: () => [...entrainementKeys.all, "intensity-today"] as const,
  cardio: (params?: { from?: string; to?: string }) =>
    [...entrainementKeys.all, "cardio", params ?? {}] as const,
  progression: (exerciceId: number, days: number) =>
    [...entrainementKeys.all, "progression", exerciceId, days] as const,
  muscleVolume: (days: number) => [...entrainementKeys.all, "muscle-volume", days] as const,
  correlation: (weeks: number) => [...entrainementKeys.all, "correlation", weeks] as const,
};

export function useEntrainementToday() {
  return useQuery({ queryKey: entrainementKeys.today(), queryFn: entrainementApi.getToday });
}
export function useProgram() {
  return useQuery({ queryKey: entrainementKeys.program(), queryFn: entrainementApi.getProgram });
}
export function useExercices(categorie?: string) {
  return useQuery({
    queryKey: entrainementKeys.exercices(categorie),
    queryFn: () => entrainementApi.listExercices(categorie),
  });
}
export function useSessions(params?: { from?: string; to?: string }) {
  return useQuery({
    queryKey: entrainementKeys.sessions(params),
    queryFn: () => entrainementApi.listSessions(params),
  });
}
export function useSessionDetail(id: number | null) {
  return useQuery({
    queryKey: entrainementKeys.session(id ?? 0),
    queryFn: () => entrainementApi.getSession(id as number),
    enabled: id != null,
  });
}
export function useIntensityToday() {
  return useQuery({
    queryKey: entrainementKeys.intensityToday(),
    queryFn: entrainementApi.getIntensityToday,
  });
}
export function useCardioList(params?: { from?: string; to?: string }) {
  return useQuery({
    queryKey: entrainementKeys.cardio(params),
    queryFn: () => entrainementApi.listCardio(params),
  });
}
export function useProgression(exerciceId: number | null, days = 90) {
  return useQuery({
    queryKey: entrainementKeys.progression(exerciceId ?? 0, days),
    queryFn: () => entrainementApi.getProgression(exerciceId as number, days),
    enabled: exerciceId != null,
  });
}
export function useMuscleVolume(days = 7) {
  return useQuery({
    queryKey: entrainementKeys.muscleVolume(days),
    queryFn: () => entrainementApi.getMuscleVolume(days),
  });
}
export function useTrainingCorrelation(weeks = 12) {
  return useQuery({
    queryKey: entrainementKeys.correlation(weeks),
    queryFn: () => entrainementApi.getCorrelation(weeks),
  });
}

function useInvalidateAll() {
  const qc = useQueryClient();
  return () => qc.invalidateQueries({ queryKey: entrainementKeys.all });
}

export function useCreateSession() {
  const invalidate = useInvalidateAll();
  return useMutation({
    mutationFn: (p: SeanceCreate) => entrainementApi.createSession(p),
    onSuccess: invalidate,
  });
}
export function usePatchSession() {
  const invalidate = useInvalidateAll();
  return useMutation({
    mutationFn: (p: { id: number; patch: Partial<SeanceCreate> }) =>
      entrainementApi.patchSession(p.id, p.patch),
    onSuccess: invalidate,
  });
}
export function useAddSet() {
  const invalidate = useInvalidateAll();
  return useMutation({
    mutationFn: (p: { seanceId: number; set: SetSerieCreate }) =>
      entrainementApi.addSet(p.seanceId, p.set),
    onSuccess: invalidate,
  });
}
export function useStartMesocycle() {
  const invalidate = useInvalidateAll();
  return useMutation({
    mutationFn: (weeks: number) => entrainementApi.startMesocycle(weeks),
    onSuccess: invalidate,
  });
}
export function useStopMesocycle() {
  const invalidate = useInvalidateAll();
  return useMutation({ mutationFn: () => entrainementApi.stopMesocycle(), onSuccess: invalidate });
}
export function useCreateCardio() {
  const invalidate = useInvalidateAll();
  return useMutation({
    mutationFn: (p: CourseCardioCreate) => entrainementApi.createCardio(p),
    onSuccess: invalidate,
  });
}
export function useDeleteCardio() {
  const invalidate = useInvalidateAll();
  return useMutation({ mutationFn: (id: number) => entrainementApi.deleteCardio(id), onSuccess: invalidate });
}
export function usePatchProgramJour() {
  const invalidate = useInvalidateAll();
  return useMutation({
    mutationFn: (p: { weekday: number; payload: Parameters<typeof entrainementApi.patchProgramJour>[1] }) =>
      entrainementApi.patchProgramJour(p.weekday, p.payload),
    onSuccess: invalidate,
  });
}
