"use client";

import { Gauge, Hourglass, Pause, Trash2 } from "lucide-react";
import { EmptyState } from "@/components/ui/empty-state";
import { Badge } from "@/components/ui/badge";
import type { BuffettProgress, BuffettRunOut } from "@/lib/finance";
import { DeProgressBar, fmt, ProgressBar, StatusBadge, type OptProgress } from "./buffett-ui";
import { DeStarrChart } from "./DeStarrChart";

type ProgressPanelProps = {
  progress: BuffettProgress | null;
  optProgress: OptProgress | null;
  interrupted: boolean;
  paused: boolean;
  resumeAt: string | null;
  onStop: () => void;
  onOpenRun?: (id: number) => void;
};

function progressIcon(interrupted: boolean, paused: boolean) {
  if (interrupted) return <Pause className="size-4" aria-hidden="true" />;
  if (paused) return <Hourglass className="size-4" aria-hidden="true" />;
  return <Gauge className="size-4" aria-hidden="true" />;
}

function progressLabel(
  interrupted: boolean,
  paused: boolean,
  optimizationLabel: string | null,
  analysisPhase: string,
) {
  if (interrupted) return "Analyse interrompue";
  if (paused) return "En pause (limite API atteinte)";
  return optimizationLabel ?? `Analyse en cours — ${analysisPhase}`;
}

function optimizationLabel(optProgress: OptProgress | null) {
  if (!optProgress?.active) return null;
  if (optProgress.phase === "optimisation") {
    return "Scoring terminé — optimisation du portefeuille en cours...";
  }
  return "Scoring terminé — préparation du portefeuille en cours...";
}

function progressPercentage(progress: BuffettProgress | null, optProgress: OptProgress | null) {
  if (optProgress?.active) return fmt(optProgress.progress_pct);
  return fmt(progress?.progress_pct);
}

function progressPanelClass(interrupted: boolean) {
  if (interrupted) {
    return "border-[var(--warning-muted)] bg-[var(--warning-muted)]";
  }
  return "border-[var(--border)]";
}

function progressBadgeVariant(interrupted: boolean, paused: boolean) {
  return interrupted || paused ? "warning" : "info";
}

function valueOr<T>(value: T | null | undefined, fallback: T) {
  return value == null ? fallback : value;
}

function etaLabel(seconds: number | null | undefined) {
  if (seconds == null) return "—";
  return `${Math.floor(seconds / 3600)} h ${Math.floor((seconds % 3600) / 60)} min`;
}

function progressStats(progress: BuffettProgress) {
  const errors = Object.values(progress.error_counts ?? {}).reduce((sum, count) => sum + count, 0);
  const requests = `${valueOr(progress.http_requests, 0)} · ${valueOr(progress.http_requests_per_hour, 2000)}/h`;
  return [
    ["Débit", `${fmt(valueOr(progress.throughput_per_min, 0))} / min`],
    ["ETA", etaLabel(progress.eta_seconds)],
    ["Cache", `${valueOr(progress.cache_hits, 0)} hits`],
    ["Erreurs", String(errors)],
    ["Requêtes Yahoo", requests],
    ["Cotations propagées", String(valueOr(progress.propagated_quotes, 0))],
  ] as const;
}

function ProgressStats({ progress }: { progress: BuffettProgress | null }) {
  if (!progress?.active) return null;
  return (
    <dl className="grid grid-cols-2 gap-2 pt-1 text-xs sm:grid-cols-3 lg:grid-cols-6">
      {progressStats(progress).map(([label, value]) => (
        <Stat key={label} label={label} value={value} />
      ))}
    </dl>
  );
}

function Stat({ label, value }: { label: string; value: string }) {
  return (
    <div>
      <dt className="text-[var(--muted-foreground)]">{label}</dt>
      <dd className="font-medium">{value}</dd>
    </div>
  );
}

function AnalysisProgressBar({
  progress,
  optimizing,
}: {
  progress: BuffettProgress | null;
  optimizing: boolean;
}) {
  if (optimizing) return null;
  return <ProgressBar pct={progress?.progress_pct ?? 0} />;
}

function InstrumentSummary({ progress }: { progress: BuffettProgress | null }) {
  if (!hasInstrumentSummary(progress)) return null;
  return (
    <p className="text-xs text-[var(--muted-foreground)]">
      {progress.n_done} / {progress.n_total} instruments uniques analysés
      {secondaryQuotesLabel(progress.secondary_quotes_skipped)}
    </p>
  );
}

function hasInstrumentSummary(
  progress: BuffettProgress | null,
): progress is BuffettProgress & { n_done: number; n_total: number } {
  return progress != null && progress.n_done != null && progress.n_total != null;
}

function secondaryQuotesLabel(skipped: number | null | undefined) {
  if (!skipped) return "";
  return ` · ${skipped} cotations secondaires ignorées`;
}

function ProgressDetails({
  progress,
  optimizing,
}: {
  progress: BuffettProgress | null;
  optimizing: boolean;
}) {
  return (
    <>
      <AnalysisProgressBar progress={progress} optimizing={optimizing} />
      <InstrumentSummary progress={progress} />
      <ProgressStats progress={progress} />
    </>
  );
}

function ProgressMessages({
  paused,
  resumeAt,
  interrupted,
}: Pick<ProgressPanelProps, "paused" | "resumeAt" | "interrupted">) {
  return (
    <>
      {paused && (
        <p className="text-xs text-[var(--warning-foreground)]">
          Limite de l&apos;API Yahoo atteinte — l&apos;analyse reprend automatiquement
          {resumeAt ? ` vers ${resumeAt}` : " sous peu"}. Aucune action requise.
        </p>
      )}
      {interrupted && (
        <p className="text-xs text-[var(--warning-foreground)]">
          Le programme s&apos;est fermé pendant l&apos;analyse. Cliquez « Reprendre » pour continuer
          sans refaire les tickers déjà analysés.
        </p>
      )}
    </>
  );
}

function ProgressHeader({
  progress,
  optProgress,
  interrupted,
  paused,
}: Pick<ProgressPanelProps, "progress" | "optProgress" | "interrupted" | "paused">) {
  const label = progressLabel(
    interrupted,
    paused,
    optimizationLabel(optProgress),
    progress?.phase ?? "scoring",
  );
  return (
    <div className="flex items-center justify-between">
      <span className="flex items-center gap-2 text-sm font-medium">
        {progressIcon(interrupted, paused)}
        {label}
      </span>
      <Badge variant={progressBadgeVariant(interrupted, paused)}>
        {progressPercentage(progress, optProgress)}%
      </Badge>
    </div>
  );
}

function ProgressChart({ optProgress }: { optProgress: OptProgress | null }) {
  if (!optProgress?.active) return null;
  return <DeStarrChart optProgress={optProgress} />;
}

function CurrentRunLink({
  optProgress,
  onOpenRun,
}: Pick<ProgressPanelProps, "optProgress" | "onOpenRun">) {
  const runId = optProgress?.run_id;
  if (runId == null || !onOpenRun) return null;
  return (
    <button
      type="button"
      className="text-xs text-[var(--primary)] hover:underline"
      onClick={() => onOpenRun(runId)}
    >
      Voir l’allocation actuelle
    </button>
  );
}

export function BuffettProgressPanel({
  progress,
  optProgress,
  interrupted,
  paused,
  resumeAt,
  onStop,
  onOpenRun,
}: ProgressPanelProps) {
  const optimizing = optProgress?.active === true;
  return (
    <div
      className={`rounded-[var(--radius-lg)] border p-4 space-y-2 ${progressPanelClass(interrupted)}`}
    >
      <ProgressHeader
        progress={progress}
        optProgress={optProgress}
        interrupted={interrupted}
        paused={paused}
      />
      <ProgressDetails progress={progress} optimizing={optimizing} />
      <CurrentRunLink optProgress={optProgress} onOpenRun={onOpenRun} />
      <DeProgressBar optProgress={optProgress} onStop={onStop} />
      <ProgressChart optProgress={optProgress} />
      <ProgressMessages paused={paused} resumeAt={resumeAt} interrupted={interrupted} />
    </div>
  );
}

function RunStatusDot({ status }: { status: string }) {
  const color =
    status === "termine"
      ? "bg-[var(--success)]"
      : status === "erreur"
        ? "bg-[var(--destructive)]"
        : "bg-[var(--ring)]";
  return (
    <span
      className={`absolute -left-[5px] top-3 h-2.5 w-2.5 rounded-full ring-2 ring-[var(--background)] ${color}`}
      aria-hidden="true"
    />
  );
}

function RunSummary({ run }: { run: BuffettRunOut }) {
  return (
    <>
      <div className="flex items-center justify-between">
        <span className="text-sm font-medium">{run.run_date}</span>
        <StatusBadge s={run.statut} />
      </div>
      <p className="text-xs text-[var(--muted-foreground)] mt-0.5">
        {run.n_tickers_analyzed ?? 0} tickers analysés
        {run.duree_sec ? ` · ${Math.round(run.duree_sec / 60)} min` : ""}
      </p>
      {run.resume && <p className="text-xs mt-1 text-[var(--foreground)]">{run.resume}</p>}
    </>
  );
}

export function BuffettRunsTimeline({
  runs,
  optProgress,
  onOpen,
  onDelete,
}: {
  runs: BuffettRunOut[];
  optProgress: OptProgress | null;
  onOpen: (id: number) => void;
  onDelete: (id: number) => void;
}) {
  const activeRunId = optProgress?.active ? optProgress.run_id : null;
  if (!runs.length && activeRunId == null) {
    return (
      <EmptyState title="Aucune analyse" description="Lancez votre première analyse Buffett." />
    );
  }
  return (
    <div>
      <h3 className="text-sm font-semibold mb-3">Historique des analyses</h3>
      {activeRunId != null && (
        <div className="mb-3 rounded-[var(--radius-lg)] border border-[var(--primary)]/50 bg-[var(--primary)]/5 p-3">
          <div className="flex items-center gap-2">
            <span
              className="size-2 animate-pulse rounded-full bg-[var(--primary)]"
              aria-hidden="true"
            />
            <span className="text-sm font-medium">Optimisation en cours · run #{activeRunId}</span>
          </div>
          <button
            type="button"
            onClick={() => onOpen(activeRunId)}
            className="mt-2 w-full rounded-[var(--radius)] border border-[var(--border)] bg-[var(--background)] p-2 text-left text-xs hover:bg-[var(--muted)] transition-colors"
          >
            Voir l’allocation actuelle de ce run
          </button>
        </div>
      )}
      {!runs.length ? null : (
        <ol className="relative ml-3 border-l border-[var(--border)] space-y-2">
          {runs.map((run) => (
            <li key={run.id} className="relative pl-5">
              <RunStatusDot status={run.statut} />
              <div className="flex items-start gap-2">
                <button
                  onClick={() => onOpen(run.id)}
                  className="flex-1 text-left rounded-[var(--radius-lg)] border border-[var(--border)] p-3 hover:bg-[var(--muted)] transition-colors"
                >
                  <RunSummary run={run} />
                </button>
                <button
                  onClick={() => onDelete(run.id)}
                  aria-label="Supprimer l'analyse"
                  className="mt-1 rounded-md p-2 text-[var(--muted-foreground)] hover:bg-[var(--muted)] hover:text-[var(--destructive)] transition-colors"
                >
                  <Trash2 size={14} aria-hidden="true" />
                </button>
              </div>
            </li>
          ))}
        </ol>
      )}
    </div>
  );
}
