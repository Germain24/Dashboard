"use client";

/** Courbe en direct du score STARR, colorée par la température du recuit. */

import { useEffect, useId, useRef, useState } from "react";
import { fmt, type OptProgress } from "./buffett-ui";

type ScorePoint = NonNullable<OptProgress["score_history"]>[number];
const STORAGE_PREFIX = "buffett-de-history-v2-";
const STORAGE_LIMIT = 20_000;
const GRADIENT_STOPS = 48;
const CHART_WIDTH = 100;
const CHART_HEIGHT = 28;

function isRecord(value: unknown): value is Record<string, unknown> {
  return typeof value === "object" && value !== null;
}

function isNumberField(point: Record<string, unknown>, key: string) {
  return typeof point[key] === "number";
}

function isFiniteTemperature(value: unknown): value is number {
  return typeof value === "number" && Number.isFinite(value);
}

function isScorePoint(value: unknown): value is ScorePoint {
  if (!isRecord(value)) return false;
  const fields = ["iteration", "seed_num", "seed_iteration", "score"];
  return fields.every((field) => isNumberField(value, field))
    && Number.isFinite(value.score);
}

export function temperatureColor(temperature: number): string {
  const clamped = Math.min(1, Math.max(0, temperature));
  if (clamped <= 0.5) {
    const share = (clamped / 0.5) * 100;
    return `color-mix(in oklab, var(--temp-mid) ${share.toFixed(1)}%, var(--temp-cold))`;
  }
  const share = ((clamped - 0.5) / 0.5) * 100;
  return `color-mix(in oklab, var(--temp-hot) ${share.toFixed(1)}%, var(--temp-mid))`;
}

function accumulateTemperatures(
  history: ScorePoint[],
  position: (point: ScorePoint) => number,
) {
  const sums = new Array<number>(GRADIENT_STOPS).fill(0);
  const counts = new Array<number>(GRADIENT_STOPS).fill(0);
  let seen = false;
  for (const point of history) {
    const temperature = point.temperature;
    if (!isFiniteTemperature(temperature)) continue;
    seen = true;
    const ratio = Math.min(1, Math.max(0, position(point)));
    const index = Math.round(ratio * (GRADIENT_STOPS - 1));
    sums[index] += temperature;
    counts[index] += 1;
  }
  if (!seen) return null;
  return sums.map((sum, index) => counts[index] > 0 ? sum / counts[index] : null);
}

function fillFromStart(buckets: (number | null)[]) {
  let carried: number | null = null;
  return buckets.map((value) => {
    if (value !== null) carried = value;
    return value ?? carried;
  });
}

function fillFromEnd(buckets: (number | null)[]) {
  let carried: number | null = null;
  return buckets.map((value, index) => {
    const reverseIndex = buckets.length - index - 1;
    const current = buckets[reverseIndex];
    if (current !== null) carried = current;
    return current ?? carried;
  }).reverse();
}

/** Températures moyennées par tranche, avec propagation dans les tranches vides. */
export function temperatureBuckets(
  history: ScorePoint[],
  position: (point: ScorePoint) => number,
): (number | null)[] | null {
  const buckets = accumulateTemperatures(history, position);
  if (!buckets) return null;
  return fillFromEnd(fillFromStart(buckets));
}

function loadHistory(optimizationId: string): ScorePoint[] {
  try {
    const raw = sessionStorage.getItem(STORAGE_PREFIX + optimizationId);
    if (!raw) return [];
    const parsed: unknown = JSON.parse(raw);
    if (!Array.isArray(parsed)) return [];
    return parsed.filter(isScorePoint);
  } catch {
    return [];
  }
}

function saveHistory(optimizationId: string, history: ScorePoint[]) {
  try {
    sessionStorage.setItem(
      STORAGE_PREFIX + optimizationId,
      JSON.stringify(history.slice(-STORAGE_LIMIT)),
    );
  } catch {
    // Le graphe courant reste valide si sessionStorage est indisponible.
  }
}

function mergeHistory(
  current: ScorePoint[],
  optimizationId: string,
  incoming: ScorePoint[],
  changed: boolean,
) {
  const base = changed ? loadHistory(optimizationId) : current;
  const merged = new Map(base.map((point) => [point.iteration, point]));
  for (const point of incoming) merged.set(point.iteration, point);
  const next = [...merged.values()].sort((a, b) => a.iteration - b.iteration);
  saveHistory(optimizationId, next);
  return next;
}

function incomingPoints(progress: OptProgress | null) {
  if (!progress) return [];
  return (progress.score_history ?? []).filter((point) => Number.isFinite(point.score));
}

function activeOptimizationId(progress: OptProgress | null) {
  if (!progress?.active) return null;
  return progress.optimization_id;
}

function syncChartHistory(
  optProgress: OptProgress | null,
  lastOptimizationRef: { current: string | null },
  setHistory: (updater: (current: ScorePoint[]) => ScorePoint[]) => void,
) {
  const optimizationId = activeOptimizationId(optProgress);
  if (!optimizationId) return;
  const changed = lastOptimizationRef.current !== optimizationId;
  if (changed) lastOptimizationRef.current = optimizationId;
  setHistory((current) => mergeHistory(
    current,
    optimizationId,
    incomingPoints(optProgress),
    changed,
  ));
}

function useChartHistory(optProgress: OptProgress | null) {
  const [history, setHistory] = useState<ScorePoint[]>([]);
  const lastOptimizationRef = useRef<string | null>(null);

  useEffect(() => {
    syncChartHistory(optProgress, lastOptimizationRef, setHistory);
  }, [optProgress]);

  return history;
}

type ChartScorePoint = { iteration: number; score: number };

function bounds(series: ChartScorePoint[]) {
  return series.reduce(
    (result, point) => ({
      min: Math.min(result.min, point.score),
      max: Math.max(result.max, point.score),
    }),
    { min: Number.POSITIVE_INFINITY, max: Number.NEGATIVE_INFINITY },
  );
}

function scoreBest(history: ScorePoint[]) {
  return history.reduce(
    (best, point) => point.score > best.score ? point : best,
    history[0],
  ).score;
}

function globalBest(progress: OptProgress | null, history: ScorePoint[]) {
  return progress?.best_score ?? scoreBest(history);
}

function chartCoordinates(
  series: ChartScorePoint[],
  xFor: (iteration: number) => number,
  yFor: (score: number) => number,
) {
  return series.map((point) =>
    `${xFor(point.iteration).toFixed(2)},${yFor(point.score).toFixed(2)}`
  ).join(" ");
}

function cumulativeGlobalSeries(history: ScorePoint[]): ChartScorePoint[] {
  let best = Number.NEGATIVE_INFINITY;
  return history.map((point) => {
    const reported = point.global_best_score;
    const candidate = typeof reported === "number" && Number.isFinite(reported)
      ? reported
      : point.score;
    best = Math.max(best, candidate);
    return { iteration: point.iteration, score: best };
  });
}

function cumulativeSeedSeries(history: ScorePoint[]): ChartScorePoint[] {
  let currentSeed: number | null = null;
  let best = Number.NEGATIVE_INFINITY;
  return history.map((point) => {
    if (currentSeed !== point.seed_num) {
      currentSeed = point.seed_num;
      best = Number.NEGATIVE_INFINITY;
    }
    best = Math.max(best, point.score);
    return { iteration: point.iteration, score: best };
  });
}

function chartStroke(buckets: (number | null)[] | null, gradientId: string) {
  if (buckets) return `url(#${gradientId})`;
  return "var(--temp-cold)";
}

function forcedExploration(history: ScorePoint[]) {
  const epochs = history.filter((point) =>
    isForcedEpoch(point)
  );
  const epoch = epochs.at(-1);
  if (!epoch) return null;
  const index = epochs.length - 1;
  const end = nextEpochEnd(epochs, index, history.at(-1)!.iteration);
  const window = history.filter((point) =>
    point.iteration >= epoch.iteration && point.iteration < end
  );
  const baseline = epoch.global_best_score ?? epoch.score;
  const best = bestInWindow(window, baseline);
  return { epoch, index, best, baseline, gain: best - baseline };
}

function isForcedEpoch(point: ScorePoint) {
  return Array.isArray(point.forced_labels) && point.forced_labels.length > 0;
}

function nextEpochEnd(epochs: ScorePoint[], index: number, lastIteration: number) {
  const next = epochs[index + 1];
  if (next) return next.iteration;
  return lastIteration + 1;
}

function bestInWindow(window: ScorePoint[], baseline: number) {
  if (!window.length) return baseline;
  return Math.max(...window.map((point) => point.global_best_score ?? point.score));
}

function temperatureValues(buckets: (number | null)[] | null) {
  return buckets?.filter((value): value is number => value !== null) ?? [];
}

function lastTemperature(lastPoint: ScorePoint, progress: OptProgress | null) {
  if (isFiniteTemperature(lastPoint.temperature)) return lastPoint.temperature;
  if (isFiniteTemperature(progress?.temperature)) return progress.temperature;
  return null;
}

function temperatureSummary(
  buckets: (number | null)[] | null,
  lastPoint: ScorePoint,
  progress: OptProgress | null,
) {
  const values = temperatureValues(buckets);
  return {
    min: values.length ? Math.min(...values) : null,
    max: values.length ? Math.max(...values) : null,
    last: lastTemperature(lastPoint, progress),
  };
}

type ChartData = {
  history: ScorePoint[];
  gradientId: string;
  width: number;
  height: number;
  min: number;
  max: number;
  globalBest: number;
  buckets: (number | null)[] | null;
  stroke: string;
  seedCoords: string;
  globalCoords: string;
  lastPoint: ScorePoint;
  seedBest: number;
  temperatures: { min: number | null; max: number | null; last: number | null };
  forced: ReturnType<typeof forcedExploration>;
};

function buildChartData(
  history: ScorePoint[],
  progress: OptProgress | null,
  gradientId: string,
): ChartData {
  const seedSeries = cumulativeSeedSeries(history);
  const globalSeries = cumulativeGlobalSeries(history);
  const { min, max } = bounds([...seedSeries, ...globalSeries]);
  const first = history[0].iteration;
  const lastPoint = history.at(-1)!;
  const iterationSpan = Math.max(1, lastPoint.iteration - first);
  const span = max - min || 1;
  const xFor = (iteration: number) => ((iteration - first) / iterationSpan) * CHART_WIDTH;
  const yFor = (score: number) => CHART_HEIGHT - ((score - min) / span) * CHART_HEIGHT;
  const position = (point: ScorePoint) => (point.iteration - first) / iterationSpan;
  const globalScore = globalBest(progress, history);
  const buckets = temperatureBuckets(history, position);
  return {
    history,
    gradientId,
    width: CHART_WIDTH,
    height: CHART_HEIGHT,
    min,
    max,
    globalBest: globalScore,
    buckets,
    stroke: chartStroke(buckets, gradientId),
    seedCoords: chartCoordinates(seedSeries, xFor, yFor),
    globalCoords: chartCoordinates(globalSeries, xFor, yFor),
    lastPoint,
    seedBest: seedSeries.at(-1)!.score,
    temperatures: temperatureSummary(buckets, lastPoint, progress),
    forced: forcedExploration(history),
  };
}

function ChartGradient({ id, buckets }: { id: string; buckets: (number | null)[] }) {
  return (
    <defs>
      <linearGradient id={id} gradientUnits="userSpaceOnUse" x1={0} y1={0} x2={CHART_WIDTH} y2={0}>
        {buckets.map((temperature, index) => (
          <stop key={index} offset={`${((index / (GRADIENT_STOPS - 1)) * 100).toFixed(2)}%`} stopColor={temperatureColor(temperature ?? 0)} />
        ))}
      </linearGradient>
    </defs>
  );
}

function TemperatureGradient({ id, buckets }: { id: string; buckets: (number | null)[] | null }) {
  if (!buckets) return null;
  return <ChartGradient id={id} buckets={buckets} />;
}

function formatTemperatureLabel(temperature: ChartData["temperatures"]) {
  if (temperature.min === null || temperature.max === null) return "";
  return `, température de ${fmt(temperature.min, 2)} à ${fmt(temperature.max, 2)}`;
}

function lastPointColor(temperature: number | null) {
  if (temperature === null) return "var(--temp-cold)";
  return temperatureColor(temperature);
}

function ForcedMarkers({
  data,
  xFor,
  height,
}: {
  data: ChartData["forced"];
  xFor: (iteration: number) => number;
  height: number;
}) {
  if (!data) return null;
  const labels = data.epoch.forced_labels ?? [];
  return (
    <g>
      <title>{`Exploration ${data.index + 1}, génération ${data.epoch.seed_iteration} · ${labels.length} portefeuilles séparés`}</title>
      <line x1={xFor(data.epoch.iteration)} y1={0} x2={xFor(data.epoch.iteration)} y2={height} stroke="var(--warning)" strokeWidth={0.45} strokeDasharray="1 1" opacity={0.8} vectorEffect="non-scaling-stroke" />
      <circle cx={xFor(data.epoch.iteration)} cy={2.2} r={1.25} fill="var(--warning)" />
    </g>
  );
}

function ChartSvg({ data }: { data: ChartData }) {
  const { history, buckets, gradientId, width, height, min, globalCoords, seedCoords, stroke, lastPoint } = data;
  const first = history[0].iteration;
  const span = Math.max(1, lastPoint.iteration - first);
  const xFor = (iteration: number) => ((iteration - first) / span) * width;
  const yFor = (score: number) => height - ((score - min) / (data.max - min || 1)) * height;
  const temperatureLabel = formatTemperatureLabel(data.temperatures);
  return (
    <svg
      viewBox={`0 0 ${width} ${height}`}
      preserveAspectRatio="none"
      className="h-20 w-full"
      role="img"
      aria-label={`Évolution du score sur ${history.length} générations${temperatureLabel}`}
    >
      <TemperatureGradient id={gradientId} buckets={buckets} />
      <polyline data-testid="global-series" points={globalCoords} fill="none" stroke="var(--muted-foreground)" strokeWidth={0.9} opacity={0.85} vectorEffect="non-scaling-stroke" />
      <polyline data-testid="score-series" points={seedCoords} fill="none" stroke={stroke} strokeWidth={0.8} vectorEffect="non-scaling-stroke" />
      <ForcedMarkers data={data.forced} xFor={xFor} height={height} />
      <circle cx={xFor(lastPoint.iteration)} cy={yFor(lastPoint.score)} r={1.05} fill={lastPointColor(data.temperatures.last)} />
    </svg>
  );
}

function forcedHasCounts(forced: NonNullable<ChartData["forced"]>) {
  return forced.epoch.forced_action_count !== undefined
    || forced.epoch.forced_etf_count !== undefined;
}

function forcedGainLabel(gain: number) {
  if (gain > 1e-9) return `Nouveau meilleur observé pendant la fenêtre : +${fmt(gain, 4)}`;
  return "Aucun nouveau meilleur observé pendant cette fenêtre pour l’instant.";
}

function ForcedCounts({ forced }: { forced: NonNullable<ChartData["forced"]> }) {
  if (!forcedHasCounts(forced)) return null;
  return (
    <p className="mt-1 font-medium text-[var(--foreground)]">
      {forced.epoch.forced_action_count ?? 0} action(s) · {forced.epoch.forced_etf_count ?? 0} ETF/fonds
    </p>
  );
}

function ForcedLabels({ labels }: { labels: string[] }) {
  return (
    <div className="mt-2 flex max-h-32 flex-wrap gap-1.5 overflow-y-auto">
      {labels.map((label) => (
        <span key={label} className="rounded-[var(--radius-full)] border border-[var(--border)] bg-[var(--card)] px-2 py-1 font-mono text-[10px] text-[var(--foreground)]">{label}</span>
      ))}
    </div>
  );
}

function ForcedDetails({ forced }: { forced: NonNullable<ChartData["forced"]> }) {
  const labels = forced.epoch.forced_labels ?? [];
  return (
    <details className="mt-2 rounded-[var(--radius-md)] bg-[var(--muted)] px-3 py-2 text-xs text-[var(--muted-foreground)]">
      <summary className="cursor-pointer font-semibold text-[var(--foreground)]">
        Exploration {forced.index + 1} · génération {forced.epoch.seed_iteration} · {labels.length} portefeuilles séparés
      </summary>
      <p className="mt-2">Chaque ligne ouvre un bassin différent : le ticker est brièvement imposé au minimum indiqué, puis la contrainte est retirée et le portefeuille poursuit une optimisation libre bornée. Les pourcentages ne sont jamais cumulés dans un même portefeuille.</p>
      <ForcedCounts forced={forced} />
      <p className="mt-1 font-medium text-[var(--foreground)]">{forcedGainLabel(forced.gain)}</p>
      <ForcedLabels labels={labels} />
    </details>
  );
}

function ChartLegend({ temperature }: { temperature: ChartData["temperatures"] }) {
  return (
    <div className="mt-2 flex items-center gap-2 text-[10px] tabular-nums text-[var(--muted-foreground)]">
      <span>froid · exploite</span>
      <span aria-hidden="true" className="h-1.5 flex-1 rounded-[var(--radius-full)]" style={{ background: "linear-gradient(to right, var(--temp-cold), var(--temp-mid), var(--temp-hot))" }} />
      <span>explore · chaud</span>
      {temperature.last !== null && <span className="shrink-0 font-semibold text-[var(--foreground)]">T&nbsp;{fmt(temperature.last, 2)}</span>}
    </div>
  );
}

function ChartCard({ data }: { data: ChartData }) {
  return (
    <div className="rounded-[var(--radius-lg)] border border-[var(--border)] p-4">
      <div className="mb-2 flex items-baseline justify-between gap-3">
        <p className="text-xs font-semibold text-[var(--muted-foreground)]">Scores continus déployés avant arrondi</p>
        <span className="shrink-0 text-xs tabular-nums text-[var(--muted-foreground)]">global&nbsp;: {fmt(data.globalBest, 4)} · seed&nbsp;: {fmt(data.seedBest, 4)}</span>
      </div>
      <ChartSvg data={data} />
      {data.forced && <ForcedDetails forced={data.forced} />}
      <ChartLegend temperature={data.temperatures} />
      <div className="mt-1 flex items-center gap-3 text-[10px] tabular-nums text-[var(--muted-foreground)]">
        <span><span className="mr-1 inline-block w-4 border-t border-[var(--muted-foreground)]" />meilleur global</span>
        <span><span className="mr-1 inline-block w-4 border-t-2 border-[var(--temp-mid)]" />meilleur seed courante</span>
      </div>
      <div className="mt-1 flex justify-between text-[10px] tabular-nums text-[var(--muted-foreground)]">
        <span>{data.history.length.toLocaleString("fr-CA")} générations</span>
        <span>min {fmt(data.min, 4)} · max {fmt(data.max, 4)}</span>
      </div>
    </div>
  );
}

export function DeStarrChart({ optProgress }: { optProgress: OptProgress | null }) {
  const history = useChartHistory(optProgress);
  const gradientId = useId();
  if (history.length < 2) return null;
  return <ChartCard data={buildChartData(history, optProgress, gradientId)} />;
}
