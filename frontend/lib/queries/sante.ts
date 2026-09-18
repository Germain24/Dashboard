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
  scoreCorrelations: (jours: number) => [...santeKeys.all, "score-correlations", jours] as const,
  favorites: () => [...santeKeys.all, "favorites"] as const,
  photos: () => [...santeKeys.all, "photos"] as const,
  fenetre: (date?: string) => [...santeKeys.all, "fenetre", date ?? "current"] as const,
  cartPlan: (date?: string) => [...santeKeys.all, "cart-plan", date ?? "current"] as const,
  cartFill: (jobId: string) => [...santeKeys.all, "cart-fill", jobId] as const,
  generateFenetre: (jobId: string) => [...santeKeys.all, "fenetre-generate", jobId] as const,
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
export function useScoreCorrelations(jours = 90) {
  return useQuery({
    queryKey: santeKeys.scoreCorrelations(jours),
    queryFn: () => santeApi.scoreCorrelations(jours),
  });
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

// ── Fenêtre batch-cook ────────────────────────────────────────────────────────
export function useFenetreCurrent(date?: string) {
  return useQuery({
    queryKey: santeKeys.fenetre(date),
    queryFn: () => santeApi.fenetreCurrent(date),
    retry: false,
  });
}
export function useGenerateFenetre() {
  const invalidate = useInvalidateAll();
  return useMutation({
    mutationFn: (body: Parameters<typeof santeApi.generateFenetre>[0]) => santeApi.generateFenetre(body),
    onSuccess: invalidate,
  });
}
export function useCartPlan(date?: string) {
  return useQuery({
    queryKey: santeKeys.cartPlan(date),
    queryFn: () => santeApi.cartPlan(date),
    retry: false,
  });
}
export function useStartGenerateFenetre() {
  return useMutation({
    mutationFn: (body: Parameters<typeof santeApi.startGenerateFenetre>[0]) =>
      santeApi.startGenerateFenetre(body),
  });
}
export function useGenerateFenetreStatus(jobId: string | null) {
  return useQuery({
    queryKey: santeKeys.generateFenetre(jobId ?? "idle"),
    queryFn: () => santeApi.generateFenetreStatus(jobId as string),
    enabled: jobId != null,
    refetchInterval: (query) => {
      const status = query.state.data?.status;
      return status && !["completed", "failed"].includes(status) ? 1500 : false;
    },
  });
}
export function useActiveGenerateFenetre() {
  return useQuery({
    queryKey: [...santeKeys.all, "fenetre-generate-active"],
    queryFn: () => santeApi.activeGenerateFenetre(),
    refetchInterval: (query) => query.state.data ? 1500 : false,
  });
}
export function useStopGenerateFenetre() {
  return useMutation({
    mutationFn: (jobId: string) => santeApi.stopGenerateFenetre(jobId),
  });
}
export function useStartCartFill() {
  return useMutation({ mutationFn: (date?: string) => santeApi.startCartFill(date) });
}
export function useCartFillStatus(jobId: string | null) {
  return useQuery({
    queryKey: santeKeys.cartFill(jobId ?? "idle"),
    queryFn: () => santeApi.cartFillStatus(jobId as string),
    enabled: jobId != null,
    refetchInterval: (query) => {
      const status = query.state.data?.status;
      return status && !["completed", "failed"].includes(status) ? 1000 : false;
    },
  });
}
