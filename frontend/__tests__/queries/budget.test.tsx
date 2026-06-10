import { describe, expect, it, vi } from "vitest";
import { renderHook, waitFor } from "@testing-library/react";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import type { ReactNode } from "react";

vi.mock("@/lib/budget", () => ({
  fetchTransactions: vi.fn().mockResolvedValue([]),
  fetchCategories: vi.fn().mockResolvedValue([]),
  fetchSummary: vi.fn().mockResolvedValue({ revenus: 100, depenses: -40, solde: 60 }),
  fetchEnvelopes: vi.fn().mockResolvedValue([]),
  fetchDisposable: vi.fn().mockResolvedValue({ disposable: 0 }),
  fetchCashflow: vi.fn().mockResolvedValue([]),
  fetchByCategory: vi.fn().mockResolvedValue([]),
  fetchTrend: vi.fn().mockResolvedValue([]),
  fetchRecurring: vi.fn().mockResolvedValue([]),
  fetchSavingsGoal: vi.fn().mockResolvedValue({ objectif: 0, epargne: 0, progress_pct: 0 }),
  fetchRules: vi.fn().mockResolvedValue([]),
  setSavingsGoal: vi.fn().mockResolvedValue({ montant: 200 }),
  setTransactionTags: vi.fn().mockResolvedValue({}),
  importCsv: vi.fn().mockResolvedValue({}),
  applyRules: vi.fn().mockResolvedValue({ updated: 0 }),
}));

import { budgetKeys, useBudgetSummary, useSetSavingsGoal } from "@/lib/queries/budget";

function wrapper({ children }: { children: ReactNode }) {
  const qc = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  return <QueryClientProvider client={qc}>{children}</QueryClientProvider>;
}

describe("queries/budget", () => {
  it("useBudgetSummary charge le résumé du mois", async () => {
    const { result } = renderHook(() => useBudgetSummary("2026-06"), { wrapper });
    await waitFor(() => expect(result.current.isSuccess).toBe(true));
    expect(result.current.data).toEqual({ revenus: 100, depenses: -40, solde: 60 });
  });

  it("les clés de cache intègrent le mois", () => {
    expect(budgetKeys.all).toEqual(["budget"]);
    expect(budgetKeys.summary("2026-06")).toEqual(["budget", "summary", "2026-06"]);
  });

  it("useSetSavingsGoal déclenche la mutation", async () => {
    const { result } = renderHook(() => useSetSavingsGoal(), { wrapper });
    result.current.mutate(200);
    await waitFor(() => expect(result.current.isSuccess).toBe(true));
  });
});
