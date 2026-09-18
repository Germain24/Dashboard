"use client";

/** Couche TanStack Query du module Budget (#519) — modèle : lib/queries/finance.ts. */

import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { financeKeys } from "@/lib/queries/finance";
import {
  applyRules,
  createBudgetCategory,
  createContract,
  deleteContract,
  fetchByCategory,
  fetchByTag,
  fetchCashflow,
  fetchCategories,
  fetchContracts,
  fetchContractsSummary,
  fetchDisposable,
  fetchEnvelopes,
  fetchCategoryShare,
  fetchForecast,
  fetchFire,
  fetchRecurring,
  fetchRecurringProjection,
  fetchRollingSummary,
  fetchSubscriptionAlerts,
  fetchRules,
  fetchRuleSuggestions,
  learnRules,
  fetchSavingsGoal,
  fetchSummary,
  fetchSummaryComparison,
  fetchTransactions,
  fetchInvestmentFlows,
  fetchTrend,
  importCsv,
  setSavingsGoal,
  setTransactionCategory,
  setTransactionTags,
  updateContract,
  updateBudgetCategory,
  type Contract,
} from "@/lib/budget";

export const budgetKeys = {
  all: ["budget"] as const,
  transactions: (params?: { from?: string; to?: string; category_id?: number }) =>
    [...budgetKeys.all, "transactions", params ?? {}] as const,
  investmentFlows: () => [...budgetKeys.all, "investment-flows"] as const,
  categories: () => [...budgetKeys.all, "categories"] as const,
  summary: (month: string) => [...budgetKeys.all, "summary", month] as const,
  summaryCompare: (month: string) => [...budgetKeys.all, "summary-compare", month] as const,
  envelopes: (month: string) => [...budgetKeys.all, "envelopes", month] as const,
  disposable: (month: string) => [...budgetKeys.all, "disposable", month] as const,
  cashflow: (from: string, to: string) => [...budgetKeys.all, "cashflow", from, to] as const,
  byCategory: (month: string) => [...budgetKeys.all, "by-category", month] as const,
  byTag: (days: number) => [...budgetKeys.all, "by-tag", days] as const,
  trend: (months: number) => [...budgetKeys.all, "trend", months] as const,
  rollingSummary: (days: number) => [...budgetKeys.all, "rolling-summary", days] as const,
  categoryShare: (days: number, window: number) =>
    [...budgetKeys.all, "category-share", days, window] as const,
  forecast: (
    monthsAhead: number,
    historyMonths: number,
    revenusDeltaPct: number,
    depensesDeltaPct: number,
  ) =>
    [
      ...budgetKeys.all,
      "forecast",
      monthsAhead,
      historyMonths,
      revenusDeltaPct,
      depensesDeltaPct,
    ] as const,
  recurring: () => [...budgetKeys.all, "recurring"] as const,
  recurringProjection: () => [...budgetKeys.all, "recurring-projection"] as const,
  recurringAlerts: () => [...budgetKeys.all, "recurring-alerts"] as const,
  fire: (months: number, tauxRetrait: number, rendementReel: number) =>
    [...budgetKeys.all, "fire", months, tauxRetrait, rendementReel] as const,
  savingsGoal: () => [...budgetKeys.all, "savings-goal"] as const,
  rules: () => [...budgetKeys.all, "rules"] as const,
  ruleSuggestions: () => [...budgetKeys.all, "rule-suggestions"] as const,
  contracts: (statut?: string) => [...budgetKeys.all, "contracts", statut ?? ""] as const,
  contractsSummary: () => [...budgetKeys.all, "contracts-summary"] as const,
};

export function useBudgetTransactions(params?: {
  from?: string;
  to?: string;
  category_id?: number;
}) {
  return useQuery({
    queryKey: budgetKeys.transactions(params),
    queryFn: ({ signal }) => fetchTransactions(params, signal),
  });
}
export function useBudgetInvestmentFlows() {
  return useQuery({
    queryKey: budgetKeys.investmentFlows(),
    queryFn: ({ signal }) => fetchInvestmentFlows(undefined, signal),
  });
}
export function useBudgetCategories() {
  return useQuery({
    queryKey: budgetKeys.categories(),
    queryFn: ({ signal }) => fetchCategories(signal),
  });
}
export function useBudgetSummary(month: string) {
  return useQuery({
    queryKey: budgetKeys.summary(month),
    queryFn: ({ signal }) => fetchSummary(month, signal),
  });
}
export function useBudgetComparison(month: string) {
  return useQuery({
    queryKey: budgetKeys.summaryCompare(month),
    queryFn: () => fetchSummaryComparison(month),
  });
}
export function useEnvelopes(month: string) {
  return useQuery({ queryKey: budgetKeys.envelopes(month), queryFn: () => fetchEnvelopes(month) });
}
export function useDisposable(month: string) {
  return useQuery({
    queryKey: budgetKeys.disposable(month),
    queryFn: () => fetchDisposable(month),
  });
}
export function useCashflow(from: string, to: string) {
  return useQuery({
    queryKey: budgetKeys.cashflow(from, to),
    queryFn: () => fetchCashflow(from, to),
  });
}
export function useByCategory(month: string) {
  return useQuery({
    queryKey: budgetKeys.byCategory(month),
    queryFn: () => fetchByCategory(month),
  });
}
export function useByTag(days = 365) {
  return useQuery({ queryKey: budgetKeys.byTag(days), queryFn: () => fetchByTag(days) });
}
export function useTrend(months = 6) {
  return useQuery({ queryKey: budgetKeys.trend(months), queryFn: () => fetchTrend(months) });
}
export function useRollingSummary(days = 30) {
  return useQuery({
    queryKey: budgetKeys.rollingSummary(days),
    queryFn: () => fetchRollingSummary(days),
  });
}
export function useCategoryShare(days = 180, window = 30) {
  return useQuery({
    queryKey: budgetKeys.categoryShare(days, window),
    queryFn: () => fetchCategoryShare(days, window),
  });
}
export function useForecast(
  monthsAhead = 6,
  historyMonths = 6,
  scenario?: { revenusDeltaPct?: number; depensesDeltaPct?: number },
) {
  const revenusDeltaPct = scenario?.revenusDeltaPct ?? 0;
  const depensesDeltaPct = scenario?.depensesDeltaPct ?? 0;
  return useQuery({
    queryKey: budgetKeys.forecast(monthsAhead, historyMonths, revenusDeltaPct, depensesDeltaPct),
    queryFn: () => fetchForecast(monthsAhead, historyMonths, { revenusDeltaPct, depensesDeltaPct }),
  });
}
export function useRecurring() {
  return useQuery({ queryKey: budgetKeys.recurring(), queryFn: fetchRecurring });
}
export function useRecurringProjection() {
  return useQuery({
    queryKey: budgetKeys.recurringProjection(),
    queryFn: fetchRecurringProjection,
  });
}
export function useSubscriptionAlerts() {
  return useQuery({ queryKey: budgetKeys.recurringAlerts(), queryFn: fetchSubscriptionAlerts });
}
export function useFire(months = 12, tauxRetrait = 0.04, rendementReel = 0.05) {
  return useQuery({
    queryKey: budgetKeys.fire(months, tauxRetrait, rendementReel),
    queryFn: () => fetchFire(months, tauxRetrait, rendementReel),
  });
}
export function useSavingsGoal() {
  return useQuery({ queryKey: budgetKeys.savingsGoal(), queryFn: fetchSavingsGoal });
}
export function useBudgetRules() {
  return useQuery({ queryKey: budgetKeys.rules(), queryFn: fetchRules });
}

function useInvalidateAll() {
  const qc = useQueryClient();
  return () => {
    void qc.invalidateQueries({ queryKey: budgetKeys.all });
    // Un import de relevé (PDF Desjardins, Wise…) met à jour account_balances.json,
    // qui alimente les lignes "auto" du Patrimoine — sans ça le total y reste figé
    // jusqu'au prochain rechargement de page.
    void qc.invalidateQueries({ queryKey: financeKeys.all });
  };
}

export function useSetSavingsGoal() {
  const invalidate = useInvalidateAll();
  return useMutation({
    mutationFn: (montant: number) => setSavingsGoal(montant),
    onSuccess: invalidate,
  });
}
export function useSetTransactionTags() {
  const invalidate = useInvalidateAll();
  return useMutation({
    mutationFn: (p: { id: number; tags: string[] }) => setTransactionTags(p.id, p.tags),
    onSuccess: invalidate,
  });
}
export function useSetTransactionCategory() {
  const invalidate = useInvalidateAll();
  return useMutation({
    mutationFn: (p: { id: number; category_id: number | null }) =>
      setTransactionCategory(p.id, p.category_id),
    onSuccess: invalidate,
  });
}
export function useCreateBudgetCategory() {
  const invalidate = useInvalidateAll();
  return useMutation({
    mutationFn: (data: { nom: string; parent_id: number | null; couleur?: string }) =>
      createBudgetCategory(data),
    onSuccess: invalidate,
  });
}
export function useUpdateBudgetCategory() {
  const invalidate = useInvalidateAll();
  return useMutation({
    mutationFn: (data: { id: number; nom: string; parent_id: number | null; couleur?: string }) => {
      const { id, ...category } = data;
      return updateBudgetCategory(id, category);
    },
    onSuccess: invalidate,
  });
}
export function useImportCsv() {
  const invalidate = useInvalidateAll();
  return useMutation({
    mutationFn: (p: { file: File; compte?: string }) => importCsv(p.file, p.compte),
    onSuccess: invalidate,
  });
}
export function useApplyRules() {
  const invalidate = useInvalidateAll();
  return useMutation({ mutationFn: () => applyRules(), onSuccess: invalidate });
}
export function useRuleSuggestions() {
  return useQuery({ queryKey: budgetKeys.ruleSuggestions(), queryFn: fetchRuleSuggestions });
}
export function useLearnRules() {
  const invalidate = useInvalidateAll();
  return useMutation({ mutationFn: () => learnRules(), onSuccess: invalidate });
}

// Suivi manuel des abonnements/contrats (#362)
export function useContracts(statut?: string) {
  return useQuery({
    queryKey: budgetKeys.contracts(statut),
    queryFn: () => fetchContracts(statut),
  });
}
export function useContractsSummary() {
  return useQuery({ queryKey: budgetKeys.contractsSummary(), queryFn: fetchContractsSummary });
}
export function useCreateContract() {
  const invalidate = useInvalidateAll();
  return useMutation({
    mutationFn: (data: {
      nom: string;
      categorie: string;
      montant: number;
      periodicite: string;
      date_echeance?: string | null;
      notes?: string;
    }) => createContract(data),
    onSuccess: invalidate,
  });
}
export function useUpdateContract() {
  const invalidate = useInvalidateAll();
  return useMutation({
    mutationFn: (p: { id: number; patch: Partial<Contract> }) => updateContract(p.id, p.patch),
    onSuccess: invalidate,
  });
}
export function useDeleteContract() {
  const invalidate = useInvalidateAll();
  return useMutation({
    mutationFn: (id: number) => deleteContract(id),
    onSuccess: invalidate,
  });
}
