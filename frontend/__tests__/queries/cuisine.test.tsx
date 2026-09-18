import { describe, expect, it, vi } from "vitest";
import { renderHook, waitFor } from "@testing-library/react";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import type { ReactNode } from "react";

vi.mock("@/lib/cuisine", () => ({
  fetchRecipes: vi.fn().mockResolvedValue([{ id: 1, titre: "Chili" }]),
  fetchRecipe: vi.fn().mockResolvedValue({ id: 1, titre: "Chili", ingredients: [] }),
  fetchRecipeNote: vi.fn().mockResolvedValue(""),
  fetchAliments: vi.fn().mockResolvedValue([]),
  fetchDailyTargets: vi.fn().mockResolvedValue({}),
  fetchMealPlan: vi.fn().mockResolvedValue([]),
  fetchShoppingPreview: vi.fn().mockResolvedValue([]),
  fetchPantry: vi.fn().mockResolvedValue([]),
  fetchFavorites: vi.fn().mockResolvedValue({ favorites: [] }),
  createRecipe: vi.fn().mockResolvedValue({ id: 2 }),
  importFromUrl: vi.fn().mockResolvedValue({ id: 3 }),
  generateMealPlan: vi.fn().mockResolvedValue([]),
  addPantryItem: vi.fn().mockResolvedValue({ id: 1 }),
  updatePantryItem: vi.fn().mockResolvedValue({ id: 1 }),
  deletePantryItem: vi.fn().mockResolvedValue(undefined),
  toggleFavorite: vi.fn().mockResolvedValue({ is_favorite: true, favorites: [1] }),
  setRecipeNote: vi.fn().mockResolvedValue(undefined),
}));

import { cuisineKeys, useRecipes, useToggleFavorite } from "@/lib/queries/cuisine";

function wrapper({ children }: { children: ReactNode }) {
  const qc = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  return <QueryClientProvider client={qc}>{children}</QueryClientProvider>;
}

describe("queries/cuisine", () => {
  it("useRecipes charge les recettes", async () => {
    const { result } = renderHook(() => useRecipes(), { wrapper });
    await waitFor(() => expect(result.current.isSuccess).toBe(true));
    expect(result.current.data).toEqual([{ id: 1, titre: "Chili" }]);
  });

  it("les clés de cache intègrent la recherche", () => {
    expect(cuisineKeys.all).toEqual(["cuisine"]);
    expect(cuisineKeys.recipes("chili")).toEqual(["cuisine", "recipes", "chili", ""]);
  });

  it("useToggleFavorite déclenche la mutation", async () => {
    const { result } = renderHook(() => useToggleFavorite(), { wrapper });
    result.current.mutate(1);
    await waitFor(() => expect(result.current.isSuccess).toBe(true));
  });
});
