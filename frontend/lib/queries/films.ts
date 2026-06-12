"use client";

/** Couche TanStack Query du module Films & Séries (#541). */

import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import {
  createWatchItem,
  deleteWatchItem,
  fetchProgress,
  fetchWatchStats,
  fetchWatchlist,
  searchTmdb,
  updateProgress,
  updateWatchItem,
  type MediaType,
  type WatchItem,
  type WatchStatut,
} from "@/lib/films";

export const filmsKeys = {
  all: ["films-series"] as const,
  watchlist: (opts?: { type?: MediaType; statut?: WatchStatut }) =>
    [...filmsKeys.all, "watchlist", opts ?? {}] as const,
  search: (q: string, type: MediaType) => [...filmsKeys.all, "search", type, q] as const,
  progress: (id: number) => [...filmsKeys.all, "progress", id] as const,
  stats: () => [...filmsKeys.all, "stats"] as const,
};

export function useWatchlist(opts?: { type?: MediaType; statut?: WatchStatut }) {
  return useQuery({
    queryKey: filmsKeys.watchlist(opts),
    queryFn: () => fetchWatchlist(opts),
  });
}

export function useTmdbSearch(q: string, type: MediaType) {
  return useQuery({
    queryKey: filmsKeys.search(q, type),
    queryFn: () => searchTmdb(q, type),
    enabled: q.trim().length > 1,
  });
}

export function useSerieProgress(id: number | null) {
  return useQuery({
    queryKey: filmsKeys.progress(id ?? 0),
    queryFn: () => fetchProgress(id as number),
    enabled: id != null,
  });
}

export function useWatchStats() {
  return useQuery({ queryKey: filmsKeys.stats(), queryFn: fetchWatchStats });
}

function useInvalidateAll() {
  const qc = useQueryClient();
  return () => qc.invalidateQueries({ queryKey: filmsKeys.all });
}

export function useAddWatchItem() {
  const invalidate = useInvalidateAll();
  return useMutation({
    mutationFn: (data: Partial<WatchItem> & { titre: string }) => createWatchItem(data),
    onSuccess: invalidate,
  });
}

export function useUpdateWatchItem() {
  const invalidate = useInvalidateAll();
  return useMutation({
    mutationFn: (p: { id: number; patch: Partial<WatchItem> }) => updateWatchItem(p.id, p.patch),
    onSuccess: invalidate,
  });
}

export function useDeleteWatchItem() {
  const invalidate = useInvalidateAll();
  return useMutation({
    mutationFn: (id: number) => deleteWatchItem(id),
    onSuccess: invalidate,
  });
}

export function useUpdateProgress() {
  const invalidate = useInvalidateAll();
  return useMutation({
    mutationFn: (p: Parameters<typeof updateProgress>) => updateProgress(...p),
    onSuccess: invalidate,
  });
}
