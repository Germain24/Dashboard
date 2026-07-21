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
  type PriceAlertCreate,
  type PriceAlertPatch,
  type TransactionCreate,
} from "@/lib/finance";

/** Clés de cache centralisées (évite les chaînes en dur dispersées). */
export const financeKeys = {
  all: ["finance"] as const,
  portfolio: () => [...financeKeys.all, "portfolio"] as const,
  perf: () => [...financeKeys.all, "perf"] as const,
  snapshot: () => [...financeKeys.all, "snapshot"] as const,
  benchmarks: () => [...financeKeys.all, "benchmarks"] as const,
  state: () => [...financeKeys.all, "state"] as const,
  settings: () => [...financeKeys.all, "settings"] as const,
  positions: () => [...financeKeys.all, "positions"] as const,
  risk: () => [...financeKeys.all, "risk"] as const,
  transactions: (ticker?: string) => [...financeKeys.all, "transactions", ticker ?? "all"] as const,
  history: (days: number) => [...financeKeys.all, "history", days] as const,
  alerts: () => [...financeKeys.all, "alerts"] as const,
  alertsStatus: () => [...financeKeys.all, "alerts-status"] as const,
};

export function usePortfolio() {
  return useQuery({ queryKey: financeKeys.portfolio(), queryFn: () => financeApi.portfolio() });
}

export function usePerf() {
  return useQuery({ queryKey: financeKeys.perf(), queryFn: () => financeApi.perf() });
}

export function useSnapshot() {
  return useQuery({
    queryKey: financeKeys.snapshot(),
    queryFn: () => financeApi.snapshot(),
  });
}

export function useBenchmarks() {
  return useQuery({
    queryKey: financeKeys.benchmarks(),
    queryFn: () => financeApi.benchmarks(),
    staleTime: 4 * 60 * 60 * 1000,
    refetchInterval: (query) => {
      const data = query.state.data;
      const cw8 = data?.find((item) => item.ticker === "CW8.PA");
      const incomplete = !cw8 || cw8.serie.length < 2;
      return incomplete && query.state.dataUpdateCount < 12 ? 5_000 : false;
    },
  });
}

export function usePortfolioState() {
  return useQuery({
    queryKey: financeKeys.state(),
    queryFn: () => financeApi.state(),
    refetchInterval: (query) => {
      const data = query.state.data;
      const missingPrices = data?.positions.some(
        (position) => position.quantite > 0 && position.prix <= 0,
      );
      return missingPrices && query.state.dataUpdateCount < 6 ? 5_000 : false;
    },
  });
}

export function useFinanceSettings() {
  return useQuery({
    queryKey: financeKeys.settings(),
    queryFn: () => financeApi.settings(),
    staleTime: 5 * 60 * 1000,
  });
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
      void qc.invalidateQueries({ queryKey: financeKeys.all });
    },
  });
}

/** Upsert position + invalidation. */
export function useCreatePosition() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (p: PositionCreate) => financeApi.positionCreate(p),
    onSuccess: () => {
      void qc.invalidateQueries({ queryKey: financeKeys.all });
    },
  });
}

/** Objectif patrimoine — lecture + mise à jour. */
export const financeObjectifKeys = {
  objectif: () => [...financeKeys.all, "objectif-patrimoine"] as const,
};

export function useObjectifPatrimoine() {
  return useQuery({
    queryKey: financeObjectifKeys.objectif(),
    queryFn: () => financeApi.objectifPatrimoine(),
  });
}

/** Estimation fiscale CTO : plus-values au PMP et dividendes. */
export function useCalculImpots(params: {
  annee: number;
  autres_revenus?: number;
  parts?: number;
  moins_values_anterieures?: number;
  moins_values_anterieures_annee?: number;
  dividendes_eligibles_abattement?: boolean;
  broker?: string;
}) {
  return useQuery({
    queryKey: [...financeKeys.all, "impots", params],
    queryFn: () => financeApi.calculImpots(params),
  });
}

/** Détail vente par vente au prix moyen pondéré. */
export function useVentesImpots(params: { annee?: number; broker?: string }, enabled = true) {
  return useQuery({
    queryKey: [...financeKeys.all, "impots-ventes", params],
    queryFn: () => financeApi.ventesImpots(params),
    enabled,
  });
}

export function useSetObjectifPatrimoine() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (objectif_eur: number) => financeApi.setObjectifPatrimoine(objectif_eur),
    onSuccess: () => {
      void qc.invalidateQueries({ queryKey: financeObjectifKeys.objectif() });
    },
  });
}

/** Alertes de marché — seuils de prix par ticker (#265). */
export function useAlerts() {
  return useQuery({ queryKey: financeKeys.alerts(), queryFn: () => financeApi.alertsList() });
}

export function useAlertsStatus() {
  return useQuery({
    queryKey: financeKeys.alertsStatus(),
    queryFn: () => financeApi.alertsStatus(),
  });
}

export function useCreateAlert() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (a: PriceAlertCreate) => financeApi.alertsCreate(a),
    onSuccess: () => {
      void qc.invalidateQueries({ queryKey: financeKeys.alerts() });
      void qc.invalidateQueries({ queryKey: financeKeys.alertsStatus() });
    },
  });
}

export function useUpdateAlert() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: ({ id, patch }: { id: number; patch: PriceAlertPatch }) =>
      financeApi.alertsUpdate(id, patch),
    onSuccess: () => {
      void qc.invalidateQueries({ queryKey: financeKeys.alerts() });
      void qc.invalidateQueries({ queryKey: financeKeys.alertsStatus() });
    },
  });
}

export function useDeleteAlert() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (id: number) => financeApi.alertsDelete(id),
    onSuccess: () => {
      void qc.invalidateQueries({ queryKey: financeKeys.alerts() });
      void qc.invalidateQueries({ queryKey: financeKeys.alertsStatus() });
    },
  });
}
