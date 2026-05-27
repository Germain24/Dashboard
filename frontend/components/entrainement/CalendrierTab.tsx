"use client";

import { useMemo, useState } from "react";
import {
  entrainementApi,
  INTENSITY_LABELS,
  type Exercice,
  type Programme,
  type Seance,
} from "@/lib/entrainement";

type Props = {
  sessions: Seance[];
  program: Programme | null;
};

export function CalendrierTab({ sessions, program }: Props) {
  const [openId, setOpenId] = useState<number | null>(null);
  const [details, setDetails] = useState<Seance | null>(null);
  const [loading, setLoading] = useState(false);
  const [err, setErr] = useState<string | null>(null);

  const days = useMemo(() => {
    const map = new Map<string, Seance[]>();
    for (const s of sessions) {
      const k = s.date.slice(0, 10);
      if (!map.has(k)) map.set(k, []);
      map.get(k)!.push(s);
    }
    return [...map.entries()].sort((a, b) => (a[0] < b[0] ? 1 : -1));
  }, [sessions]);

  const openSession = async (id: number) => {
    setOpenId(id);
    setLoading(true);
    setErr(null);
    try {
      const d = await entrainementApi.getSession(id);
      setDetails(d);
    } catch (e: any) {
      setErr(e?.message ?? "Erreur");
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="space-y-4">
      <p className="text-sm text-[var(--muted-foreground)]">
        Séances des 30 derniers jours ({sessions.length} total).
      </p>

      {days.length === 0 && (
        <div className="rounded border border-dashed border-[var(--border)] p-6 text-center text-sm text-[var(--muted-foreground)]">
          Aucune séance loggée pour le moment.
        </div>
      )}

      <div className="space-y-2">
        {days.map(([dateKey, list]) => (
          <div key={dateKey} className="rounded border border-[var(--border)]">
            <div className="bg-[var(--muted)]/50 px-3 py-1.5 text-xs font-medium flex items-center gap-3">
              <span>{new Date(dateKey + "T12:00:00").toLocaleDateString("fr-CA", { weekday: "long", day: "numeric", month: "short" })}</span>
              <span className="ml-auto opacity-60">{list.length} séance(s)</span>
            </div>
            <table className="w-full text-sm">
              <tbody>
                {list.map((s) => (
                  <tr
                    key={s.id}
                    className="border-t border-[var(--border)] cursor-pointer hover:bg-[var(--accent)]/50"
                    onClick={() => openSession(s.id)}
                  >
                    <td className="px-3 py-1.5">{s.type ?? "—"}</td>
                    <td className="px-3 py-1.5 text-right opacity-70">{s.duree_min ?? "—"} min</td>
                    <td className="px-3 py-1.5 text-right opacity-70">{s.sets.length} séries</td>
                    <td className="px-3 py-1.5 text-right text-xs">
                      {s.intensite ? INTENSITY_LABELS[s.intensite] : "—"}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        ))}
      </div>

      {openId !== null && (
        <div
          className="fixed inset-0 z-40 bg-black/40"
          onClick={() => { setOpenId(null); setDetails(null); }}
        >
          <div
            className="absolute right-0 top-0 h-full w-full max-w-md bg-[var(--background)] border-l border-[var(--border)] p-4 overflow-auto"
            onClick={(e) => e.stopPropagation()}
          >
            <div className="flex items-center justify-between mb-3">
              <h3 className="font-semibold">Détail séance</h3>
              <button
                onClick={() => { setOpenId(null); setDetails(null); }}
                className="text-sm rounded border border-[var(--border)] px-2 py-1"
              >Fermer</button>
            </div>
            {loading && <div className="text-sm">Chargement…</div>}
            {err && <div className="text-sm text-[var(--destructive)]">⚠ {err}</div>}
            {details && (
              <div className="space-y-3 text-sm">
                <div>
                  <div className="text-xs opacity-60">
                    {new Date(details.date).toLocaleString("fr-CA")}
                  </div>
                  <div className="font-medium">
                    {details.type ?? "—"} · {details.duree_min ?? "—"} min
                  </div>
                </div>
                <div className="rounded border border-[var(--border)] overflow-hidden">
                  <table className="w-full text-xs">
                    <thead className="bg-[var(--muted)]/50 text-[var(--muted-foreground)]">
                      <tr>
                        <th className="text-left px-2 py-1">Exo</th>
                        <th className="text-right px-2 py-1">Reps</th>
                        <th className="text-right px-2 py-1">Poids</th>
                        <th className="text-right px-2 py-1">RPE</th>
                      </tr>
                    </thead>
                    <tbody>
                      {details.sets.map((st) => (
                        <tr key={st.id} className="border-t border-[var(--border)]">
                          <td className="px-2 py-1">#{st.exercice_id}</td>
                          <td className="px-2 py-1 text-right">{st.reps}</td>
                          <td className="px-2 py-1 text-right">{st.poids_kg} kg</td>
                          <td className="px-2 py-1 text-right">{st.rpe ?? "—"}</td>
                        </tr>
                      ))}
                      {details.sets.length === 0 && (
                        <tr>
                          <td colSpan={4} className="px-2 py-2 text-center opacity-60">
                            Aucune série loggée.
                          </td>
                        </tr>
                      )}
                    </tbody>
                  </table>
                </div>
                {details.note && (
                  <div className="text-xs text-[var(--muted-foreground)]">
                    Note : {details.note}
                  </div>
                )}
              </div>
            )}
          </div>
        </div>
      )}
    </div>
  );
}
