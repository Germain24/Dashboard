import type { OptProgress } from "./buffett-ui";

function isOlderOptimization(current: OptProgress | null, next: OptProgress) {
  return current?.optimization_started_at != null
    && next.optimization_started_at != null
    && next.optimization_started_at < current.optimization_started_at;
}

type ScorePoint = NonNullable<OptProgress["score_history"]>[number];

function previousPoints(current: OptProgress | null, next: OptProgress) {
  if (!current) return [];
  if (current.optimization_id !== next.optimization_id) return [];
  if (!current.score_history) return [];
  return current.score_history;
}

function scoreMap(current: OptProgress | null, next: OptProgress) {
  const points = new Map(
    previousPoints(current, next).map(
      (point) => [point.iteration, point],
    ),
  );
  addPoints(points, next.score_history);
  return points;
}

function addPoints(
  points: Map<number, ScorePoint>,
  incoming: OptProgress["score_history"],
) {
  for (const point of incoming ?? []) points.set(point.iteration, point);
}

function mergeScoreHistory(current: OptProgress | null, next: OptProgress) {
  const points = scoreMap(current, next);
  return [...points.values()].sort((a, b) => a.iteration - b.iteration);
}

export function mergeOptimizationProgress(
  current: OptProgress | null,
  next: OptProgress,
): OptProgress | null {
  if (isOlderOptimization(current, next)) return current;
  return { ...next, score_history: mergeScoreHistory(current, next) };
}
