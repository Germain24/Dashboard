"use client";

/** Couche TanStack Query du module Langues & International. */

import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { languesApi, type ProjetInternational, type VocabEntry } from "@/lib/langues";

export const languesKeys = {
  all: ["langues"] as const,
  vocab: (type?: string) => [...languesKeys.all, "vocab", type ?? "tous"] as const,
  stats: () => [...languesKeys.all, "stats"] as const,
  projets: () => [...languesKeys.all, "projets"] as const,
};

export function useVocab(type?: string) {
  return useQuery({ queryKey: languesKeys.vocab(type), queryFn: () => languesApi.vocab(type) });
}
export function useVocabStats() {
  return useQuery({ queryKey: languesKeys.stats(), queryFn: languesApi.stats });
}
export function useProjets() {
  return useQuery({ queryKey: languesKeys.projets(), queryFn: languesApi.projets });
}

function useInvalidateAll() {
  const qc = useQueryClient();
  return () => qc.invalidateQueries({ queryKey: languesKeys.all });
}

export function useCreateVocab() {
  const invalidate = useInvalidateAll();
  return useMutation({ mutationFn: (d: Partial<VocabEntry>) => languesApi.createVocab(d), onSuccess: invalidate });
}
export function useUpdateVocab() {
  const invalidate = useInvalidateAll();
  return useMutation({
    mutationFn: (p: { id: number; patch: Partial<VocabEntry> }) => languesApi.updateVocab(p.id, p.patch),
    onSuccess: invalidate,
  });
}
export function useDeleteVocab() {
  const invalidate = useInvalidateAll();
  return useMutation({ mutationFn: (id: number) => languesApi.removeVocab(id), onSuccess: invalidate });
}
export function useCreateProjet() {
  const invalidate = useInvalidateAll();
  return useMutation({ mutationFn: (d: Partial<ProjetInternational>) => languesApi.createProjet(d), onSuccess: invalidate });
}
export function useUpdateProjet() {
  const invalidate = useInvalidateAll();
  return useMutation({
    mutationFn: (p: { id: number; patch: Partial<ProjetInternational> }) => languesApi.updateProjet(p.id, p.patch),
    onSuccess: invalidate,
  });
}
export function useDeleteProjet() {
  const invalidate = useInvalidateAll();
  return useMutation({ mutationFn: (id: number) => languesApi.removeProjet(id), onSuccess: invalidate });
}
