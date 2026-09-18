"use client";

/** Onglet Buffett — orchestrateur : runs, progression, timeline (#532 :
 *  vue détail et panneau d'actions extraits). */

import { useEffect, useMemo, useState, useCallback } from "react";
import {
  financeApi, type BuffettRunOut, type BuffettRunDetail, type BuffettProgress,
} from "@/lib/finance";
import { Spinner } from "@/components/ui/spinner";
import type { OptProgress } from "./buffett-ui";
import { BuffettTabContent } from "./BuffettTabContent";
import { optimizationIsActive, progressFlags, scoreHistory } from "./buffett-tab-state";
import {
  applyLiveState,
  initialLoadFailure,
  useBuffettLivePolling,
  useBuffettOptimizationEvents,
  useBuffettProgressEvents,
  useBuffettRunEvents,
} from "./buffett-tab-sync";
import {
  deleteRun,
  openRun,
  reloadSelectedRun,
  startRun,
  stopOptimization,
} from "./buffett-tab-actions";
import { useRealtimeStatus } from "@/components/RealtimeProvider";

export function BuffettTab() {
  const [runs, setRuns] = useState<BuffettRunOut[]>([]);
  const [selected, setSelected] = useState<BuffettRunDetail | null>(null);
  const [progress, setProgress] = useState<BuffettProgress | null>(null);
  const [optProgress, setOptProgress] = useState<OptProgress | null>(null);
  const [loading, setLoading] = useState(true);
  const [liveHydrated, setLiveHydrated] = useState(false);
  const [reconnecting, setReconnecting] = useState(false);
  const [starting, setStarting] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const realtimeStatus = useRealtimeStatus();
  const liveHandlers = useMemo(() => ({
    setProgress,
    setOptProgress,
    setLiveHydrated,
    setReconnecting,
  }), []);

  const loadRuns = useCallback(async () => {
    // Appliquer l'état live dès sa réponse : la timeline SQLite peut être lente
    // sans devoir retarder la barre de progression lors d'un F5.
    const liveRequest = financeApi.buffettLiveState(0).then((value) => {
      applyLiveState(value, liveHandlers);
      return value;
    });
    const runsRequest = financeApi.buffettRuns().then((value) => {
      setRuns(value);
      return value;
    });
    const [runsResult, liveResult] = await Promise.allSettled([
      runsRequest,
      liveRequest,
    ]);
    setError(initialLoadFailure(runsResult, liveResult, setLiveHydrated, setReconnecting));
    setLoading(false);
  }, [liveHandlers]);

  useEffect(() => {
    // Hydratation initiale depuis l'API ; les setState ont lieu après la réponse.
    // eslint-disable-next-line react-hooks/set-state-in-effect
    void loadRuns();
  }, [loadRuns]);

  useBuffettProgressEvents({ setProgress, loadRuns });

  // Filet de sécurité pour la COURBE d'optimisation. Sans lui, `optProgress` ne
  // dépendait que du flux SSE : un événement perdu (onglet en arrière-plan,
  // proxy silencieux, resynchronisation) figeait le graphique jusqu'au F5.
  // `history_after` ne redemande que les générations non encore reçues, donc le
  // rattrapage reste peu coûteux même sur un run de plusieurs heures.
  // Ref plutôt que dépendance d'effet : la dernière itération change à chaque
  // génération et recréerait l'intervalle (donc une requête) à chaque fois.
  const history = scoreHistory(optProgress);
  const optimizationActive = optimizationIsActive(progress, optProgress);
  useBuffettLivePolling({
    loading,
    liveHydrated,
    optimizationActive,
    realtimeStatus,
    history,
    loadRuns,
    handlers: liveHandlers,
  });
  useBuffettOptimizationEvents(progress, setOptProgress, loadRuns);
  useBuffettRunEvents({
    selectedId: selected?.run.id ?? null,
    setSelected,
    loadRuns,
  });

  const { interrupted, paused, resumeAt } = progressFlags(progress);

  if (loading) return <Spinner label="Chargement analyses Buffett..." />;

  return (
    <BuffettTabContent
      error={error}
      reconnecting={reconnecting}
      progress={progress}
      optProgress={optProgress}
      runs={runs}
      selected={selected}
      starting={starting}
      interrupted={interrupted}
      paused={paused}
      resumeAt={resumeAt}
      onStop={() => { void stopOptimization(setError); }}
      onStartRun={() => { void startRun({ interrupted, setStarting, setError, loadRuns }); }}
      onOptimizationStarted={(value) => {
        setOptProgress(value);
        // L'optimisation réutilise le dernier run d'analyse : rafraîchir la
        // timeline permet de l'ouvrir immédiatement après le clic.
        void loadRuns();
      }}
      onError={setError}
      onOpenRun={(id) => { void openRun(id, setSelected, setError); }}
      onDeleteRun={(id) => {
        void deleteRun({
          id,
          selectedId: selected?.run.id ?? null,
          setSelected,
          setProgress,
          setError,
          loadRuns,
        });
      }}
      onBack={() => setSelected(null)}
      onReload={() => reloadSelectedRun(selected?.run.id ?? null, setSelected)}
    />
  );
}
