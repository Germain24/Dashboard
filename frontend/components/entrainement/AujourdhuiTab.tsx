"use client";

import { useCallback, useEffect, useState } from "react";
import {
  entrainementApi,
  type Seance,
  type SlotToday,
  type TodayResponse,
} from "@/lib/entrainement";
import { Button } from "@/components/ui/button";
import { Spinner } from "@/components/ui/spinner";
import { EmptyState } from "@/components/ui/empty-state";

type Props = {
  onSessionsChanged?: () => Promise<void>;
};

export function AujourdhuiTab({ onSessionsChanged }: Props) {
  const [today, setToday] = useState<TodayResponse | null>(null);
  const [loading, setLoading] = useState(true);
  const [err, setErr] = useState<string | null>(null);

  const reload = useCallback(async () => {
    setErr(null);
    try {
      const t = await entrainementApi.getToday();
      setToday(t);
    } catch (e: any) {
      setErr(e?.message ?? "Erreur de chargement");
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => { reload(); }, [reload]);

  const handleStart = async () => {
    if (!today) return;
    setErr(null);
    try {
      await entrainementApi.createSession({
        date: new Date().toISOString(),
        type: today.jour_label.toLowerCase(),
        programme_jour_id: today.programme_jour_id,
      });
      await reload();
      await onSessionsChanged?.();
    } catch (e: any) {
      setErr(e?.message ?? "Erreur création séance");
    }
  };

  const handleFinish = async (duree_min: number) => {
    if (!today?.seance_en_cours) return;
    try {
      await entrainementApi.patchSession(today.seance_en_cours.id, { duree_min });
      await reload();
      await onSessionsChanged?.();
    } catch (e: any) {
      setErr(e?.message ?? "Erreur");
    }
  };

  if (loading) return <Spinner label="Chargement…" />;
  if (err) return <p className="text-sm text-[var(--destructive)]">⚠ {err}</p>;
  if (!today) return null;

  const isRest = today.jour_label.toLowerCase() === "repos";
  const seance = today.seance_en_cours;
  const dureeStarted = seance ? new Date(seance.date) : null;

  return (
    <div className="space-y-4 animate-fade-in-up">
      <div className="rounded-xl border border-[var(--border)] bg-[var(--card)] p-3 flex flex-wrap items-center gap-3 text-sm card-hover">
        <span className="font-medium">
          {new Date(today.date + "T12:00:00").toLocaleDateString("fr-CA", {
            weekday: "long", day: "numeric", month: "long",
          })}
        </span>
        <span className="rounded-[var(--radius-sm)] bg-[var(--muted)] px-2 py-0.5 text-xs font-medium">
          {today.jour_label}
        </span>
        <span className="text-xs text-[var(--muted-foreground)]">
          Poids : {today.poids_corps_kg.toFixed(1)} kg
        </span>
        {today.kcal_estimees > 0 && (
          <span className="ml-auto rounded-md bg-[color-mix(in_srgb,var(--success,#16a34a)_12%,transparent)] text-[var(--success,#16a34a)] px-2 py-0.5 text-xs">
            🔥 {today.kcal_estimees.toFixed(0)} kcal
          </span>
        )}
      </div>

      {isRest && (
        <EmptyState
          title="Jour de repos"
          description="Profite-en pour récupérer. 😴"
        />
      )}

      {!isRest && !seance && (
        <div className="rounded-[var(--radius)] border border-[var(--border)] p-4 flex flex-wrap items-center gap-3">
          <span className="text-sm">Prêt pour la séance {today.jour_label} ?</span>
          <Button onClick={handleStart} className="ml-auto" size="sm">
            ▶️ Commencer la séance
          </Button>
        </div>
      )}

      {!isRest && (
        <div className="space-y-2 stagger">
          {today.slots.map((slot, i) => (
            <SlotCard key={i} slot={slot} seance={seance} onSetAdded={reload} />
          ))}
          {today.slots.length === 0 && (
            <EmptyState
              title="Aucun slot configuré"
              description="Lance POST /entrainement/program/seed-garmin ou édite le jour dans l'onglet Programme."
            />
          )}
        </div>
      )}

      {seance && (
        <FinishBar startedAt={dureeStarted!} onFinish={handleFinish} />
      )}
    </div>
  );
}

/* ── Slot card ────────────────────────────────────────────── */
function SlotCard({
  slot, seance, onSetAdded,
}: {
  slot: SlotToday;
  seance: Seance | null;
  onSetAdded: () => Promise<void>;
}) {
  const setsForSlot = seance?.sets.filter((s) => s.exercice_id === slot.exercice_id) ?? [];
  const setsDone = setsForSlot.length;
  const setsTarget = slot.sets_target ?? null;
  const progress = setsTarget && setsTarget > 0
    ? Math.min(100, Math.round((setsDone / setsTarget) * 100))
    : 0;
  const noExercice = slot.exercice_id === null;
  const isWarmup = /warm-?up/i.test(slot.label);

  return (
    <div className="rounded-xl border border-[var(--border)] bg-[var(--card)] p-3 card-hover">
      <div className="flex flex-wrap items-baseline gap-2 text-sm">
        <span className="font-medium">{slot.label}</span>
        {setsTarget && (
          <span className="text-xs text-[var(--muted-foreground)]">
            cible {setsTarget}×{slot.reps_target ?? "?"}
          </span>
        )}
        {slot.poids_suggere_kg !== null && slot.poids_suggere_kg > 0 && (
          <span className="text-xs text-[var(--muted-foreground)]">
            · sugg. <strong>{slot.poids_suggere_kg} kg</strong>
          </span>
        )}
        {slot.poids_suggere_kg === 0 && (
          <span className="text-xs text-[var(--muted-foreground)]">· poids du corps</span>
        )}
        {slot.note && <span className="text-xs italic opacity-60">{slot.note}</span>}
        {setsTarget && (
          <span className="ml-auto text-xs font-medium" style={{ color: "var(--ring)" }}>
            {setsDone}/{setsTarget}
          </span>
        )}
      </div>

      {setsTarget && (
        <div className="mt-1 h-1 rounded-full bg-[var(--muted)] overflow-hidden">
          <div
            className="h-full bg-[var(--ring)] transition-all"
            style={{ width: `${progress}%` }}
          />
        </div>
      )}

      {setsForSlot.length > 0 && (
        <ul className="mt-2 text-xs space-y-0.5 text-[var(--muted-foreground)]">
          {setsForSlot.map((s, i) => (
            <li key={s.id}>
              Série {i + 1} : <strong className="text-[var(--foreground)]">{s.reps}</strong> reps
              × <strong className="text-[var(--foreground)]">{s.poids_kg}</strong> kg
              {s.rpe ? ` · RPE ${s.rpe}` : ""}
            </li>
          ))}
        </ul>
      )}

      {seance && !noExercice && !isWarmup && (
        <AddSetForm
          seanceId={seance.id}
          exerciceId={slot.exercice_id!}
          suggested={slot.poids_suggere_kg ?? 0}
          repsHint={typeof slot.reps_target === "number" ? slot.reps_target : 8}
          onAdded={onSetAdded}
        />
      )}

      {seance && noExercice && !isWarmup && (
        <p className="mt-2 text-xs text-[var(--warning)]">
          ⚠ Exercice « {slot.label} » introuvable dans le catalogue.
        </p>
      )}
    </div>
  );
}

/* ── Add set form ─────────────────────────────────────────── */
function AddSetForm({
  seanceId, exerciceId, suggested, repsHint, onAdded,
}: {
  seanceId: number;
  exerciceId: number;
  suggested: number;
  repsHint: number;
  onAdded: () => Promise<void>;
}) {
  const [reps, setReps] = useState<string>(String(repsHint));
  const [poids, setPoids] = useState<string>(suggested > 0 ? String(suggested) : "");
  const [rpe, setRpe] = useState<string>("");
  const [busy, setBusy] = useState(false);

  const submit = async () => {
    if (!reps) return;
    setBusy(true);
    try {
      await entrainementApi.addSet(seanceId, {
        exercice_id: exerciceId,
        reps: parseInt(reps, 10),
        poids_kg: poids ? parseFloat(poids) : 0,
        rpe: rpe ? parseFloat(rpe) : null,
      });
      await onAdded();
    } finally {
      setBusy(false);
    }
  };

  const inputCls = "mt-0.5 rounded-[var(--radius-sm)] border border-[var(--border)] bg-transparent px-1.5 py-0.5 text-xs focus:border-[var(--ring)] focus:outline-none";

  return (
    <div className="mt-2 flex flex-wrap items-end gap-2 text-xs">
      <label className="flex flex-col">
        Reps
        <input type="number" value={reps} onChange={(e) => setReps(e.target.value)} className={`${inputCls} w-16`} />
      </label>
      <label className="flex flex-col">
        Poids (kg)
        <input type="number" step="0.5" value={poids} onChange={(e) => setPoids(e.target.value)} className={`${inputCls} w-20`} />
      </label>
      <label className="flex flex-col">
        RPE
        <input type="number" step="0.5" min="6" max="10" value={rpe} onChange={(e) => setRpe(e.target.value)} className={`${inputCls} w-14`} />
      </label>
      <Button size="sm" onClick={submit} disabled={busy}>
        + Série
      </Button>
    </div>
  );
}

/* ── Finish bar ───────────────────────────────────────────── */
function FinishBar({ startedAt, onFinish }: {
  startedAt: Date;
  onFinish: (duree_min: number) => Promise<void>;
}) {
  const [now, setNow] = useState(Date.now());
  useEffect(() => {
    const id = setInterval(() => setNow(Date.now()), 30_000);
    return () => clearInterval(id);
  }, []);
  const dureeMin = Math.max(1, Math.round((now - startedAt.getTime()) / 60_000));

  return (
    <div className="sticky bottom-2 rounded-[var(--radius)] border border-[var(--border)] bg-[var(--background)] p-3 flex items-center gap-3 text-sm shadow-md">
      <span>⏱️ {dureeMin} min écoulées</span>
      <Button onClick={() => onFinish(dureeMin)} className="ml-auto" size="sm">
        ✓ Terminer la séance
      </Button>
    </div>
  );
}
