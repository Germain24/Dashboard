"use client";

/** Couche TanStack Query du module Voyage — modèle : lib/queries/garderobe.ts. */

import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { voyageApi, type PlanifierAutoRequest, type PlanifierRequest } from "@/lib/voyage";

export const voyageKeys = {
  all: ["voyage"] as const,
  lieux: () => [...voyageKeys.all, "lieux"] as const,
};

export function useLieuxVoyage() {
  return useQuery({ queryKey: voyageKeys.lieux(), queryFn: voyageApi.listLieux });
}

export function useSyncVoyage() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: voyageApi.sync,
    onSuccess: () => queryClient.invalidateQueries({ queryKey: voyageKeys.all }),
  });
}

export function useSuggererLieux() {
  return useMutation({
    mutationFn: ({ departIata, limit }: { departIata: string; limit?: number }) =>
      voyageApi.suggerer(departIata, limit),
  });
}

export function usePlanifierAuto() {
  return useMutation({ mutationFn: (req: PlanifierAutoRequest) => voyageApi.planifierAuto(req) });
}

export function usePlanifier() {
  return useMutation({ mutationFn: (req: PlanifierRequest) => voyageApi.planifier(req) });
}

export function useConfirmerVoyage() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (lieuIds: number[]) => voyageApi.confirmer(lieuIds),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: voyageKeys.all }),
  });
}
