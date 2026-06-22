"use client";

/** Couche TanStack Query du module Santé (#530). */

import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { santeApi } from "@/lib/sante";

export const santeKeys = {
  all: ["sante"] as const,
  mesures: (days: number) => [...santeKeys.all, "mesures", days] as const,
  goal: () => [...santeKeys.all, "goal"] as const,
  planToday: () => [...santeKeys.all, "plan-today"] as const,
  projection: () => [...santeKeys.all, "projection"] as const,
  waterToday: () => [...santeKeys.all, "water-today"] as const,
  sleepSummary: (days: number) => [...santeKeys.all, "sleep-summary", days] as const,
  workoutBurn: () => [...santeKeys.all, "workout-burn"] as const,
  weeklyQuality: (days: number) => [...santeKeys.all, "weekly-quality", days] as const,
  energyBalance: (days: number) => [...santeKeys.all, "energy-balance", days] as const,
  aliments: () => [...santeKeys.all, "aliments"] as const,
  score: () => [...santeKeys.all, "score"] as const,
  scoreHistory: (days: number) => [...santeKeys.all, "score-history", days] as const,
  favorites: () => [...santeKeys.all, "favorites"] as const,
  photos: () => [...santeKeys.all, "photos"] as const,
};

export function useMesures(days = 180) {
  return useQuery({ queryKey: santeKeys.mesures(days), queryFn: () => santeApi.listMesures(days) });
}
export function useScore() {
  return useQuery({ queryKey: santeKeys.score(), queryFn: santeApi.score });
}
export function useScoreHistory(days = 90) {
  return useQuery({ queryKey: santeKeys.scoreHistory(days), queryFn: () => santeApi.scoreHistory(days) });
}
export function useNutritionGoal() {
  return useQuery({ queryKey: santeKeys.goal(), queryFn: santeApi.getGoal });
}
export function usePlanToday() {
  return useQuery({ queryKey: santeKeys.planToday(), queryFn: santeApi.getPlanToday, retry: false });
}
export function useProjection() {
  return useQuery({
    queryKey: santeKeys.projection(),
    queryFn: () => santeApi.getProjection(),
    retry: false,
  });
}
export function useWaterToday() {
  return useQuery({ queryKey: santeKeys.waterToday(), queryFn: santeApi.waterToday });
}
export function useSleepSummary(days = 30) {
  return useQuery({ queryKey: santeKeys.sleepSummary(days), queryFn: () => santeApi.sleepSummary(days) });
}
export function useWorkoutBurn() {
  return useQuery({ queryKey: santeKeys.workoutBurn(), queryFn: () => santeApi.workoutBurn() });
}
export function useWeeklyQuality(days = 7) {
  return useQuery({ queryKey: santeKeys.weeklyQuality(days), queryFn: () => santeApi.weeklyQuality(days) });
}
export function useEnergyBalance(days = 7) {
  return useQuery({ queryKey: santeKeys.energyBalance(days), queryFn: () => santeApi.energyBalance(days) });
}
export function useSanteAliments() {
  return useQuery({ queryKey: santeKeys.aliments(), queryFn: santeApi.listAliments });
}
export function useSanteFavorites() {
  return useQuery({ queryKey: santeKeys.favorites(), queryFn: santeApi.listFavorites });
}
export function useProgressPhotos() {
  return useQuery({ queryKey: santeKeys.photos(), queryFn: santeApi.listPhotos });
}

function useInvalidateAll() {
  const qc = useQueryClient();
  return () => qc.invalidateQueries({ queryKey: santeKeys.all });
}

export function useUpsertMesure() {
  const invalidate = useInvalidateAll();
  return useMutation({
    mutationFn: (p: Parameters<typeof santeApi.upsertMesure>[0]) => santeApi.upsertMesure(p),
    onSuccess: invalidate,
  });
}
export function useUpdateNutritionGoal() {
  const invalidate = useInvalidateAll();
  return useMutation({
    mutationFn: (p: Parameters<typeof santeApi.updateGoal>[0]) => santeApi.updateGoal(p),
    onSuccess: invalidate,
  });
}
export function useGeneratePlan() {
  const invalidate = useInvalidateAll();
  return useMutation({
    mutationFn: (p: Parameters<typeof santeApi.generatePlan>[0]) => santeApi.generatePlan(p),
    onSuccess: invalidate,
  });
}
export function usePatchPlan() {
  const invalidate = useInvalidateAll();
  return useMutation({
    mutationFn: (p: { date: string; patch: Parameters<typeof santeApi.patchPlan>[1] }) =>
      santeApi.patchPlan(p.date, p.patch),
    onSuccess: invalidate,
  });
}
export function useAddWater() {
  const invalidate = useInvalidateAll();
  return useMutation({
    mutationFn: (ml: number) => santeApi.addWater(ml),
    onSuccess: invalidate,
  });
}
export function useLogSleep() {
  const invalidate = useInvalidateAll();
  return useMutation({
    mutationFn: (p: { heures: number; qualite?: number }) => santeApi.logSleep(p.heures, p.qualite),
    onSuccess: invalidate,
  });
}
export function useAddSanteFavorite() {
  const invalidate = useInvalidateAll();
  return useMutation({ mutationFn: (nom: string) => santeApi.addFavorite(nom), onSuccess: invalidate });
}
export function useRemoveSanteFavorite() {
  const invalidate = useInvalidateAll();
  return useMutation({ mutationFn: (nom: string) => santeApi.removeFavorite(nom), onSuccess: invalidate });
}
export function useUploadProgressPhoto() {
  const invalidate = useInvalidateAll();
  return useMutation({
    mutationFn: (p: Parameters<typeof santeApi.uploadPhoto>) => santeApi.uploadPhoto(...p),
    onSuccess: invalidate,
  });
}
