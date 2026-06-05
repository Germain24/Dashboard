"use client";

/** Stats d'étude : objectif (#95), temps/matière (#94), streak (#101), heatmap (#97), rapport hebdo (#102). */

import { useCallback, useEffect, useMemo, useState } from "react";
import { toast } from "sonner";
import { fetchEtudesStats, setEtudesGoal, type EtudesStats } from "@/lib/etudes";
import { Skeleton } from "@/components/ui/skeleton";

function fmtH(min: number): string {
  const h = Math.floor(min / 60);
  const m = min % 60;
  return h > 0 ? `${h}h${m > 0 ? String(m).padStart(2, "0") : ""}` : `${m}min`;
}

export function StatistiquesTab() {
  const [stats, setStats] = useState<EtudesStats | null>(null);
  const [goalInput, setGoalInput] = useState("");
  const [savingGoal, setSavingGoal] = useState(false);

  const [error, setError] = useState(false);

  const load = useCallback(() => {
    let active = true;
    fetchEtudesStats(120)
      .then((s) => { if (active) { setStats(s); setError(false); } })
      .catch(() => active && setError(true));
    return () => { active = false; };
  }, []);
  useEffect(() => load(), [load]);

  const saveGoal = async () => {
    const h = parseFloat(goalInput);
    if (!Number.isFinite(h) || h < 0) return;
    setSavingGoal(true);
    try { await setEtudesGoal(h); setGoalInput(""); load(); }
    catch { toast.error("Impossible d'enregistrer l'objectif."); }
    finally { setSavingGoal(false); }
  };

  if (error) {
    return (
      <div className="flex flex-col items-start gap-2 py-2">
        <p className="text-sm text-[var(--muted-foreground)]">Statistiques indisponibles pour le moment.</p>
        <button onClick={() => { setError(false); load(); }}
          className="rounded border border-[var(--border)] px-2.5 py-1 text-xs font-medium hover:bg-[var(--accent)]">
          Réessayer
        </button>
      </div>
    );
  }

  if (!stats) return <Skeleton lines={6} />;

  const maxCourse = Math.max(1, ...stats.by_course.map((c) => c.minutes));

  return (
    <div className="space-y-6">
      {/* Objectif hebdo (#95) + streak (#101) */}
      <div className="grid gap-3 sm:grid-cols-2">
        <div className="rounded-lg border border-[var(--border)] bg-[var(--card)] p-4">
          <div className="flex items-center justify-between mb-2">
            <span className="text-sm font-medium">Objectif de la semaine</span>
            <span className="text-xs text-[var(--muted-foreground)] tabular-nums">
              {stats.goal.done_hours}h / {stats.goal.weekly_hours}h
            </span>
          </div>
          <div className="h-2 rounded-full bg-[var(--border)] overflow-hidden">
            <div
              className="h-full rounded-full transition-all"
              style={{ width: `${stats.goal.progress_pct}%`, backgroundColor: stats.goal.progress_pct >= 100 ? "var(--success)" : "var(--ring)" }}
            />
          </div>
          <div className="mt-2 flex gap-2">
            <input
              type="number" step="0.5" min="0" placeholder={`${stats.goal.weekly_hours}`}
              value={goalInput} onChange={(e) => setGoalInput(e.target.value)}
              className="w-20 border rounded px-2 py-1 text-sm bg-transparent"
            />
            <button onClick={() => void saveGoal()} disabled={savingGoal || !goalInput}
              className="px-2 py-1 text-xs border border-[var(--border)] text-[var(--foreground)] rounded hover:bg-[var(--accent)] disabled:opacity-50">
              Définir l&apos;objectif (h/sem)
            </button>
          </div>
        </div>

        <div className="rounded-lg border border-[var(--border)] bg-[var(--card)] p-4 flex items-center gap-6">
          <div className="text-center">
            <div className="text-3xl font-bold text-[var(--tertiary)]">🔥 {stats.streak.current}</div>
            <div className="text-xs text-[var(--muted-foreground)]">jours d&apos;affilée</div>
          </div>
          <div className="text-center">
            <div className="text-3xl font-bold">{stats.streak.best}</div>
            <div className="text-xs text-[var(--muted-foreground)]">meilleure série</div>
          </div>
        </div>
      </div>

      {/* Rapport hebdo (#102) */}
      <div className="rounded-lg border border-[var(--border)] bg-[var(--card)] p-4">
        <h3 className="text-sm font-semibold mb-1">Cette semaine</h3>
        <p className="text-sm text-[var(--muted-foreground)]">
          {fmtH(stats.weekly.total_minutes)} sur {stats.weekly.sessions} session{stats.weekly.sessions > 1 ? "s" : ""}
          {stats.weekly.by_course.length > 0 && (
            <> · {stats.weekly.by_course.slice(0, 3).map((c) => `${c.label} (${fmtH(c.minutes)})`).join(", ")}</>
          )}
        </p>
      </div>

      {/* Temps par matière (#94) */}
      <div>
        <h3 className="text-sm font-semibold mb-2">Temps par matière (120 j)</h3>
        {stats.by_course.length === 0 ? (
          <p className="text-sm text-[var(--muted-foreground)]">Aucune session enregistrée.</p>
        ) : (
          <div className="space-y-1.5">
            {stats.by_course.map((c) => (
              <div key={String(c.cours_id)} className="flex items-center gap-2 text-sm">
                <div className="w-24 truncate" title={c.label}>{c.label}</div>
                <div className="flex-1 h-3 bg-[var(--border)] rounded overflow-hidden">
                  <div className="h-full bg-[var(--ring)]" style={{ width: `${(c.minutes / maxCourse) * 100}%` }} />
                </div>
                <div className="w-16 text-right text-xs text-[var(--muted-foreground)] tabular-nums">{fmtH(c.minutes)}</div>
              </div>
            ))}
          </div>
        )}
      </div>

      {/* Heatmap régularité (#97) */}
      <Heatmap daily={stats.daily} />
    </div>
  );
}

function Heatmap({ daily }: { daily: Record<string, number> }) {
  // 18 dernières semaines, colonnes = semaines, lignes = jours (lun→dim).
  const weeks = useMemo(() => {
    const today = new Date();
    const end = new Date(today);
    // reculer jusqu'au dimanche courant pour aligner les colonnes
    const cols: { date: string; min: number }[][] = [];
    const start = new Date(end);
    start.setDate(end.getDate() - 18 * 7);
    // aligner sur lundi
    const startDay = start.getDay();
    start.setDate(start.getDate() + (startDay === 0 ? 1 : 1 - startDay));
    const cur = new Date(start);
    while (cur <= end) {
      const col: { date: string; min: number }[] = [];
      for (let i = 0; i < 7; i++) {
        const ds = `${cur.getFullYear()}-${String(cur.getMonth() + 1).padStart(2, "0")}-${String(cur.getDate()).padStart(2, "0")}`;
        col.push({ date: ds, min: daily[ds] || 0 });
        cur.setDate(cur.getDate() + 1);
      }
      cols.push(col);
    }
    return cols;
  }, [daily]);

  const color = (min: number) => {
    if (min === 0) return "var(--border)";
    if (min < 30) return "color-mix(in srgb, var(--ring) 22%, transparent)";
    if (min < 60) return "color-mix(in srgb, var(--ring) 45%, transparent)";
    if (min < 120) return "color-mix(in srgb, var(--ring) 70%, transparent)";
    return "var(--ring)";
  };

  return (
    <div>
      <h3 className="text-sm font-semibold mb-2">Régularité</h3>
      <div className="flex gap-[3px] overflow-x-auto">
        {weeks.map((col, ci) => (
          <div key={ci} className="flex flex-col gap-[3px]">
            {col.map((cell) => (
              <div
                key={cell.date}
                className="h-3 w-3 rounded-[2px]"
                style={{ backgroundColor: color(cell.min) }}
                title={`${cell.date} · ${cell.min} min`}
              />
            ))}
          </div>
        ))}
      </div>
    </div>
  );
}
