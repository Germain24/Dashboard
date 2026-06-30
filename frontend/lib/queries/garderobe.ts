"use client";

/** Couche TanStack Query du module Garde-robe (#524) — modèle : lib/queries/finance.ts. */

import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { garderobeApi, type VetementUpdate } from "@/lib/garderobe";

export const garderobeKeys = {
  all: ["garderobe"] as const,
  vetements: (params?: Record<string, string>) =>
    [...garderobeKeys.all, "vetements", params ?? {}] as const,
  meteo: () => [...garderobeKeys.all, "meteo"] as const,
  slots: () => [...garderobeKeys.all, "slots"] as const,
  stats: () => [...garderobeKeys.all, "stats"] as const,
  history: (limit: number) => [...garderobeKeys.all, "history", limit] as const,
  recommendations: () => [...garderobeKeys.all, "recommendations"] as const,
  frequence: (topN: number) => [...garderobeKeys.all, "frequence", topN] as const,
  planner: (start?: string) => [...garderobeKeys.all, "planner", start ?? "current"] as const,
  objectif: () => [...garderobeKeys.all, "objectif"] as const,
};

export function useVetements(params?: Parameters<typeof garderobeApi.listVetements>[0]) {
  return useQuery({
    queryKey: garderobeKeys.vetements(params as Record<string, string> | undefined),
    queryFn: () => garderobeApi.listVetements(params),
  });
}
export function useMeteo() {
  return useQuery({ queryKey: garderobeKeys.meteo(), queryFn: () => garderobeApi.getMeteo() });
}
export function useGarderobeSlots() {
  return useQuery({ queryKey: garderobeKeys.slots(), queryFn: garderobeApi.getSlots });
}
export function useGarderobeStats() {
  return useQuery({ queryKey: garderobeKeys.stats(), queryFn: garderobeApi.stats });
}
export function useTenueHistory(limit = 20) {
  return useQuery({ queryKey: garderobeKeys.history(limit), queryFn: () => garderobeApi.history(limit) });
}
export function useGarderobeRecommendations() {
  return useQuery({ queryKey: garderobeKeys.recommendations(), queryFn: garderobeApi.recommendations });
}
export function useWearFrequence(topN = 5) {
  return useQuery({ queryKey: garderobeKeys.frequence(topN), queryFn: () => garderobeApi.frequence(topN) });
}
export function useWeekPlanner(start?: string) {
  return useQuery({ queryKey: garderobeKeys.planner(start), queryFn: () => garderobeApi.getPlanner(start) });
}

function useInvalidateAll() {
  const qc = useQueryClient();
  return () => qc.invalidateQueries({ queryKey: garderobeKeys.all });
}

/** Suggestion = action imperative (recalcul) : mutation sans invalidation. */
export function useSuggestTenue() {
  return useMutation({
    mutationFn: (opts: { mean_temp?: number; rain?: boolean } = {}) => garderobeApi.suggest(opts),
  });
}
export function useValiderTenue() {
  const invalidate = useInvalidateAll();
  return useMutation({
    mutationFn: (p: { tenue: Record<string, string | null>; use_body?: boolean; note?: string }) =>
      garderobeApi.valider(p),
    onSuccess: invalidate,
  });
}
export function useUpdateVetement() {
  const invalidate = useInvalidateAll();
  return useMutation({
    mutationFn: (p: { id: string; patch: VetementUpdate }) =>
      garderobeApi.updateVetement(p.id, p.patch),
    onSuccess: invalidate,
  });
}
export function useUploadVetementPhoto() {
  const invalidate = useInvalidateAll();
  return useMutation({
    mutationFn: (p: { id: string; file: File; couleurDominante?: string }) =>
      garderobeApi.uploadPhoto(p.id, p.file, p.couleurDominante),
    onSuccess: invalidate,
  });
}
export function useObjectif() {
  return useQuery({ queryKey: garderobeKeys.objectif(), queryFn: garderobeApi.getObjectif });
}
export function useSyncObjectif() {
  const invalidate = useInvalidateAll();
  return useMutation({ mutationFn: garderobeApi.syncObjectif, onSuccess: invalidate });
}
export function useAutoRattacher() {
  const invalidate = useInvalidateAll();
  return useMutation({ mutationFn: garderobeApi.autoRattacher, onSuccess: invalidate });
}
export function useSetPlannerDay() {
  const invalidate = useInvalidateAll();
  return useMutation({
    mutationFn: (p: { date: string; tenue: Record<string, string | null> }) =>
      garderobeApi.setPlannerDay(p.date, p.tenue),
    onSuccess: invalidate,
  });
}
