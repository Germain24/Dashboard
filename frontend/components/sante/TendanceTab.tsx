"use client";

import { useMemo } from "react";
import {
  type MesureSante,
  type NutritionGoal,
  type ProjectionResponse,
} from "@/lib/sante";

type Props = {
  mesures: MesureSante[];
  projection: ProjectionResponse | null;
  goal: NutritionGoal | null;
};

const WIDTH = 720;
const HEIGHT = 220;
const PAD = { top: 10, right: 20, bottom: 30, left: 40 };

export function TendanceTab({ mesures, projection, goal }: Props) {
  const points = useMemo(
    () =>
      mesures
        .filter((m) => m.poids !== null && m.poids !== undefined)
        .map((m) => ({ date: new Date(m.date), weight: m.poids as number })),
    [mesures],
  );

  if (points.length === 0) {
    return (
      <div className="rounded border border-[var(--border)] p-4 text-sm text-[var(--muted-foreground)]">
        Aucune mesure de poids — saisis-en une dans l'onglet Composition.
      </div>
    );
  }

  // Limites
  const last90 = points.slice(-90);
  const xs = last90.map((p) => p.date.getTime());
  const ys = last90.map((p) => p.weight);
  const xMin = Math.min(...xs);
  const xMax = Math.max(...xs);
  const yMinRaw = Math.min(...ys);
  const yMaxRaw = Math.max(...ys);
  const yMin = Math.floor(yMinRaw - 1);
  const yMax = Math.ceil(yMaxRaw + 1);

  const xScale = (t: number) => {
    if (xMax === xMin) return PAD.left;
    return PAD.left + ((t - xMin) / (xMax - xMin)) * (WIDTH - PAD.left - PAD.right);
  };
  const yScale = (w: number) => {
    return HEIGHT - PAD.bottom - ((w - yMin) / (yMax - yMin)) * (HEIGHT - PAD.top - PAD.bottom);
  };

  const path = last90
    .map((p, i) => `${i === 0 ? "M" : "L"} ${xScale(p.date.getTime()).toFixed(1)} ${yScale(p.weight).toFixed(1)}`)
    .join(" ");

  // Ligne de tendance 30j (si dispo)
  let trendLine: { x1: number; y1: number; x2: number; y2: number } | null = null;
  if (projection?.trend_30d && last90.length >= 2) {
    const slope = projection.trend_30d.slope_kg_per_day;
    const last = last90[last90.length - 1];
    const startDate = new Date(last.date.getTime() - 30 * 86400000);
    const startW = last.weight - slope * 30;
    const futureDate = projection.target_date ? new Date(projection.target_date) : new Date(last.date.getTime() + 60 * 86400000);
    const futureW = projection.target_weight;
    trendLine = {
      x1: xScale(startDate.getTime()),
      y1: yScale(startW),
      x2: xScale(Math.min(futureDate.getTime(), xMax + 60 * 86400000)),
      y2: yScale(futureW),
    };
  }

  // Ligne d'objectif
  const goalLine = goal?.poids_cible
    ? { y: yScale(goal.poids_cible) }
    : null;

  const trend7 = projection?.trend_7d;
  const trend30 = projection?.trend_30d;

  return (
    <div className="space-y-4">
      <div className="grid grid-cols-2 md:grid-cols-4 gap-3">
        <StatCard
          label="Poids actuel"
          value={`${points[points.length - 1].weight.toFixed(1)} kg`}
          hint={`${points.length} mesures`}
        />
        <StatCard
          label="Tendance 7j"
          value={trend7 ? `${trend7.slope_kg_per_week >= 0 ? "+" : ""}${trend7.slope_kg_per_week.toFixed(2)} kg/sem` : "—"}
          hint={trend7 ? `${trend7.samples} pts` : "pas assez de données"}
        />
        <StatCard
          label="Tendance 30j"
          value={trend30 ? `${trend30.slope_kg_per_week >= 0 ? "+" : ""}${trend30.slope_kg_per_week.toFixed(2)} kg/sem` : "—"}
          hint={trend30 ? `${trend30.samples} pts` : "pas assez de données"}
        />
        <StatCard
          label="Objectif"
          value={goal?.poids_cible ? `${goal.poids_cible.toFixed(1)} kg` : "non défini"}
          hint={projection?.target_date ? `≈ ${projection.target_date}` : projection?.note ?? ""}
        />
      </div>

      {projection && (
        <div className={`rounded border px-3 py-2 text-sm ${
          projection.confidence === "high" ? "border-emerald-500/40 bg-emerald-500/10"
          : projection.confidence === "medium" ? "border-blue-500/40 bg-blue-500/10"
          : "border-amber-500/40 bg-amber-500/10"
        }`}>
          {projection.note}
        </div>
      )}

      <div className="rounded border border-[var(--border)] p-3 overflow-x-auto">
        <svg viewBox={`0 0 ${WIDTH} ${HEIGHT}`} className="w-full h-auto">
          {/* Axe Y graduations */}
          {[yMin, Math.round((yMin + yMax) / 2), yMax].map((y) => (
            <g key={y}>
              <line x1={PAD.left} y1={yScale(y)} x2={WIDTH - PAD.right} y2={yScale(y)} stroke="currentColor" strokeOpacity={0.1} />
              <text x={PAD.left - 4} y={yScale(y) + 4} fontSize="10" textAnchor="end" fill="currentColor" opacity={0.5}>
                {y}
              </text>
            </g>
          ))}
          {/* Objectif */}
          {goalLine && (
            <line
              x1={PAD.left}
              y1={goalLine.y}
              x2={WIDTH - PAD.right}
              y2={goalLine.y}
              stroke="#10b981"
              strokeDasharray="4 4"
              opacity={0.7}
            />
          )}
          {/* Trend line */}
          {trendLine && (
            <line
              x1={trendLine.x1}
              y1={trendLine.y1}
              x2={trendLine.x2}
              y2={trendLine.y2}
              stroke="#3b82f6"
              strokeDasharray="6 4"
              strokeWidth={1.5}
              opacity={0.6}
            />
          )}
          {/* Série */}
          <path d={path} fill="none" stroke="currentColor" strokeWidth={1.5} />
          {last90.map((p, i) => (
            <circle
              key={i}
              cx={xScale(p.date.getTime())}
              cy={yScale(p.weight)}
              r={2}
              fill="currentColor"
            />
          ))}
        </svg>
        <div className="text-xs text-[var(--muted-foreground)] mt-1">
          90 derniers jours · ligne pointillée bleue = tendance 30j · pointillé vert = objectif
        </div>
      </div>
    </div>
  );
}

function StatCard({ label, value, hint }: { label: string; value: string; hint?: string }) {
  return (
    <div className="rounded border border-[var(--border)] p-3">
      <div className="text-xs text-[var(--muted-foreground)]">{label}</div>
      <div className="text-lg font-semibold">{value}</div>
      {hint && <div className="text-xs text-[var(--muted-foreground)] mt-0.5">{hint}</div>}
    </div>
  );
}
