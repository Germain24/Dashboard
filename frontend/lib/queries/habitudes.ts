"use client";

/** Couche TanStack Query du module Habitudes (#525) — modèle : lib/queries/finance.ts. */

import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import {
  archiveHabit,
  checkEntry,
  createHabit,
  deleteEntry,
  fetchGamification,
  fetchHabits,
  fetchHeatmap,
  fetchStats,
  fetchStreaks,
  fetchToday,
  updateHabit,
  type Habit,
} from "@/lib/habitudes";

export const habitudesKeys = {
  all: ["habitudes"] as const,
  habits: () => [...habitudesKeys.all, "habits"] as const,
  today: () => [...habitudesKeys.all, "today"] as const,
  streaks: () => [...habitudesKeys.all, "streaks"] as const,
  gamification: () => [...habitudesKeys.all, "gamification"] as const,
  stats: () => [...habitudesKeys.all, "stats"] as const,
  heatmap: (habitId: number, year: number) =>
    [...habitudesKeys.all, "heatmap", habitId, year] as const,
};

export function useHabits() {
  return useQuery({ queryKey: habitudesKeys.habits(), queryFn: fetchHabits });
}
export function useToday() {
  return useQuery({ queryKey: habitudesKeys.today(), queryFn: fetchToday });
}
export function useStreaks() {
  return useQuery({ queryKey: habitudesKeys.streaks(), queryFn: fetchStreaks });
}
export function useGamification() {
  return useQuery({ queryKey: habitudesKeys.gamification(), queryFn: fetchGamification });
}
export function useHabitudesStats() {
  return useQuery({ queryKey: habitudesKeys.stats(), queryFn: fetchStats });
}
export function useHeatmap(habitId: number | null, year: number) {
  return useQuery({
    queryKey: habitudesKeys.heatmap(habitId ?? 0, year),
    queryFn: () => fetchHeatmap(habitId as number, year),
    enabled: habitId != null,
  });
}

/** Heatmap de toutes les habitudes (vue Heatmap) : habits + une heatmap par habit. */
export function useHeatmapRows(year: number) {
  return useQuery({
    queryKey: [...habitudesKeys.all, "heatmap-rows", year] as const,
    queryFn: async () => {
      const habits = await fetchHabits();
      return Promise.all(
        habits.map(async (h) => {
          const data: { date: string; valeur: number }[] = await fetchHeatmap(h.id, year);
          return { id: h.id, nom: h.nom, data };
        }),
      );
    },
  });
}

function useInvalidateAll() {
  const qc = useQueryClient();
  return () => qc.invalidateQueries({ queryKey: habitudesKeys.all });
}

export function useCheckEntry() {
  const invalidate = useInvalidateAll();
  return useMutation({
    mutationFn: (p: { habit_id: number; date: string; valeur?: number }) =>
      checkEntry(p.habit_id, p.date, p.valeur ?? 1),
    onSuccess: invalidate,
  });
}
export function useDeleteEntry() {
  const invalidate = useInvalidateAll();
  return useMutation({ mutationFn: (id: number) => deleteEntry(id), onSuccess: invalidate });
}
export function useCreateHabit() {
  const invalidate = useInvalidateAll();
  return useMutation({ mutationFn: createHabit, onSuccess: invalidate });
}
export function useUpdateHabit() {
  const invalidate = useInvalidateAll();
  return useMutation({
    mutationFn: (p: { id: number; patch: Partial<Habit> }) => updateHabit(p.id, p.patch),
    onSuccess: invalidate,
  });
}
export function useArchiveHabit() {
  const invalidate = useInvalidateAll();
  return useMutation({ mutationFn: (id: number) => archiveHabit(id), onSuccess: invalidate });
}
