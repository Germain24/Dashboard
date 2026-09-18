"use client";

/** Couche TanStack Query du module Musique (#529).
 *  La progression du classement arrive par le canal temps réel global. */

import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { musiqueApi } from "@/lib/musique";

export const musiqueKeys = {
  all: ["musique"] as const,
  tracks: (q: string, ambiance: string) => [...musiqueKeys.all, "tracks", q, ambiance] as const,
  ambiances: () => [...musiqueKeys.all, "ambiances"] as const,
  playlist: (a: string) => [...musiqueKeys.all, "playlist", a] as const,
  reco: (a: string) => [...musiqueKeys.all, "reco", a] as const,
  discovery: (a: string) => [...musiqueKeys.all, "discovery", a] as const,
  quality: () => [...musiqueKeys.all, "quality"] as const,
  walkmanSyncStatus: () => [...musiqueKeys.all, "walkman-sync-status"] as const,
};

export function useTracks(q = "", ambiance = "") {
  return useQuery({
    queryKey: musiqueKeys.tracks(q, ambiance),
    queryFn: () => musiqueApi.tracks(q, ambiance),
  });
}
export function useAmbiances() {
  return useQuery({ queryKey: musiqueKeys.ambiances(), queryFn: musiqueApi.ambiances });
}
export function usePlaylist(ambiance: string | null) {
  return useQuery({
    queryKey: musiqueKeys.playlist(ambiance ?? ""),
    queryFn: () => musiqueApi.playlist(ambiance as string),
    enabled: !!ambiance,
  });
}
export function usePlaylistReco(ambiance: string | null) {
  return useQuery({
    queryKey: musiqueKeys.reco(ambiance ?? ""),
    queryFn: () => musiqueApi.reco(ambiance as string),
    enabled: !!ambiance,
  });
}
export function useDiscovery(ambiance: string | null) {
  return useQuery({
    queryKey: musiqueKeys.discovery(ambiance ?? ""),
    queryFn: () => musiqueApi.discovery(ambiance as string),
    enabled: !!ambiance,
  });
}

export function useQuality() {
  return useQuery({ queryKey: musiqueKeys.quality(), queryFn: musiqueApi.quality });
}

export function useWalkmanSyncStatus() {
  return useQuery({
    queryKey: musiqueKeys.walkmanSyncStatus(),
    queryFn: musiqueApi.walkmanSyncStatus,
    refetchInterval: (query) => (query.state.data?.active ? 2_000 : false),
  });
}

export function useStartWalkmanSync() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: musiqueApi.startWalkmanSync,
    onSuccess: () => qc.invalidateQueries({ queryKey: musiqueKeys.walkmanSyncStatus() }),
  });
}

export function useSetQobuzAvailable() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (p: { id: number; available: boolean | null }) =>
      musiqueApi.setQobuzAvailable(p.id, p.available),
    onSuccess: () => qc.invalidateQueries({ queryKey: musiqueKeys.quality() }),
  });
}

function useInvalidateAll() {
  const qc = useQueryClient();
  return () => qc.invalidateQueries({ queryKey: musiqueKeys.all });
}

export function useScanLibrary() {
  const invalidate = useInvalidateAll();
  return useMutation({ mutationFn: () => musiqueApi.scan(), onSuccess: invalidate });
}
export function useClassify() {
  return useMutation({ mutationFn: () => musiqueApi.classify() });
}
export function useResetClassify() {
  const invalidate = useInvalidateAll();
  return useMutation({
    mutationFn: (tout: boolean = false) => musiqueApi.resetClassify(tout),
    onSuccess: invalidate,
  });
}
export function useAddAmbiance() {
  const invalidate = useInvalidateAll();
  return useMutation({
    mutationFn: (p: { id: number; ambiance: string }) => musiqueApi.addAmbiance(p.id, p.ambiance),
    onSuccess: invalidate,
  });
}
export function useRemoveAmbiance() {
  const invalidate = useInvalidateAll();
  return useMutation({
    mutationFn: (p: { id: number; ambiance: string }) =>
      musiqueApi.removeAmbiance(p.id, p.ambiance),
    onSuccess: invalidate,
  });
}
