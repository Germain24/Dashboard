"use client";

/** Couche TanStack Query du module Cuisine (#520) — modèle : lib/queries/finance.ts. */

import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import {
  addPantryItem,
  createRecipe,
  deletePantryItem,
  fetchAliments,
  fetchDailyTargets,
  fetchFavorites,
  fetchMealPlan,
  fetchPantry,
  fetchRecipe,
  fetchRecipeNote,
  fetchRecipes,
  fetchShoppingPreview,
  generateMealPlan,
  importFromUrl,
  setRecipeNote,
  toggleFavorite,
  updatePantryItem,
  type PantryItemInput,
  type RecipeInput,
} from "@/lib/cuisine";

export const cuisineKeys = {
  all: ["cuisine"] as const,
  recipes: (search?: string, ingredient?: string) =>
    [...cuisineKeys.all, "recipes", search ?? "", ingredient ?? ""] as const,
  recipe: (id: number) => [...cuisineKeys.all, "recipe", id] as const,
  recipeNote: (id: number) => [...cuisineKeys.all, "recipe-note", id] as const,
  aliments: () => [...cuisineKeys.all, "aliments"] as const,
  dailyTargets: () => [...cuisineKeys.all, "daily-targets"] as const,
  mealPlan: (week: string) => [...cuisineKeys.all, "meal-plan", week] as const,
  shoppingPreview: (week: string, jours?: number[]) =>
    [...cuisineKeys.all, "shopping-preview", week, jours ?? []] as const,
  pantry: () => [...cuisineKeys.all, "pantry"] as const,
  favorites: () => [...cuisineKeys.all, "favorites"] as const,
};

export function useRecipes(search?: string, ingredient?: string) {
  return useQuery({
    queryKey: cuisineKeys.recipes(search, ingredient),
    queryFn: () => fetchRecipes(search, ingredient),
  });
}
export function useRecipe(id: number | null) {
  return useQuery({
    queryKey: cuisineKeys.recipe(id ?? 0),
    queryFn: () => fetchRecipe(id as number),
    enabled: id != null,
  });
}
export function useRecipeNote(id: number | null) {
  return useQuery({
    queryKey: cuisineKeys.recipeNote(id ?? 0),
    queryFn: () => fetchRecipeNote(id as number),
    enabled: id != null,
  });
}
export function useAliments() {
  return useQuery({ queryKey: cuisineKeys.aliments(), queryFn: fetchAliments });
}
export function useDailyTargets() {
  return useQuery({ queryKey: cuisineKeys.dailyTargets(), queryFn: fetchDailyTargets });
}
export function useMealPlan(week: string) {
  return useQuery({ queryKey: cuisineKeys.mealPlan(week), queryFn: () => fetchMealPlan(week) });
}
export function useShoppingPreview(week: string, jours?: number[]) {
  return useQuery({
    queryKey: cuisineKeys.shoppingPreview(week, jours),
    queryFn: () => fetchShoppingPreview(week, jours),
  });
}
export function usePantry() {
  return useQuery({ queryKey: cuisineKeys.pantry(), queryFn: fetchPantry });
}
export function useCuisineFavorites() {
  return useQuery({ queryKey: cuisineKeys.favorites(), queryFn: fetchFavorites });
}

function useInvalidateAll() {
  const qc = useQueryClient();
  return () => qc.invalidateQueries({ queryKey: cuisineKeys.all });
}

export function useCreateRecipe() {
  const invalidate = useInvalidateAll();
  return useMutation({ mutationFn: (data: RecipeInput) => createRecipe(data), onSuccess: invalidate });
}
export function useImportFromUrl() {
  const invalidate = useInvalidateAll();
  return useMutation({ mutationFn: (url: string) => importFromUrl(url), onSuccess: invalidate });
}
export function useGenerateMealPlan() {
  const invalidate = useInvalidateAll();
  return useMutation({
    mutationFn: (p: { semaine: string; cibles: Record<string, number> }) =>
      generateMealPlan(p.semaine, p.cibles),
    onSuccess: invalidate,
  });
}
export function useAddPantryItem() {
  const invalidate = useInvalidateAll();
  return useMutation({ mutationFn: (d: PantryItemInput) => addPantryItem(d), onSuccess: invalidate });
}
export function useUpdatePantryItem() {
  const invalidate = useInvalidateAll();
  return useMutation({
    mutationFn: (p: { id: number; patch: Partial<PantryItemInput> }) => updatePantryItem(p.id, p.patch),
    onSuccess: invalidate,
  });
}
export function useDeletePantryItem() {
  const invalidate = useInvalidateAll();
  return useMutation({ mutationFn: (id: number) => deletePantryItem(id), onSuccess: invalidate });
}
export function useToggleFavorite() {
  const invalidate = useInvalidateAll();
  return useMutation({ mutationFn: (id: number) => toggleFavorite(id), onSuccess: invalidate });
}
export function useSetRecipeNote() {
  const invalidate = useInvalidateAll();
  return useMutation({
    mutationFn: (p: { id: number; note: string }) => setRecipeNote(p.id, p.note),
    onSuccess: invalidate,
  });
}
