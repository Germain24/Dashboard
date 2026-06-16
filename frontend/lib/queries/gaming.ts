"use client";

/** Couche TanStack Query du module Gaming. */

import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { gamingApi, type Game, type GameGoal } from "@/lib/gaming";

export const gamingKeys = {
  all: ["gaming"] as const,
  games: () => [...gamingKeys.all, "games"] as const,
  goals: (gameId: number) => [...gamingKeys.all, "goals", gameId] as const,
};

export function useGames() {
  return useQuery({ queryKey: gamingKeys.games(), queryFn: gamingApi.games });
}
export function useGameGoals(gameId: number | null) {
  return useQuery({
    queryKey: gamingKeys.goals(gameId ?? 0),
    queryFn: () => gamingApi.goals(gameId as number),
    enabled: gameId != null,
  });
}

function useInvalidateAll() {
  const qc = useQueryClient();
  return () => qc.invalidateQueries({ queryKey: gamingKeys.all });
}

export function useCreateGame() {
  const invalidate = useInvalidateAll();
  return useMutation({ mutationFn: (d: Partial<Game>) => gamingApi.createGame(d), onSuccess: invalidate });
}
export function useUpdateGame() {
  const invalidate = useInvalidateAll();
  return useMutation({
    mutationFn: (p: { id: number; patch: Partial<Game> }) => gamingApi.updateGame(p.id, p.patch),
    onSuccess: invalidate,
  });
}
export function useDeleteGame() {
  const invalidate = useInvalidateAll();
  return useMutation({ mutationFn: (id: number) => gamingApi.removeGame(id), onSuccess: invalidate });
}
export function useCreateGameGoal() {
  const invalidate = useInvalidateAll();
  return useMutation({
    mutationFn: (p: { gameId: number; data: Partial<GameGoal> }) => gamingApi.createGoal(p.gameId, p.data),
    onSuccess: invalidate,
  });
}
export function useUpdateGameGoal() {
  const invalidate = useInvalidateAll();
  return useMutation({
    mutationFn: (p: { id: number; patch: Partial<GameGoal> }) => gamingApi.updateGoal(p.id, p.patch),
    onSuccess: invalidate,
  });
}
export function useDeleteGameGoal() {
  const invalidate = useInvalidateAll();
  return useMutation({ mutationFn: (id: number) => gamingApi.removeGoal(id), onSuccess: invalidate });
}
