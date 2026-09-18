"use client";

/** Couche TanStack Query du module Objectifs long terme. */

import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { objectifsApi, type LongTermGoal } from "@/lib/objectifs";

export const objectifsKeys = {
  all: ["objectifs"] as const,
  goals: () => [...objectifsKeys.all, "goals"] as const,
};

export function useGoals() {
  return useQuery({ queryKey: objectifsKeys.goals(), queryFn: objectifsApi.list });
}

function useInvalidateAll() {
  const qc = useQueryClient();
  return () => qc.invalidateQueries({ queryKey: objectifsKeys.all });
}

export function useCreateGoal() {
  const invalidate = useInvalidateAll();
  return useMutation({ mutationFn: (d: Partial<LongTermGoal>) => objectifsApi.create(d), onSuccess: invalidate });
}
export function useUpdateGoal() {
  const invalidate = useInvalidateAll();
  return useMutation({
    mutationFn: (p: { id: number; patch: Partial<LongTermGoal> }) => objectifsApi.update(p.id, p.patch),
    onSuccess: invalidate,
  });
}
export function useDeleteGoal() {
  const invalidate = useInvalidateAll();
  return useMutation({ mutationFn: (id: number) => objectifsApi.remove(id), onSuccess: invalidate });
}
