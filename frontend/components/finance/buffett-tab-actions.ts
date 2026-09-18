import type { Dispatch, SetStateAction } from "react";
import type { BuffettRunDetail } from "@/lib/finance";
import { financeApi } from "@/lib/finance";

type SetError = Dispatch<SetStateAction<string | null>>;

function errorMessage(error: unknown, fallback: string) {
  return error instanceof Error ? error.message : fallback;
}

export async function stopOptimization(setError: SetError) {
  try {
    await financeApi.optimizationStop();
  } catch (error: unknown) {
    setError(errorMessage(error, "Erreur arrêt optimisation"));
  }
}

export async function openRun(
  id: number,
  setSelected: Dispatch<SetStateAction<BuffettRunDetail | null>>,
  setError: SetError,
) {
  try {
    setSelected(await financeApi.buffettRun(id));
  } catch (error: unknown) {
    setError(errorMessage(error, "Erreur"));
  }
}

export async function deleteRun({
  id,
  selectedId,
  setSelected,
  setProgress,
  setError,
  loadRuns,
}: {
  id: number;
  selectedId: number | null;
  setSelected: Dispatch<SetStateAction<BuffettRunDetail | null>>;
  setProgress: Dispatch<SetStateAction<import("@/lib/finance").BuffettProgress | null>>;
  setError: SetError;
  loadRuns: () => Promise<void>;
}) {
  if (!confirm("Supprimer cette analyse et ses résultats ?")) return;
  try {
    await financeApi.buffettDeleteRun(id);
    if (selectedId === id) setSelected(null);
    setProgress(null);
    await loadRuns();
  } catch (error: unknown) {
    setError(errorMessage(error, "Erreur suppression"));
  }
}

export async function startRun({
  interrupted,
  setStarting,
  setError,
  loadRuns,
}: {
  interrupted: boolean;
  setStarting: Dispatch<SetStateAction<boolean>>;
  setError: SetError;
  loadRuns: () => Promise<void>;
}) {
  const message = interrupted
    ? "Reprendre l'analyse interrompue ? Les tickers déjà analysés ne seront pas refaits."
    : "Lancer une analyse complète de tous les tickers ? Durée : plusieurs heures.";
  if (!confirm(message)) return;
  setStarting(true);
  setError(null);
  try {
    await financeApi.buffettStart();
    await loadRuns();
  } catch (error: unknown) {
    setError(errorMessage(error, "Erreur démarrage"));
  } finally {
    setStarting(false);
  }
}

export async function reloadSelectedRun(
  selectedId: number | null,
  setSelected: Dispatch<SetStateAction<BuffettRunDetail | null>>,
) {
  if (selectedId == null) return;
  setSelected(await financeApi.buffettRun(selectedId));
}
