"use client";

import { useEffect, useState, type Dispatch, type SetStateAction } from "react";
import type { FenetreDayPlan, WindowPlanResponse } from "@/lib/sante";
import {
  useCartFillStatus,
  useCartPlan,
  useActiveGenerateFenetre,
  useFenetreCurrent,
  useGenerateFenetreStatus,
  usePatchPlan,
  useStartCartFill,
  useStartGenerateFenetre,
  useStopGenerateFenetre,
} from "@/lib/queries/sante";

export function useFenetreGeneration(onSaveMesure: (m: { date: string; poids?: number }) => Promise<void>, lastWeight?: number | null) {
  const fenetreQ = useFenetreCurrent();
  const cartPlanQ = useCartPlan();
  const generate = useStartGenerateFenetre();
  const stopGenerate = useStopGenerateFenetre();
  const activeGenQ = useActiveGenerateFenetre();
  const [genJobId, setGenJobId] = useState<string | null>(null);
  const [poids, setPoids] = useState("");
  const effectiveGenJobId = firstJobId(genJobId, activeGenQ.data?.job_id);
  const genQ = useGenerateFenetreStatus(effectiveGenJobId);
  const genJob = nullableJob(genQ.data);
  const generating = isGenerating(generate.isPending, genJob);

  useGenerationCompletion(genQ.data?.status, fenetreQ.refetch, cartPlanQ.refetch, setGenJobId);
  useGenerationRecovery(genJobId, genQ.isError, activeGenQ.isFetched, activeGenQ.data?.job_id, setGenJobId);
  useWeightSync(lastWeight, poids, setPoids);

  const onGenerate = (force = false, refreshPrices = true) => runGeneration(
    poids, force, refreshPrices, onSaveMesure, generate.mutateAsync, setGenJobId, activeGenQ.refetch,
  );
  const onStopGenerate = () => runStopGeneration(
    firstJobId(effectiveGenJobId, genJob?.job_id), genJob?.stop_requested, stopGenerate.mutateAsync, genQ.refetch,
  );

  return { fenetreQ, cartPlanQ, genJob, generating, poids, setPoids, onGenerate, onStopGenerate };
}

function firstJobId(primary: string | null, fallback: string | undefined) { return primary ?? fallback ?? null; }
function nullableJob<T>(job: T | null | undefined) { return job ?? null; }
function isGenerating(pending: boolean, job: { status: string } | null) {
  return pending || Boolean(job && ["queued", "running"].includes(job.status));
}

function useGenerationCompletion(status: string | undefined, refetchWindow: () => Promise<unknown>, refetchCart: () => Promise<unknown>, setJobId: Dispatch<SetStateAction<string | null>>) {
  useEffect(() => {
    if (status !== "completed") return;
    void Promise.all([refetchWindow(), refetchCart()]).finally(() => setJobId(null));
  }, [status]); // eslint-disable-line react-hooks/exhaustive-deps
}

function useGenerationRecovery(jobId: string | null, isError: boolean, isFetched: boolean, activeJobId: string | undefined, setJobId: Dispatch<SetStateAction<string | null>>) {
  useEffect(() => {
    if (!jobId) return;
    if (!isError) return;
    if (!isFetched) return;
    setJobId(nullableJob(activeJobId));
  }, [jobId, isError, isFetched, activeJobId, setJobId]);
}

function useWeightSync(lastWeight: number | null | undefined, poids: string, setPoids: Dispatch<SetStateAction<string>>) {
  useEffect(() => {
    if (lastWeight != null && poids === "") setPoids(String(lastWeight));
  }, [lastWeight]); // eslint-disable-line react-hooks/exhaustive-deps
}

type GenerateMutation = ReturnType<typeof useStartGenerateFenetre>;

async function runGeneration(
  poids: string,
  force: boolean,
  refreshPrices: boolean,
  onSaveMesure: (m: { date: string; poids?: number }) => Promise<void>,
  mutateAsync: GenerateMutation["mutateAsync"],
  setJobId: Dispatch<SetStateAction<string | null>>,
  refetchActive: () => Promise<unknown>,
) {
  const parsedWeight = poids ? parseFloat(poids) : undefined;
  if (parsedWeight) await onSaveMesure({ date: new Date().toISOString().slice(0, 10), poids: parsedWeight });
  const job = await mutateAsync({ poids: parsedWeight, force, refresh_prices: refreshPrices });
  setJobId(job.job_id);
  void refetchActive();
}

async function runStopGeneration(
  jobId: string | null,
  stopRequested: boolean | undefined,
  mutateAsync: ReturnType<typeof useStopGenerateFenetre>["mutateAsync"],
  refetch: () => Promise<unknown>,
) {
  if (!jobId) return;
  if (stopRequested) return;
  await mutateAsync(jobId);
  await refetch();
}

export function useFenetreConsumption() {
  const patchPlanMutation = usePatchPlan();
  const [checked, setChecked] = useState<Record<string, boolean>>({});
  const [savingDate, setSavingDate] = useState<string | null>(null);
  const [savedDates, setSavedDates] = useState<Record<string, boolean>>({});
  const [consoErr, setConsoErr] = useState<string | null>(null);
  const [consoDrawerDate, setConsoDrawerDate] = useState<string | null>(null);

  const onChecked = (aliment: string, value: boolean) => {
    setChecked((current) => ({ ...current, [aliment]: value }));
  };

  const onConsume = (day: FenetreDayPlan) => {
    setConsoErr(null);
    setSavingDate(day.date);
    const consumed_grams = Object.fromEntries(day.items.map((item): [string, number] => [item.aliment, item.quantite_g]));
    patchPlanMutation.mutate(
      { date: day.date, patch: { consumed_grams } },
      {
        onSuccess: () => setSavedDates((saved) => ({ ...saved, [day.date]: true })),
        onError: (error) => setConsoErr(error instanceof Error ? error.message : "Erreur enregistrement conso"),
        onSettled: () => setSavingDate((date) => date === day.date ? null : date),
      },
    );
  };

  const onSaveForDay = async (grams: Record<string, number>) => {
    if (!consoDrawerDate) return;
    await patchPlanMutation.mutateAsync({ date: consoDrawerDate, patch: { consumed_grams: grams } });
    setSavedDates((saved) => ({ ...saved, [consoDrawerDate]: true }));
  };

  return { checked, savingDate, savedDates, consoErr, consoDrawerDate, setConsoDrawerDate, onChecked, onConsume, onSaveForDay };
}

export function useFenetreCart() {
  const [cartJobId, setCartJobId] = useState<string | null>(null);
  const startCartFill = useStartCartFill();
  const cartFillQ = useCartFillStatus(cartJobId);
  const onStartCart = () => {
    startCartFill.mutate(undefined, { onSuccess: (job) => setCartJobId(job.job_id) });
  };
  return { cartJob: cartFillQ.data ?? null, cartPending: startCartFill.isPending, cartError: startCartFill.isError, onStartCart };
}

export function buildMacroSummary(win: WindowPlanResponse | null) {
  return MACROS.map(({ key, label, unit }) => ({
    key, label, unit,
    total: sumMetric(win, key, "totals"),
    target: sumMetric(win, key, "targets"),
  }));
}

const MACROS = [
  { key: "Calories", label: "Calories", unit: "kcal" },
  { key: "Protéines", label: "Protéines", unit: "g" },
  { key: "Lipides", label: "Lipides", unit: "g" },
  { key: "Glucides", label: "Glucides", unit: "g" },
] as const;

function sumMetric(win: WindowPlanResponse | null, key: string, field: "totals" | "targets") {
  if (!win) return 0;
  return win.jours.reduce((sum, day) => sum + (day[field]?.[key] ?? 0), 0);
}

export function macroBalance(macros: ReturnType<typeof buildMacroSummary>) {
  const values = macros.filter((macro) => macro.target > 0).map((macro) => balanceValue(macro.total, macro.target));
  return values.length ? values.reduce((sum, value) => sum + value, 0) / values.length : 0;
}

function balanceValue(total: number, target: number) {
  if (total <= 0) return 0;
  const ratio = total / target;
  return Math.min(ratio, 1 / ratio);
}

export function findFenetreDay(win: WindowPlanResponse | null, date: string | null) {
  return win?.jours.find((day) => day.date === date) ?? null;
}
