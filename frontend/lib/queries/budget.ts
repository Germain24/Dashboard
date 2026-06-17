"use client";

/** Couche TanStack Query du module Budget (#519) — modèle : lib/queries/finance.ts. */

import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import {
  applyRules,
  fetchByCategory,
  fetchCashflow,
  fetchCategories,
  fetchDisposable,
  fetchEnvelopes,
  fetchRecurring,
  fetchRecurringProjection,
  fetchRules,
  fetchRuleSuggestions,
  learnRules,
  fetchSavingsGoal,
  fetchSummary,
  fetchSummaryComparison,
  fetchTransactions,
  fetchTrend,
  importCsv,
  setSavingsGoal,
  setTransactionTags,
} from "@/lib/budget";

export const budgetKeys = {
  all: ["budget"] as const,
  transactions: (params?: { from?: string; to?: string; category_id?: number }) =>
    [...budgetKeys.all, "transactions", params ?? {}] as const,
  categories: () => [...budgetKeys.all, "categories"] as const,
  summary: (month: string) => [...budgetKeys.all, "summary", month] as const,
  summaryCompare: (month: string) => [...budgetKeys.all, "summary-compare", month] as const,
  envelopes: (month: string) => [...budgetKeys.all, "envelopes", month] as const,
  disposable: (month: string) => [...budgetKeys.all, "disposable", month] as const,
  cashflow: (from: string, to: string) => [...budgetKeys.all, "cashflow", from, to] as const,
  byCategory: (month: string) => [...budgetKeys.all, "by-category", month] as const,
  trend: (months: number) => [...budgetKeys.all, "trend", months] as const,
  recurring: () => [...budgetKeys.all, "recurring"] as const,
  recurringProjection: () => [...budgetKeys.all, "recurring-projection"] as const,
  savingsGoal: () => [...budgetKeys.all, "savings-goal"] as const,
  rules: () => [...budgetKeys.all, "rules"] as const,
  ruleSuggestions: () => [...budgetKeys.all, "rule-suggestions"] as const,
};

export function useBudgetTransactions(params?: { from?: string; to?: string; category_id?: number }) {
  return useQuery({ queryKey: budgetKeys.transactions(params), queryFn: () => fetchTransactions(params) });
}
export function useBudgetCategories() {
  return useQuery({ queryKey: budgetKeys.categories(), queryFn: fetchCategories });
}
export function useBudgetSummary(month: string) {
  return useQuery({ queryKey: budgetKeys.summary(month), queryFn: () => fetchSummary(month) });
}
export function useBudgetComparison(month: string) {
  return useQuery({ queryKey: budgetKeys.summaryCompare(month), queryFn: () => fetchSummaryComparison(month) });
}
export function useEnvelopes(month: string) {
  return useQuery({ queryKey: budgetKeys.envelopes(month), queryFn: () => fetchEnvelopes(month) });
}
export function useDisposable(month: string) {
  return useQuery({ queryKey: budgetKeys.disposable(month), queryFn: () => fetchDisposable(month) });
}
export function useCashflow(from: string, to: string) {
  return useQuery({ queryKey: budgetKeys.cashflow(from, to), queryFn: () => fetchCashflow(from, to) });
}
export function useByCategory(month: string) {
  return useQuery({ queryKey: budgetKeys.byCategory(month), queryFn: () => fetchByCategory(month) });
}
export function useTrend(months = 6) {
  return useQuery({ queryKey: budgetKeys.trend(months), queryFn: () => fetchTrend(months) });
}
export function useRecurring() {
  return useQuery({ queryKey: budgetKeys.recurring(), queryFn: fetchRecurring });
}
export function useRecurringProjection() {
  return useQuery({ queryKey: budgetKeys.recurringProjection(), queryFn: fetchRecurringProjection });
}
export function useSavingsGoal() {
  return useQuery({ queryKey: budgetKeys.savingsGoal(), queryFn: fetchSavingsGoal });
}
export function useBudgetRules() {
  return useQuery({ queryKey: budgetKeys.rules(), queryFn: fetchRules });
}

function useInvalidateAll() {
  const qc = useQueryClient();
  return () => qc.invalidateQueries({ queryKey: budgetKeys.all });
}

export function useSetSavingsGoal() {
  const invalidate = useInvalidateAll();
  return useMutation({ mutationFn: (montant: number) => setSavingsGoal(montant), onSuccess: invalidate });
}
export function useSetTransactionTags() {
  const invalidate = useInvalidateAll();
  return useMutation({
    mutationFn: (p: { id: number; tags: string[] }) => setTransactionTags(p.id, p.tags),
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
