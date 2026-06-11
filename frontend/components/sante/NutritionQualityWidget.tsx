"use client";

/** Score de qualité nutritionnelle sur 7 jours (#65). */

import type { WeeklyQuality } from "@/lib/sante";
import { useWeeklyQuality } from "@/lib/queries/sante";

function scoreColor(s: number): string {
  if (s >= 80) return "var(--success)";
  if (s >= 60) return "var(--warning)";
  return "var(--destructive)";
}

export function NutritionQualityWidget() {
  const q: WeeklyQuality | null = useWeeklyQuality(7).data ?? null;

  if (!q || q.score === null) return null;

  return (
    <div className="rounded-[var(--radius-lg)] border border-[var(--border)] p-4 flex items-center gap-4">
      <div className="flex flex-col items-center justify-center shrink-0">
        <span className="text-2xl font-bold tabular-nums" style={{ color: scoreColor(q.score) }}>
          {q.score}
        </span>
        <span className="text-[10px] uppercase tracking-wide text-[var(--muted-foreground)]">/ 100</span>
      </div>
      <div className="min-w-0 space-y-1">
        <h3 className="text-sm font-semibold">🥗 Qualité nutritionnelle · 7 j</h3>
        <p className="text-xs text-[var(--muted-foreground)]">
          {q.days} jour{q.days > 1 ? "s" : ""} avec conso enregistrée
          {q.worst && <> · point faible : <strong>{q.worst}</strong></>}
          {q.best && <> · point fort : <strong>{q.best}</strong></>}
        </p>
        {q.criteria_avg && (
          <div className="flex flex-wrap gap-1.5 pt-0.5">
            {Object.entries(q.criteria_avg).map(([k, v]) => (
              <span
                key={k}
                className="text-[10px] rounded px-1.5 py-0.5 tabular-nums"
                style={{ background: "var(--muted)", color: scoreColor(v) }}
                title={`${k} : ${v}/100`}
              >
                {k} {v}
              </span>
            ))}
          </div>
        )}
      </div>
    </div>
  );
}
