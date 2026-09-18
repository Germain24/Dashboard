"use client";

import { useState } from "react";
import type { CategorySpend } from "@/lib/budget";
import {
  useBudgetCategories,
  useByCategory,
  useByTag,
  useCategoryShare,
  useEnvelopes,
  useForecast,
  useRecurring,
  useRecurringProjection,
  useSavingsGoal,
  useSetSavingsGoal,
  useSubscriptionAlerts,
  useTrend,
  useRollingSummary,
} from "@/lib/queries/budget";

function valueOr<T>(value: T | undefined, fallback: T): T {
  return value ?? fallback;
}

function arrayOrEmpty<T>(value: T[] | undefined): T[] {
  return Array.isArray(value) ? value : [];
}

function loading(...states: boolean[]) {
  return states.some(Boolean);
}

const GROCERY_MARKERS = ["épicerie", "epicerie", "courses", "alimentation", "cuisine", "supermarch", "grocery"];

function groceryTotal(rows: CategorySpend[]) {
  return rows
    .filter((row) => GROCERY_MARKERS.some((marker) => row.nom.toLowerCase().includes(marker)))
    .reduce((sum, row) => sum + row.montant, 0);
}

export function useBudgetMonthData() {
  const [goalInput, setGoalInput] = useState("");
  const [revenusDeltaPct, setRevenusDeltaPct] = useState(0);
  const [depensesDeltaPct, setDepensesDeltaPct] = useState(0);
  const [periodMonths, setPeriodMonths] = useState(12);
  const month = new Date().toISOString().slice(0, 7);

  const rollingQ = useRollingSummary(30);
  const categoryShareQ = useCategoryShare(periodMonths * 31, 30);
  const byTagQ = useByTag(periodMonths * 31);
  const envelopesQ = useEnvelopes(month);
  const categoriesQ = useBudgetCategories();
  const byCatQ = useByCategory(month);
  const trendQ = useTrend(periodMonths);
  const recurringQ = useRecurring();
  const projectionQ = useRecurringProjection();
  const alertsQ = useSubscriptionAlerts();
  const savingsQ = useSavingsGoal();
  const forecastQ = useForecast(6, 6, { revenusDeltaPct, depensesDeltaPct });
  const setGoalMutation = useSetSavingsGoal();

  const rolling = valueOr(rollingQ.data, { revenus: 0, depenses: 0, solde: 0, debut: "", fin: "", jours: 30 });
  const categoryShare = valueOr(categoryShareQ.data, { categories: [], points: [] });
  const byTag = arrayOrEmpty(byTagQ.data);
  const envelopes = arrayOrEmpty(envelopesQ.data);
  const categories = arrayOrEmpty(categoriesQ.data);
  const byCat = arrayOrEmpty(byCatQ.data);
  const trend = arrayOrEmpty(trendQ.data);
  const recurring = arrayOrEmpty(recurringQ.data);
  const savings = valueOr(savingsQ.data, null);
  const isLoading = loading(
    rollingQ.isLoading,
    categoryShareQ.isLoading,
    envelopesQ.isLoading,
    categoriesQ.isLoading,
    byCatQ.isLoading,
    trendQ.isLoading,
    recurringQ.isLoading,
    savingsQ.isLoading,
  );
  const saveGoal = () => {
    const amount = parseFloat(goalInput);
    if (!Number.isFinite(amount) || amount < 0) return;
    setGoalMutation.mutate(amount, { onSuccess: () => setGoalInput("") });
  };
  const categoryName = (id: number) => categories.find((category) => category.id === id)?.nom ?? `#${id}`;
  return {
    month,
    goalInput,
    setGoalInput,
    revenusDeltaPct,
    setRevenusDeltaPct,
    depensesDeltaPct,
    setDepensesDeltaPct,
    periodMonths,
    setPeriodMonths,
    rolling,
    categoryShare,
    byTag,
    envelopes,
    byCat,
    groceryCost: groceryTotal(byCat),
    trend,
    recurring,
    projection: projectionQ.data ?? null,
    alerts: alertsQ.data,
    forecast: forecastQ.data ?? null,
    savings,
    isLoading,
    saveGoal,
    categoryName,
  };
}
