"use client";

/**
 * Couche TanStack Query pour le module Finance — cache, retries, invalidation.
 *
 * Référence d'adoption : les composants Finance peuvent remplacer leurs
 * useEffect/fetch manuels par ces hooks. Le client bas niveau reste
 * `financeApi` (lib/finance.ts) ; TanStack Query ajoute le cache et
 * l'invalidation automatique après mutation.
 */

import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import {
  financeApi,
  type PositionCreate,
  type TransactionCreate,
} from "@/lib/finance";

/** Clés de cache centralisées (évite les chaînes en dur dispersées). */
export const financeKeys = {
  all: ["finance"] as const,
  portfolio: () => [...financeKeys.all, "portfolio"] as const,
  perf: () => [...financeKeys.all, "perf"] as const,
  positions: () => [...financeKeys.all, "positions"] as const,
  risk: () => [...financeKeys.all, "risk"] as const,
  transactions: (ticker?: string) =>
    [...financeKeys.all, "transactions", ticker ?? "all"] as const,
  history: (days: number) => [...financeKeys.all, "history", days] as const,
};

export function usePortfolio() {
  return useQuery({ queryKey: financeKeys.portfolio(), queryFn: () => financeApi.portfolio() });
}

export function usePerf() {
  return useQuery({ queryKey: financeKeys.perf(), queryFn: () => financeApi.perf() });
}

export function useRisk() {
  return useQuery({ queryKey: financeKeys.risk(), queryFn: () => financeApi.risk() });
}

export function useHistory(days = 365) {
  return useQuery({ queryKey: financeKeys.history(days), queryFn: () => financeApi.history(days) });
}

export function useTransactions(ticker?: string) {
  return useQuery({
    queryKey: financeKeys.transactions(ticker),
    queryFn: () => financeApi.transactions(ticker),
  });
}

export function usePositions() {
  return useQuery({ queryKey: financeKeys.positions(), queryFn: () => financeApi.positionsList() });
}

/** Création de transaction + invalidation du cache lié. */
export function useCreateTransaction() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (tx: TransactionCreate) => financeApi.createTransaction(tx),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: financeKeys.all });
    },
  });
}

/** Upsert position + invalidation. */
export function useCreatePosition() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (p: PositionCreate) => financeApi.positionCreate(p),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: financeKeys.all });
    },
  });
}
