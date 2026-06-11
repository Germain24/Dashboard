"use client";

/** Couche TanStack Query du module Musique (#529).
 *  Le polling de progression du classement reste piloté par le composant. */

import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { musiqueApi } from "@/lib/musique";

export const musiqueKeys = {
  all: ["musique"] as const,
  tracks: (q: string, ambiance: string) => [...musiqueKeys.all, "tracks", q, ambiance] as const,
  ambiances: () => [...musiqueKeys.all, "ambiances"] as const,
  playlist: (a: string) => [...musiqueKeys.all, "playlist", a] as const,
  reco: (a: string) => [...musiqueKeys.all, "reco", a] as const,
  discovery: (a: string) => [...musiqueKeys.all, "discovery", a] as const,
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
    mutationFn: (p: { id: number; ambiance: string }) => musiqueApi.removeAmbiance(p.id, p.ambiance),
    onSuccess: invalidate,
  });
}
