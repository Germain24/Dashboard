import { describe, expect, it } from "vitest";
import {
  categoryDescendantIds,
  categoryPathLabel,
  flattenCategoryOptions,
} from "@/lib/budget-categories";
import type { BudgetCategory } from "@/lib/budget";

const categories: BudgetCategory[] = [
  { id: 1, nom: "Logement", parent_id: null, couleur: "#111111" },
  { id: 2, nom: "Assurances", parent_id: 1, couleur: "#222222" },
  { id: 3, nom: "Habitation", parent_id: 2, couleur: "#333333" },
  { id: 4, nom: "Revenus", parent_id: null, couleur: "#444444" },
];

describe("budget category tree", () => {
  it("filtre récursivement les catégories descendantes", () => {
    expect([...categoryDescendantIds(categories, 1)]).toEqual([1, 2, 3]);
    expect(categoryPathLabel(categories, 3)).toBe("Logement › Assurances › Habitation");
  });

  it("aplatit les catégories en conservant leur chemin lisible", () => {
    expect(flattenCategoryOptions(categories).map((option) => option.label)).toEqual([
      "Logement",
      "Logement › Assurances",
      "Logement › Assurances › Habitation",
      "Revenus",
    ]);
  });
});
