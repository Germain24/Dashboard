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
  fetchForecast: vi.fn().mockResolvedValue({
    moyenne_revenus: 3000, moyenne_depenses: 2000, solde_mensuel_moyen: 1000,
    points: [{ mois: "2026-08", solde_mensuel: 1000, cumul: 1000 }],
  }),
  fetchSubscriptionAlerts: vi.fn().mockResolvedValue({
    hausses: [{ marchand: "NETFLIX.COM", montant_precedent: 15.99, montant_actuel: 18.99,
                delta: 3, delta_pct: 18.8, date: "2026-04-05", occurrences: 4, category_id: null }],
    doublons: [], nb_alertes: 1, surcout_mensuel: 3,
  }),
  fetchFire: vi.fn().mockResolvedValue({ taux_epargne_pct: 25, annees_restantes: 17.1, atteint: false }),
  fetchSavingsGoal: vi.fn().mockResolvedValue({ objectif: 0, epargne: 0, progress_pct: 0 }),
  fetchRules: vi.fn().mockResolvedValue([]),
  setSavingsGoal: vi.fn().mockResolvedValue({ montant: 200 }),
  setTransactionTags: vi.fn().mockResolvedValue({}),
  importCsv: vi.fn().mockResolvedValue({}),
  applyRules: vi.fn().mockResolvedValue({ updated: 0 }),
  fetchContracts: vi.fn().mockResolvedValue([]),
  fetchContractsSummary: vi.fn().mockResolvedValue({ cout_mensuel: 0, prochaines_echeances: [] }),
  createContract: vi.fn().mockResolvedValue({}),
  updateContract: vi.fn().mockResolvedValue({}),
  deleteContract: vi.fn().mockResolvedValue(undefined),
}));

import {
  budgetKeys, useBudgetSummary, useContractsSummary, useFire, useForecast,
  useSetSavingsGoal, useSubscriptionAlerts,
} from "@/lib/queries/budget";

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

  it("useForecast charge la prévision de trésorerie", async () => {
    const { result } = renderHook(() => useForecast(6, 6, { revenusDeltaPct: 0, depensesDeltaPct: 0 }), { wrapper });
    await waitFor(() => expect(result.current.isSuccess).toBe(true));
    expect(result.current.data?.solde_mensuel_moyen).toBe(1000);
  });

  it("useSubscriptionAlerts charge les alertes d'abonnement (#260)", async () => {
    const { result } = renderHook(() => useSubscriptionAlerts(), { wrapper });
    await waitFor(() => expect(result.current.isSuccess).toBe(true));
    expect(result.current.data?.nb_alertes).toBe(1);
    expect(result.current.data?.hausses[0].marchand).toBe("NETFLIX.COM");
  });

  it("useFire charge le rapport d'indépendance financière (#268)", async () => {
    const { result } = renderHook(() => useFire(), { wrapper });
    await waitFor(() => expect(result.current.isSuccess).toBe(true));
    expect(result.current.data?.annees_restantes).toBe(17.1);
    expect(budgetKeys.fire(12, 0.04, 0.05)).toEqual(["budget", "fire", 12, 0.04, 0.05]);
  });

  it("useContractsSummary charge le coût mensuel des contrats (#362)", async () => {
    const { result } = renderHook(() => useContractsSummary(), { wrapper });
    await waitFor(() => expect(result.current.isSuccess).toBe(true));
    expect(result.current.data).toEqual({ cout_mensuel: 0, prochaines_echeances: [] });
  });
});
