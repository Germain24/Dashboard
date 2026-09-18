"use client";

/** Couche TanStack Query du module Travail. */

import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { travailApi, type WorkShift } from "@/lib/travail";

export const travailKeys = {
  all: ["travail"] as const,
  shifts: (mois: string) => [...travailKeys.all, "shifts", mois] as const,
  summary: (mois: string) => [...travailKeys.all, "summary", mois] as const,
  settings: () => [...travailKeys.all, "settings"] as const,
};

export function useShifts(mois: string) {
  return useQuery({ queryKey: travailKeys.shifts(mois), queryFn: () => travailApi.shifts(mois) });
}
export function useTravailSummary(mois: string) {
  return useQuery({ queryKey: travailKeys.summary(mois), queryFn: () => travailApi.summary(mois) });
}
export function useTravailSettings() {
  return useQuery({ queryKey: travailKeys.settings(), queryFn: travailApi.settings });
}

function useInvalidateAll() {
  const qc = useQueryClient();
  return () => qc.invalidateQueries({ queryKey: travailKeys.all });
}

export function useCreateShift() {
  const invalidate = useInvalidateAll();
  return useMutation({ mutationFn: (d: Partial<WorkShift>) => travailApi.create(d), onSuccess: invalidate });
}
export function useUpdateShift() {
  const invalidate = useInvalidateAll();
  return useMutation({
    mutationFn: (p: { id: number; patch: Partial<WorkShift> }) => travailApi.update(p.id, p.patch),
    onSuccess: invalidate,
  });
}
export function useDeleteShift() {
  const invalidate = useInvalidateAll();
  return useMutation({ mutationFn: (id: number) => travailApi.remove(id), onSuccess: invalidate });
}
export function useSetTauxHoraire() {
  const invalidate = useInvalidateAll();
  return useMutation({ mutationFn: (t: number) => travailApi.setTauxHoraire(t), onSuccess: invalidate });
}
