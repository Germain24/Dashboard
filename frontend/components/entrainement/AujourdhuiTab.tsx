"use client";

import { useMemo, useState } from "react";
import {
  entrainementApi,
  INTENSITY_LABELS,
  type Exercice,
  type IntensityResponse,
  type Programme,
  type Seance,
} from "@/lib/entrainement";

type Props = {
  program: Programme | null;
  exercices: Exercice[];
  sessions: Seance[];
  intensity: IntensityResponse | null;
  onSessionsChanged: () => Promise<void>;
};

function weekdayMondayZero(d: Date): number {
  return d.getDay() === 0 ? 6 : d.getDay() - 1;
}

export function AujourdhuiTab({
  program, exercices, sessions, intensity, onSessionsChanged,
}: Props) {
  const today = useMemo(() => new Date(), []);
  const todayKey = today.toISOString().slice(0, 10);
  const wd = weekdayMondayZero(today);
  const jour = program?.jours.find((j) => j.weekday === wd) ?? null;

  const todaySessions = sessions.filter(
    (s) => s.date.slice(0, 10) === todayKey,
  );

  const [type, setType] = useState<string>(
    (jour?.label && jour.label.toLowerCase()) || "push",
  );
  const [duree, setDuree] = useState<string>("");
  const [note, setNote] = useState<string>("");
  const [creating, setCreating] = useState(false);
  const [err, setErr] = useState<string | null>(null);

  const handleCreateSession = async () => {
    setCreating(true);
    setErr(null);
    try {
      await entrainementApi.createSession({
        date: new Date().toISOString(),
        type,
        duree_min: duree ? parseInt(duree, 10) : null,
        note: note || null,
        programme_jour_id: jour?.id ?? null,
      });
      setDuree("");
      setNote("");
      await onSessionsChanged();
    } catch (e: any) {
      setErr(e?.message ?? "Erreur création");
    } finally {
      setCreating(false);
    }
  };

  return (
    <div className="space-y-4">
      <div className="rounded border border-[var(--border)] p-3 flex flex-wrap items-center gap-3 text-sm">
        <span className="font-medium">
          {today.toLocaleDateString("fr-CA")} · {jour?.label ?? "?"}
        </span>
        {intensity && (
          <span className="text-[var(--muted-foreground)]">
            Intensité du jour :{" "}
            <strong>{INTENSITY_LABELS[intensity.intensity] ?? intensity.intensity}</strong>
            <span className="ml-1 text-xs opacity-70">
              (consommé par Nutrition)
            </span>
          </span>
        )}
        <span className="ml-auto text-xs text-[var(--muted-foreground)]">
          {todaySessions.length} séance(s) loggée(s)
        </span>
      </div>

      {(jour?.slots?.length ?? 0) > 0 && (
        <div className="rounded border border-[var(--border)] p-3 text-sm">
          <p className="font-medium mb-2">Programme du jour</p>
          <ul className="text-xs space-y-1">
            {jour!.slots.map((slot, i) => (
              <li key={i}>
                {(slot as any).label ?? `Exercice ${(slot as any).exercice_id}`}
                {(slot as any).sets_target && (
                  <span className="opacity-70"> · {(slot as any).sets_target}×{(slot as any).reps_target}</span>
                )}
              </li>
            ))}
          </ul>
        </div>
      )}

      {/* Nouvelle séance */}
      {jour?.label !== "Repos" && (
        <div className="rounded border border-[var(--border)] p-3">
          <p className="font-medium mb-2 text-sm">Nouvelle séance</p>
          <div className="flex flex-wrap items-end gap-2 text-xs">
            <label className="flex flex-col">
              Type
              <select
                value={type}
                onChange={(e) => setType(e.target.value)}
                className="mt-1 rounded border border-[var(--border)] bg-transparent px-2 py-1"
              >
                {["push", "pull", "legs", "upper", "lower", "cardio", "custom"].map((t) => (
                  <option key={t} value={t}>{t}</option>
                ))}
              </select>
            </label>
            <label className="flex flex-col">
              Durée (min)
              <input
                type="number"
                value={duree}
                onChange={(e) => setDuree(e.target.value)}
                className="mt-1 w-24 rounded border border-[var(--border)] bg-transparent px-2 py-1"
              />
            </label>
            <label className="flex flex-col flex-1 min-w-[200px]">
              Note
              <input
                type="text"
                value={note}
                onChange={(e) => setNote(e.target.value)}
                className="mt-1 rounded border border-[var(--border)] bg-transparent px-2 py-1"
              />
            </label>
            <button
              onClick={handleCreateSession}
              disabled={creating}
              className="rounded bg-[var(--primary)] text-[var(--primary-foreground)] px-3 py-1.5 font-medium disabled:opacity-50"
            >
              {creating ? "…" : "+ Créer la séance"}
            </button>
          </div>
          {err && <div className="mt-2 text-sm text-red-500">⚠ {err}</div>}
          <p className="mt-2 text-xs text-[var(--muted-foreground)]">
            Une fois créée, ouvre la séance dans l&apos;onglet Calendrier pour
            logger des séries.
          </p>
        </div>
      )}

      {/* Liste séances du jour */}
      {todaySessions.length > 0 && (
        <div className="rounded border border-[var(--border)] overflow-hidden">
          <table className="w-full text-sm">
            <thead className="bg-[var(--muted)]/50 text-xs uppercase text-[var(--muted-foreground)]">
              <tr>
                <th className="text-left px-3 py-2">Type</th>
                <th className="text-right px-3 py-2">Durée</th>
                <th className="text-right px-3 py-2">Séries</th>
                <th className="text-right px-3 py-2">Intensité</th>
              </tr>
            </thead>
            <tbody>
              {todaySessions.map((s) => (
                <tr key={s.id} className="border-t border-[var(--border)]">
                  <td className="px-3 py-1.5">{s.type ?? "—"}</td>
                  <td className="px-3 py-1.5 text-right">{s.duree_min ?? "—"} min</td>
                  <td className="px-3 py-1.5 text-right">{s.sets.length}</td>
                  <td className="px-3 py-1.5 text-right">
                    {s.intensite ? INTENSITY_LABELS[s.intensite] : "—"}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}

      <p className="text-xs text-[var(--muted-foreground)]">
        Catalogue : {exercices.length} exercices chargés.
      </p>
    </div>
  );
}
