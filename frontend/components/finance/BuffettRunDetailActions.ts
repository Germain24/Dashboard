import { useState } from "react";
import type { BuffettEquityLookthrough, BuffettRunDetail } from "@/lib/finance";
import { financeApi } from "@/lib/finance";

export type DetailBacktest = Awaited<ReturnType<typeof financeApi.backtest>>
  & Partial<Awaited<ReturnType<typeof financeApi.backtestWalkForward>>>;

type ErrorHandler = (message: string) => void;

function errorMessage(error: unknown, fallback: string) {
  return error instanceof Error ? error.message : fallback;
}

async function runBacktestRequest(
  request: Promise<DetailBacktest>,
  setBacktest: (value: DetailBacktest | null) => void,
  setBacktesting: (value: boolean) => void,
  onError: ErrorHandler,
  fallback: string,
) {
  setBacktesting(true);
  setBacktest(null);
  try {
    setBacktest(await request);
  } catch (error: unknown) {
    onError(errorMessage(error, fallback));
  } finally {
    setBacktesting(false);
  }
}

async function loadLookthrough(
  runId: number,
  setLookthroughState: (value: { runId: number; data: BuffettEquityLookthrough }) => void,
  setLoading: (value: boolean) => void,
  setError: (value: string | null) => void,
  onError: ErrorHandler,
) {
  setLoading(true);
  try {
    const data = await financeApi.buffettEquityLookthrough(runId);
    setLookthroughState({ runId, data });
  } catch (error: unknown) {
    const message = errorMessage(error, "Erreur de décomposition des ETF");
    setError(message);
    onError(message);
  } finally {
    setLoading(false);
  }
}

async function downloadRun(
  runId: number,
  runDate: string,
  format: "xlsx" | "csv",
  onError: ErrorHandler,
) {
  try {
    const path = format === "csv" ? "export.csv" : "export";
    const response = await fetch(`/api/finance/buffett/runs/${runId}/${path}`);
    if (!response.ok) throw new Error("Erreur export");
    const url = URL.createObjectURL(await response.blob());
    const link = document.createElement("a");
    link.href = url;
    link.download = `buffett_run_${runId}_${runDate}.${format}`;
    link.click();
    URL.revokeObjectURL(url);
  } catch (error: unknown) {
    onError(errorMessage(error, `Erreur export ${format}`));
  }
}

export function useBuffettRunDetailActions({
  selected,
  onError,
  onReload,
}: {
  selected: BuffettRunDetail;
  onError: ErrorHandler;
  onReload: () => Promise<void>;
}) {
  const [backtest, setBacktest] = useState<DetailBacktest | null>(null);
  const [backtesting, setBacktesting] = useState(false);
  const [lookthroughState, setLookthroughState] = useState<{
    runId: number;
    data: BuffettEquityLookthrough;
  } | null>(null);
  const [lookthroughView, setLookthroughView] = useState({ runId: selected.run.id, show: false });
  const [loadingLookthrough, setLoadingLookthrough] = useState(false);
  const [lookthroughError, setLookthroughError] = useState<string | null>(null);
  const [selectingScenario, setSelectingScenario] = useState<string | null>(null);
  const lookthrough = lookthroughState?.runId === selected.run.id ? lookthroughState.data : null;
  const showLookthrough = lookthroughView.runId === selected.run.id && lookthroughView.show;

  const runBacktest = () => runBacktestRequest(
    financeApi.backtest("2y"),
    setBacktest,
    setBacktesting,
    onError,
    "Erreur backtest",
  );
  const runWalkForward = () => runBacktestRequest(
    financeApi.backtestWalkForward("5y", 10),
    setBacktest,
    setBacktesting,
    onError,
    "Erreur backtest walk-forward",
  );
  const selectAllocationView = async (view: string) => {
    if (view === "etf") {
      setLookthroughView({ runId: selected.run.id, show: false });
      return;
    }
    setLookthroughView({ runId: selected.run.id, show: true });
    setLookthroughError(null);
    if (lookthrough) return;
    await loadLookthrough(
      selected.run.id,
      setLookthroughState,
      setLoadingLookthrough,
      setLookthroughError,
      onError,
    );
  };
  const selectScenario = async (scenario: "free" | "world_25" | "world_40" | "world_55") => {
    setSelectingScenario(scenario);
    try {
      await financeApi.selectBuffettScenario(selected.run.id, scenario);
      setLookthroughState(null);
      setLookthroughView({ runId: selected.run.id, show: false });
      await onReload();
    } catch (error: unknown) {
      onError(errorMessage(error, "Erreur de sélection du scénario"));
    } finally {
      setSelectingScenario(null);
    }
  };
  const exportRun = (format: "xlsx" | "csv") =>
    downloadRun(selected.run.id, selected.run.run_date, format, onError);

  return {
    backtest,
    backtesting,
    lookthrough,
    showLookthrough,
    loadingLookthrough,
    lookthroughError,
    selectingScenario,
    runBacktest,
    runWalkForward,
    selectAllocationView,
    selectScenario,
    exportRun,
  };
}
