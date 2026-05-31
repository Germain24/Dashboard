"use client";

import { useEffect, useState } from "react";
import {
  entrainementApi,
  type Exercice,
  type ProgressionResponse,
} from "@/lib/entrainement";

type Props = {
  exercices: Exercice[];
};

export function ProgressionTab({ exercices }: Props) {
  const muscuExos = exercices.filter((e) => e.categorie !== "cardio");
  const [selected, setSelected] = useState<number | null>(
    muscuExos.find((e) => e.nom === "Squat barre")?.id ?? muscuExos[0]?.id ?? null,
  );
  const [days, setDays] = useState<number>(90);
  const [data, setData] = useState<ProgressionResponse | null>(null);
  const [loading, setLoading] = useState(false);
  const [err, setErr] = useState<string | null>(null);

  useEffect(() => {
    if (!selected) {
      setData(null);
      return;
    }
    let cancelled = false;
    setLoading(true);
    setErr(null);
    entrainementApi
      .getProgression(selected, days)
      .then((d) => { if (!cancelled) setData(d); })
      .catch((e) => { if (!cancelled) setErr(e?.message ?? "Erreur"); })
      .finally(() => { if (!cancelled) setLoading(false); });
    return () => { cancelled = true; };
  }, [selected, days]);

  return (
    <div className="space-y-4">
      <div className="flex flex-wrap items-end gap-2 text-xs">
        <label className="flex flex-col">
          Exercice
          <select
            value={selected ?? ""}
            onChange={(e) => setSelected(parseInt(e.target.value, 10))}
            className="mt-1 min-w-[260px] rounded border border-[var(--border)] bg-transparent px-2 py-1"
          >
            {muscuExos.map((e) => (
              <option key={e.id} value={e.id}>
                [{e.categorie}] {e.nom}
              </option>
            ))}
          </select>
        </label>
        <label className="flex flex-col">
          Période
          <select
            value={days}
            onChange={(e) => setDays(parseInt(e.target.value, 10))}
            className="mt-1 rounded border border-[var(--border)] bg-transparent px-2 py-1"
          >
            <option value={30}>30 j</option>
            <option value={90}>90 j</option>
            <option value={180}>180 j</option>
            <option value={365}>1 an</option>
          </select>
        </label>
      </div>

      {loading && <div className="text-sm text-[var(--muted-foreground)]">Chargement…</div>}
      {err && <div className="text-sm text-[var(--destructive)]">⚠ {err}</div>}

      {data && (
        <>
          <div className="grid grid-cols-2 sm:grid-cols-4 gap-3 text-sm">
            <Stat label="1RM courant" value={`${data.current_1rm_kg.toFixed(1)} kg`} />
            <Stat label="1RM record" value={`${data.best_1rm_kg.toFixed(1)} kg`} />
            <Stat
              label="Δ 4 semaines"
              value={data.delta_4w_pct !== null ? `${data.delta_4w_pct.toFixed(1)} %` : "—"}
              positive={data.delta_4w_pct !== null && data.delta_4w_pct > 0}
              negative={data.delta_4w_pct !== null && data.delta_4w_pct < 0}
            />
            <Stat label="Séances" value={String(data.points.length)} />
          </div>

          <ProgressionChart points={data.points} />

          {data.points.length > 0 && (
            <div className="rounded border border-[var(--border)] overflow-hidden">
              <table className="w-full text-sm">
                <thead className="bg-[var(--muted)]/50 text-xs uppercase text-[var(--muted-foreground)]">
                  <tr>
                    <th className="text-left px-3 py-2">Date</th>
                    <th className="text-right px-3 py-2">1RM (Epley)</th>
                    <th className="text-right px-3 py-2">Top set</th>
                    <th className="text-right px-3 py-2">Volume</th>
                    <th className="text-right px-3 py-2">Séries</th>
                  </tr>
                </thead>
                <tbody>
                  {[...data.points].reverse().map((p, i) => (
                    <tr key={i} className="border-t border-[var(--border)]">
                      <td className="px-3 py-1.5">{p.date}</td>
                      <td className="px-3 py-1.5 text-right">{p.best_1rm_kg.toFixed(1)} kg</td>
                      <td className="px-3 py-1.5 text-right">{p.top_set_kg.toFixed(1)} kg</td>
                      <td className="px-3 py-1.5 text-right">{p.volume_kg.toFixed(0)} kg</td>
                      <td className="px-3 py-1.5 text-right">{p.nb_sets}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )}
        </>
      )}
    </div>
  );
}

function Stat({
  label, value, positive, negative,
}: { label: string; value: string; positive?: boolean; negative?: boolean }) {
  return (
    <div className="rounded border border-[var(--border)] p-3">
      <div className="text-xs text-[var(--muted-foreground)]">{label}</div>
      <div className={`text-lg font-semibold ${positive ? "text-[var(--success)]" : negative ? "text-[var(--destructive)]" : ""}`}>
        {value}
      </div>
    </div>
  );
}

function ProgressionChart({ points }: { points: ProgressionResponse["points"] }) {
  if (points.length < 2) {
    return (
      <div className="rounded border border-dashed border-[var(--border)] p-6 text-center text-sm text-[var(--muted-foreground)]">
        Pas assez de données pour tracer la courbe (besoin de ≥ 2 séances).
      </div>
    );
  }
  const W = 600, H = 160, PAD = 24;
  const xs = points.map((p) => new Date(p.date).getTime());
  const ys = points.map((p) => p.best_1rm_kg);
  const xmin = Math.min(...xs), xmax = Math.max(...xs);
  const ymin = Math.min(...ys) * 0.95, ymax = Math.max(...ys) * 1.05;
  const sx = (x: number) =>
    PAD + ((x - xmin) / Math.max(1, xmax - xmin)) * (W - 2 * PAD);
  const sy = (y: number) =>
    H - PAD - ((y - ymin) / Math.max(0.1, ymax - ymin)) * (H - 2 * PAD);
  const path = points
    .map((p, i) => `${i === 0 ? "M" : "L"} ${sx(new Date(p.date).getTime()).toFixed(1)} ${sy(p.best_1rm_kg).toFixed(1)}`)
    .join(" ");
  return (
    <div className="rounded border border-[var(--border)] p-3">
      <svg viewBox={`0 0 ${W} ${H}`} className="w-full h-40">
        <path d={path} fill="none" stroke="currentColor" strokeWidth={2} />
        {points.map((p, i) => (
          <circle
            key={i}
            cx={sx(new Date(p.date).getTime())}
            cy={sy(p.best_1rm_kg)}
            r={3}
            fill="currentColor"
          />
        ))}
      </svg>
    </div>
  );
}
