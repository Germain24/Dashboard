import { useEffect, useRef } from "react";
import type { Dispatch, SetStateAction } from "react";
import type { BuffettProgress } from "@/lib/finance";
import { financeApi } from "@/lib/finance";
import { useRealtimeEvent } from "@/components/RealtimeProvider";
import type { OptProgress } from "./buffett-ui";
import { mergeOptimizationProgress } from "./buffett-progress";

type SetProgress = Dispatch<SetStateAction<BuffettProgress | null>>;
type SetOptimization = Dispatch<SetStateAction<OptProgress | null>>;

type LiveHandlers = {
  setProgress: SetProgress;
  setOptProgress: SetOptimization;
  setLiveHydrated: Dispatch<SetStateAction<boolean>>;
  setReconnecting: Dispatch<SetStateAction<boolean>>;
};

type LiveState = Awaited<ReturnType<typeof financeApi.buffettLiveState>>;

function isRejected<T>(
  result: PromiseSettledResult<T>,
): result is PromiseRejectedResult {
  return result.status === "rejected";
}

function markInitialLiveFailure(
  liveResult: PromiseSettledResult<unknown>,
  setLiveHydrated: Dispatch<SetStateAction<boolean>>,
  setReconnecting: Dispatch<SetStateAction<boolean>>,
) {
  if (!isRejected(liveResult)) return;
  setLiveHydrated(false);
  setReconnecting(true);
}

function initialFailureMessage(reason: unknown) {
  return reason instanceof Error ? reason.message : "Service Finance indisponible";
}

export function initialLoadFailure(
  runsResult: PromiseSettledResult<unknown>,
  liveResult: PromiseSettledResult<unknown>,
  setLiveHydrated: Dispatch<SetStateAction<boolean>>,
  setReconnecting: Dispatch<SetStateAction<boolean>>,
) {
  markInitialLiveFailure(liveResult, setLiveHydrated, setReconnecting);
  if (!isRejected(runsResult) || !isRejected(liveResult)) return null;
  return initialFailureMessage(liveResult.reason);
}

export function applyLiveState(value: LiveState, handlers: LiveHandlers) {
  const { analysis, optimization } = value;
  handlers.setProgress(analysis);
  handlers.setLiveHydrated(true);
  handlers.setReconnecting(false);
  if (analysis.run_id == null || optimization.run_id === analysis.run_id) {
    handlers.setOptProgress((current) => mergeOptimizationProgress(current, optimization));
  }
}

function flushProgress(
  pending: { current: Partial<BuffettProgress> | null },
  setProgress: SetProgress,
  loadRuns: () => Promise<void>,
) {
  const next = pending.current;
  pending.current = null;
  if (!next) return;
  setProgress((current) => ({ ...(current ?? {}), ...next } as BuffettProgress));
  if (next.active === false) void loadRuns();
}

function queueProgress(
  data: Partial<BuffettProgress>,
  pending: { current: Partial<BuffettProgress> | null },
  timer: { current: number | null },
  setProgress: SetProgress,
  loadRuns: () => Promise<void>,
) {
  pending.current = { ...(pending.current ?? {}), ...data };
  if (timer.current != null) return;
  timer.current = window.setTimeout(() => {
    timer.current = null;
    flushProgress(pending, setProgress, loadRuns);
  }, 100);
}

export function useBuffettProgressEvents({
  setProgress,
  loadRuns,
}: {
  setProgress: SetProgress;
  loadRuns: () => Promise<void>;
}) {
  const pending = useRef<Partial<BuffettProgress> | null>(null);
  const timer = useRef<number | null>(null);

  useRealtimeEvent<Partial<BuffettProgress>>("finance.buffett.progress", ({ data }) => {
    if (!data) return;
    queueProgress(data, pending, timer, setProgress, loadRuns);
  });

  useEffect(() => () => {
    if (timer.current != null) window.clearTimeout(timer.current);
  }, []);
}

function latestIteration(history: OptProgress["score_history"]) {
  if (!history?.length) return 0;
  return history[history.length - 1].iteration;
}

function shouldSkipPolling(
  loading: boolean,
  liveHydrated: boolean,
  optimizationActive: boolean,
) {
  if (loading) return true;
  return liveHydrated && !optimizationActive;
}

function applyPolledState(
  next: LiveState,
  handlers: LiveHandlers,
  loadRuns: () => Promise<void>,
) {
  applyLiveState(next, handlers);
  if (!next.analysis.active && !next.optimization.active) void loadRuns();
}

function handleRefreshSuccess(
  next: LiveState,
  isDisposed: () => boolean,
  handlers: LiveHandlers,
  loadRuns: () => Promise<void>,
) {
  if (isDisposed()) return;
  applyPolledState(next, handlers, loadRuns);
}

function handleRefreshFailure(
  isDisposed: () => boolean,
  setReconnecting: Dispatch<SetStateAction<boolean>>,
) {
  if (!isDisposed()) setReconnecting(true);
}

async function refreshLiveState({
  iteration,
  refreshing,
  isDisposed,
  handlers,
  loadRuns,
}: {
  iteration: { current: number };
  refreshing: { current: boolean };
  isDisposed: () => boolean;
  handlers: LiveHandlers;
  loadRuns: () => Promise<void>;
}) {
  if (refreshing.current) return;
  refreshing.current = true;
  try {
    const next = await financeApi.buffettLiveState(iteration.current);
    handleRefreshSuccess(next, isDisposed, handlers, loadRuns);
  } catch {
    handleRefreshFailure(isDisposed, handlers.setReconnecting);
  } finally {
    refreshing.current = false;
  }
}

function pollingDelay(liveHydrated: boolean, realtimeStatus: string) {
  if (liveHydrated && realtimeStatus === "connected") return 10_000;
  return 5_000;
}

function configurePolling(
  refresh: () => void,
  liveHydrated: boolean,
  realtimeStatus: string,
) {
  const kickoff = window.setTimeout(refresh, liveHydrated ? 5_000 : 500);
  const timer = window.setInterval(refresh, pollingDelay(liveHydrated, realtimeStatus));
  return () => {
    window.clearTimeout(kickoff);
    window.clearInterval(timer);
  };
}

export function useBuffettLivePolling({
  loading,
  liveHydrated,
  optimizationActive,
  realtimeStatus,
  history,
  loadRuns,
  handlers,
}: {
  loading: boolean;
  liveHydrated: boolean;
  optimizationActive: boolean;
  realtimeStatus: string;
  history: OptProgress["score_history"];
  loadRuns: () => Promise<void>;
  handlers: LiveHandlers;
}) {
  const lastIteration = useRef(0);
  useEffect(() => {
    lastIteration.current = latestIteration(history);
  }, [history]);

  useEffect(() => {
    if (shouldSkipPolling(loading, liveHydrated, optimizationActive)) return;
    let disposed = false;
    const refreshing = { current: false };
    const refresh = () => void refreshLiveState({
      iteration: lastIteration,
      refreshing,
      isDisposed: () => disposed,
      handlers,
      loadRuns,
    });
    const cleanup = configurePolling(refresh, liveHydrated, realtimeStatus);
    return () => {
      disposed = true;
      cleanup();
    };
  }, [handlers, liveHydrated, loadRuns, loading, optimizationActive, realtimeStatus]);
}

function isMatchingOptimization(data: OptProgress, progress: BuffettProgress | null) {
  if (progress?.run_id == null) return true;
  return data.run_id === progress.run_id;
}

export function useBuffettOptimizationEvents(
  progress: BuffettProgress | null,
  setOptProgress: SetOptimization,
  loadRuns?: () => Promise<void>,
) {
  useRealtimeEvent<OptProgress>("finance.optimization.progress", ({ data }) => {
    if (!data) return;
    if (!isMatchingOptimization(data, progress)) return;
    setOptProgress((current) => mergeOptimizationProgress(current, data));
    if (!data.active) void loadRuns?.();
  });
}

function shouldReloadRuns(data: { reason: string; progressive?: boolean }) {
  return data.reason === "created" || data.reason === "finished" || data.reason === "deleted"
    || (data.reason === "allocation" && data.progressive === false);
}

function refreshSelectedRun(
  data: { run_id: number; reason: string },
  selectedId: number | null,
  setSelected: Dispatch<SetStateAction<import("@/lib/finance").BuffettRunDetail | null>>,
) {
  if (data.reason !== "allocation" || selectedId !== data.run_id) return;
  void financeApi.buffettRun(data.run_id).then(setSelected).catch(() => undefined);
}

export function useBuffettRunEvents({
  selectedId,
  setSelected,
  loadRuns,
}: {
  selectedId: number | null;
  setSelected: Dispatch<SetStateAction<import("@/lib/finance").BuffettRunDetail | null>>;
  loadRuns: () => Promise<void>;
}) {
  useRealtimeEvent<{ run_id: number; reason: string; progressive?: boolean }>("finance.run.changed", ({ data }) => {
    if (!data) return;
    refreshSelectedRun(data, selectedId, setSelected);
    if (shouldReloadRuns(data)) void loadRuns();
  });
}
