import { describe, expect, it, vi } from "vitest";
import { fireEvent, render, screen, within } from "@testing-library/react";

const mocks = vi.hoisted(() => ({
  setCategory: vi.fn(),
  setTags: vi.fn(),
  importCsv: vi.fn(),
  learnRules: vi.fn(),
  createCategory: vi.fn(),
  updateCategory: vi.fn(),
}));

const fixture = vi.hoisted(() => ({
  transactions: [
    {
      id: 42,
      marchand: "Bourse Direct",
      description: "Virement PEA",
      montant: -250,
      date: "2026-09-12",
      compte: "banquepopulaire-debit",
      category_id: 3,
      tags: ["PEA"],
    },
  ],
  categories: [
    { id: 1, nom: "Dépenses", parent_id: null, couleur: "#ef4444" },
    { id: 2, nom: "Investissement", parent_id: 1, couleur: "#f97316" },
    { id: 3, nom: "Bourse", parent_id: 2, couleur: "#f59e0b" },
  ],
}));

vi.mock("@/lib/queries/budget", () => ({
  useBudgetTransactions: () => ({ data: fixture.transactions, isLoading: false }),
  useBudgetCategories: () => ({ data: fixture.categories, isLoading: false }),
  useImportCsv: () => ({ mutate: mocks.importCsv, isPending: false }),
  useSetTransactionTags: () => ({ mutate: mocks.setTags, isPending: false }),
  useRuleSuggestions: () => ({ data: { suggestions: [] } }),
  useLearnRules: () => ({ mutate: mocks.learnRules, isPending: false }),
  useSetTransactionCategory: () => ({ mutate: mocks.setCategory, isPending: false }),
  useCreateBudgetCategory: () => ({ mutate: mocks.createCategory, isPending: false }),
  useUpdateBudgetCategory: () => ({ mutate: mocks.updateCategory, isPending: false }),
}));

import TransactionsTab from "@/components/budget/TransactionsTab";

describe("TransactionsTab sur mobile", () => {
  it("présente une carte compacte avec catégorie hiérarchique et actions conservées", () => {
    render(<TransactionsTab />);

    const mobileList = screen.getByTestId("transactions-mobile-list");
    const card = within(mobileList).getByTestId("transaction-mobile-card-42");
    expect(mobileList).toHaveClass("md:hidden");
    expect(card).toHaveTextContent("Bourse Direct");
    expect(card).toHaveTextContent("Banque Populaire");
    expect(card).toHaveTextContent("Dépenses › Investissement › Bourse");
    expect(
      within(card).getByRole("combobox", { name: "Ajouter un tag à Bourse Direct" }),
    ).toBeInTheDocument();

    fireEvent.click(
      within(card).getByRole("button", { name: "Modifier la catégorie de Bourse Direct" }),
    );

    const categorySelect = within(card).getByRole("combobox", {
      name: "Catégorie de Bourse Direct",
    });
    expect(
      within(categorySelect).getByRole("option", {
        name: "Dépenses › Investissement › Bourse",
      }),
    ).toBeInTheDocument();

    fireEvent.change(categorySelect, { target: { value: "2" } });
    expect(mocks.setCategory).toHaveBeenCalledWith(
      { id: 42, category_id: 2 },
      expect.objectContaining({ onSuccess: expect.any(Function) }),
    );
  });
});
