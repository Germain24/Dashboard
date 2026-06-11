"use client";

import { useState } from "react";
import { formatPaceFromSeconds, type CourseCardio } from "@/lib/entrainement";
import { useCardioList, useCreateCardio, useDeleteCardio } from "@/lib/queries/entrainement";

function todayKey(): string {
  const d = new Date();
  return `${d.getFullYear()}-${String(d.getMonth() + 1).padStart(2, "0")}-${String(d.getDate()).padStart(2, "0")}`;
}

export function CardioTab() {
  const [err, setErr] = useState<string | null>(null);

  const [date, setDate] = useState<string>(todayKey());
  const [distance, setDistance] = useState<string>("");
  const [minutes, setMinutes] = useState<string>("");
  const [seconds, setSeconds] = useState<string>("");
  const [note, setNote] = useState<string>("");

  const cardioQ = useCardioList();
  const items: CourseCardio[] = cardioQ.data ?? [];
  const loading = cardioQ.isLoading;
  const createMutation = useCreateCardio();
  const deleteMutation = useDeleteCardio();
  const saving = createMutation.isPending;

  const handleSave = () => {
    setErr(null);
    const km = parseFloat(distance);
    const sec = parseInt(minutes || "0", 10) * 60 + parseInt(seconds || "0", 10);
    if (!km || km <= 0 || sec <= 0) {
      setErr("Distance et durée requises.");
      return;
    }
    createMutation.mutate(
      { date, distance_km: km, duree_sec: sec, note: note || null },
      {
        onSuccess: () => {
          setDistance("");
          setMinutes("");
          setSeconds("");
          setNote("");
        },
        onError: (e) => setErr(e instanceof Error ? e.message : "Erreur"),
      },
    );
  };

  const handleDelete = (id: number) => {
    deleteMutation.mutate(id, {
      onError: (e) => setErr(e instanceof Error ? e.message : "Erreur"),
    });
  };

  const totalKm = items.reduce((s, i) => s + i.distance_km, 0);
  const totalSec = items.reduce((s, i) => s + i.duree_sec, 0);
  const avgPace = totalKm > 0 ? totalSec / totalKm : 0;

  return (
    <div className="space-y-4">
      <div className="rounded border border-[var(--border)] p-3">
        <p className="font-medium text-sm mb-2">Nouvelle course</p>
        <div className="flex flex-wrap items-end gap-2 text-xs">
          <label className="flex flex-col">
            Date
            <input
              type="date"
              value={date}
              onChange={(e) => setDate(e.target.value)}
              className="mt-1 rounded border border-[var(--border)] bg-transparent px-2 py-1"
            />
          </label>
          <label className="flex flex-col">
            Distance (km)
            <input
              type="number"
              step="0.01"
              value={distance}
              onChange={(e) => setDistance(e.target.value)}
              className="mt-1 w-24 rounded border border-[var(--border)] bg-transparent px-2 py-1"
            />
          </label>
          <label className="flex flex-col">
            Min
            <input
              type="number"
              value={minutes}
              onChange={(e) => setMinutes(e.target.value)}
              className="mt-1 w-20 rounded border border-[var(--border)] bg-transparent px-2 py-1"
            />
          </label>
          <label className="flex flex-col">
            Sec
            <input
              type="number"
              value={seconds}
              onChange={(e) => setSeconds(e.target.value)}
              className="mt-1 w-20 rounded border border-[var(--border)] bg-transparent px-2 py-1"
            />
          </label>
          <label className="flex flex-col flex-1 min-w-[180px]">
            Note
            <input
              type="text"
              value={note}
              onChange={(e) => setNote(e.target.value)}
              className="mt-1 rounded border border-[var(--border)] bg-transparent px-2 py-1"
            />
          </label>
          <button
            onClick={handleSave}
            disabled={saving}
            className="rounded bg-[var(--primary)] text-[var(--primary-foreground)] px-3 py-1.5 font-medium disabled:opacity-50"
          >
            {saving ? "…" : "+ Enregistrer"}
          </button>
        </div>
        {err && <div className="mt-2 text-sm text-[var(--destructive)]">⚠ {err}</div>}
      </div>

      <div className="grid grid-cols-3 gap-3 text-sm">
        <Stat label="Total km" value={totalKm.toFixed(2)} />
        <Stat label="Courses" value={String(items.length)} />
        <Stat label="Allure moy." value={avgPace > 0 ? `${formatPaceFromSeconds(avgPace)}/km` : "—"} />
      </div>

      {loading ? (
        <div className="text-sm text-[var(--muted-foreground)]">Chargement…</div>
      ) : (
        <div className="rounded border border-[var(--border)] overflow-hidden">
          <table className="w-full text-sm">
            <thead className="bg-[var(--muted)]/50 text-xs uppercase text-[var(--muted-foreground)]">
              <tr>
                <th className="text-left px-3 py-2">Date</th>
                <th className="text-right px-3 py-2">Distance</th>
                <th className="text-right px-3 py-2">Durée</th>
                <th className="text-right px-3 py-2">Allure</th>
                <th className="text-left px-3 py-2">Note</th>
                <th className="text-right px-3 py-2">Source</th>
                <th className="text-right px-3 py-2"></th>
              </tr>
            </thead>
            <tbody>
              {items.map((c) => (
                <tr key={c.id} className="border-t border-[var(--border)]">
                  <td className="px-3 py-1.5">{c.date}</td>
                  <td className="px-3 py-1.5 text-right">{c.distance_km.toFixed(2)} km</td>
                  <td className="px-3 py-1.5 text-right">
                    {Math.floor(c.duree_sec / 60)}:{String(c.duree_sec % 60).padStart(2, "0")}
                  </td>
                  <td className="px-3 py-1.5 text-right">{c.pace_str ?? "—"}</td>
                  <td className="px-3 py-1.5">{c.note ?? ""}</td>
                  <td className="px-3 py-1.5 text-right text-xs opacity-60">{c.source}</td>
                  <td className="px-3 py-1.5 text-right">
                    <button
                      onClick={() => handleDelete(c.id)}
                      className="text-xs text-[var(--destructive)] hover:underline"
                    >Suppr.</button>
                  </td>
                </tr>
              ))}
              {items.length === 0 && (
                <tr>
                  <td colSpan={7} className="px-3 py-4 text-center text-[var(--muted-foreground)]">
                    Aucune course enregistrée.
                  </td>
                </tr>
              )}
            </tbody>
          </table>
        </div>
      )}
    </div>
  );
}

function Stat({ label, value }: { label: string; value: string }) {
  return (
    <div className="rounded border border-[var(--border)] p-3">
      <div className="text-xs text-[var(--muted-foreground)]">{label}</div>
      <div className="text-lg font-semibold">{value}</div>
    </div>
  );
}
