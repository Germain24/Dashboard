import { describe, expect, it } from "vitest";
import {
  bucketTransactionCategory,
  buildCashflowSankey,
  compactFlowBuckets,
} from "@/lib/budget-sankey";
import type { BudgetCategory } from "@/lib/budget";
import { flattenCategoryOptions } from "@/lib/budget-categories";

const categories: BudgetCategory[] = [
  { id: 1, nom: "Dépenses", parent_id: null, couleur: "#111111" },
  { id: 2, nom: "Investissement", parent_id: 1, couleur: "#222222" },
  { id: 3, nom: "Bourse", parent_id: 2, couleur: "#333333" },
  { id: 4, nom: "PEA", parent_id: 3, couleur: "#444444" },
  { id: 5, nom: "Bourse Direct", parent_id: 4, couleur: "#555555" },
  { id: 6, nom: "Revenus", parent_id: null, couleur: "#666666" },
  { id: 7, nom: "Salaire", parent_id: 6, couleur: "#777777" },
  { id: 8, nom: "Employeur A", parent_id: 7, couleur: "#888888" },
  { id: 9, nom: "Employeur B", parent_id: 7, couleur: "#999999" },
  { id: 10, nom: "Dividendes", parent_id: 6, couleur: "#aaaaaa" },
];

describe("budget Sankey", () => {
  it("expose les chemins complets pour affecter une catégorie finale", () => {
    const options = new Map(
      flattenCategoryOptions(categories).map(({ category, label }) => [category.id, label]),
    );

    expect(options.get(5)).toBe("Dépenses › Investissement › Bourse › PEA › Bourse Direct");
    expect(options.get(8)).toBe("Revenus › Salaire › Employeur A");
  });

  it("remonte une dépense classée à sa catégorie finale vers le niveau choisi", () => {
    expect(bucketTransactionCategory(5, categories, null, "expense", 6)).toMatchObject({
      label: "Dépenses",
      categoryId: 1,
    });
    expect(bucketTransactionCategory(5, categories, 1, "expense", 6)).toMatchObject({
      label: "Investissement",
      categoryId: 2,
    });
    expect(bucketTransactionCategory(5, categories, 4, "expense", 6)).toMatchObject({
      label: "Bourse Direct",
      categoryId: 5,
    });
  });

  it("permet le même détail hiérarchique pour les revenus", () => {
    expect(bucketTransactionCategory(8, categories, 6, "income", 6)).toMatchObject({
      label: "Salaire",
      categoryId: 7,
    });
    expect(bucketTransactionCategory(8, categories, 7, "income", 6)).toMatchObject({
      label: "Employeur A",
      categoryId: 8,
    });
    expect(bucketTransactionCategory(10, categories, 7, "income", 6)).toMatchObject({
      label: "Autres revenus",
      categoryId: 6,
    });
  });

  it("ventile le revenu entre dépenses et épargne sans perdre le solde", () => {
    const flow = buildCashflowSankey(
      [{ id: "salary", label: "Salaire", value: 3000 }],
      [{ id: "housing", label: "Logement", value: 2000 }],
    );

    expect(flow.totalIncome).toBe(3000);
    expect(flow.totalExpenses).toBe(2000);
    expect(flow.targets.find((bucket) => bucket.id === "__surplus__")?.value).toBe(1000);
    expect(flow.links.reduce((sum, link) => sum + link.value, 0)).toBeCloseTo(3000);
  });

  it("ajoute les fonds antérieurs quand les sorties dépassent les revenus", () => {
    const flow = buildCashflowSankey(
      [{ id: "salary", label: "Salaire", value: 1500 }],
      [
        { id: "housing", label: "Logement", value: 1000 },
        { id: "food", label: "Nourriture", value: 1000 },
      ],
    );

    expect(flow.sources.find((bucket) => bucket.id === "__other_funds__")?.value).toBe(500);
    expect(flow.totalFlow).toBe(2000);
    expect(flow.links.reduce((sum, link) => sum + link.value, 0)).toBeCloseTo(2000);
  });

  it("regroupe les petits postes sous une ligne Autres", () => {
    const compact = compactFlowBuckets(
      [
        { id: "a", label: "A", value: 100 },
        { id: "b", label: "B", value: 50 },
        { id: "c", label: "C", value: 25 },
        { id: "d", label: "D", value: 10 },
      ],
      "Autres dépenses",
      3,
    );

    expect(compact).toHaveLength(3);
    expect(compact[2]).toMatchObject({ label: "Autres dépenses", value: 35 });
  });
});
