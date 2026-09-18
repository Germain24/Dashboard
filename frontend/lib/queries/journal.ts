"use client";

/** Couche TanStack Query du module Journal (#527). */

import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { journalApi, type MoodEntry } from "@/lib/journal";

export const journalKeys = {
  all: ["journal"] as const,
  entries: (from?: string, to?: string) =>
    [...journalKeys.all, "entries", from ?? "", to ?? ""] as const,
  entry: (date: string) => [...journalKeys.all, "entry", date] as const,
  trends: (days: number) => [...journalKeys.all, "trends", days] as const,
  correlations: (days: number) => [...journalKeys.all, "correlations", days] as const,
};

export function useJournalEntries(from?: string, to?: string) {
  return useQuery({
    queryKey: journalKeys.entries(from, to),
    queryFn: () => journalApi.entries(from, to),
  });
}
export function useJournalEntry(date: string) {
  return useQuery({
    queryKey: journalKeys.entry(date),
    queryFn: () => journalApi.getEntry(date),
    retry: false, // 404 attendu quand le jour n'a pas d'entrée
  });
}
export function useMoodTrends(days = 30) {
  return useQuery({ queryKey: journalKeys.trends(days), queryFn: () => journalApi.trends(days) });
}
export function useJournalCorrelations(days = 90) {
  return useQuery({
    queryKey: journalKeys.correlations(days),
    queryFn: () => journalApi.correlations(days),
  });
}

export function usePutJournalEntry() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (p: { date: string; body: Omit<MoodEntry, "id" | "date"> }) =>
      journalApi.putEntry(p.date, p.body),
    onSuccess: () => qc.invalidateQueries({ queryKey: journalKeys.all }),
  });
}
