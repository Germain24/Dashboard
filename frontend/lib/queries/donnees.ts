"use client";

/** Couche TanStack Query du module Données (#521).
 *  Les exports (downloads navigateur) restent des appels directs : pas de cache. */

import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { fetchTables, importBackup, seedDemo } from "@/lib/data";

export const donneesKeys = {
  all: ["donnees"] as const,
  tables: () => [...donneesKeys.all, "tables"] as const,
};

export function useTables() {
  return useQuery({ queryKey: donneesKeys.tables(), queryFn: fetchTables });
}

export function useImportBackup() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (p: { data: unknown; mode: "replace" | "merge" }) => importBackup(p.data, p.mode),
    // Un import touche potentiellement toutes les tables : on invalide tout le cache.
    onSuccess: () => qc.invalidateQueries(),
  });
}

export function useSeedDemo() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (force: boolean) => seedDemo(force),
    onSuccess: () => qc.invalidateQueries(),
  });
}
