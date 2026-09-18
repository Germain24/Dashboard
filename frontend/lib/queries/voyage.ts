"use client";

/** Couche TanStack Query du module Voyage — modèle : lib/queries/garderobe.ts. */

import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import {
  voyageApi,
  type ConfirmerRequest,
  type PlanifierAutoRequest,
  type PlanifierRequest,
} from "@/lib/voyage";

export const voyageKeys = {
  all: ["voyage"] as const,
  lieux: () => [...voyageKeys.all, "lieux"] as const,
  voyages: () => [...voyageKeys.all, "voyages"] as const,
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
    mutationFn: (req: ConfirmerRequest) => voyageApi.confirmer(req),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: voyageKeys.all }),
  });
}

// ─── Voyages confirmés : checklist + budget par étape ─────────────────────────

export function useVoyagesConfirmes() {
  return useQuery({ queryKey: voyageKeys.voyages(), queryFn: voyageApi.listVoyages });
}

/** Invalide la liste des voyages : budget et checklist sont dérivés côté serveur. */
function useVoyagesMutation<TArgs>(fn: (args: TArgs) => Promise<unknown>) {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: fn,
    onSuccess: () => queryClient.invalidateQueries({ queryKey: voyageKeys.voyages() }),
  });
}

export function useDeleteVoyage() {
  return useVoyagesMutation((voyageId: number) => voyageApi.deleteVoyage(voyageId));
}

export function useSetCoutReel() {
  return useVoyagesMutation(
    ({ voyageId, etapeId, coutReel }: { voyageId: number; etapeId: number; coutReel: number | null }) =>
      voyageApi.setCoutReel(voyageId, etapeId, coutReel),
  );
}

export function useAddChecklistItem() {
  return useVoyagesMutation(({ voyageId, label }: { voyageId: number; label: string }) =>
    voyageApi.addChecklistItem(voyageId, label),
  );
}

export function useUpdateChecklistItem() {
  return useVoyagesMutation(
    ({ voyageId, itemId, patch }: {
      voyageId: number; itemId: number; patch: { label?: string; fait?: boolean; ordre?: number };
    }) => voyageApi.updateChecklistItem(voyageId, itemId, patch),
  );
}

export function useDeleteChecklistItem() {
  return useVoyagesMutation(({ voyageId, itemId }: { voyageId: number; itemId: number }) =>
    voyageApi.deleteChecklistItem(voyageId, itemId),
  );
}
