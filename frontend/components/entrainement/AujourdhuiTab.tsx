"use client";

import { useCallback, useEffect, useState } from "react";
import {
  entrainementApi,
  type Mesocycle,
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
  // Minuteur de repos entre séries (#106)
  const [restDuration, setRestDuration] = useState(90);
  const [restEndsAt, setRestEndsAt] = useState<number | null>(null);
  const startRest = useCallback((sec: number) => {
    setRestDuration(sec);
    setRestEndsAt(Date.now() + sec * 1000);
  }, []);

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

  const startMeso = () => {
    entrainementApi.startMesocycle(4).then(() => reload()).catch(() => setErr("Erreur mésocycle"));
  };
  const stopMeso = () => {
    entrainementApi.stopMesocycle().then(() => reload()).catch(() => setErr("Erreur mésocycle"));
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

      <MesocycleBanner meso={today.mesocycle} onStart={startMeso} onStop={stopMeso} />

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
            <SlotCard
              key={i}
              slot={slot}
              seance={seance}
              onSetAdded={reload}
              onRest={() => startRest(restDuration)}
            />
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
        <RestTimer
          endsAt={restEndsAt}
          duration={restDuration}
          onPreset={startRest}
          onSkip={() => setRestEndsAt(null)}
        />
      )}

      {seance && (
        <FinishBar startedAt={dureeStarted!} onFinish={handleFinish} />
      )}
    </div>
  );
}

/* ── Mésocycle banner (#110) ──────────────────────────────── */
function MesocycleBanner({ meso, onStart, onStop }: {
  meso: Mesocycle | null;
  onStart: () => void;
  onStop: () => void;
}) {
  if (!meso || !meso.active) {
    return (
      <div className="flex items-center justify-between gap-2 rounded-[var(--radius)] border border-dashed border-[var(--border)] p-2.5 text-xs">
        <span className="text-[var(--muted-foreground)]">Pas de mésocycle actif — volume progressif puis deload.</span>
        <button type="button" onClick={onStart}
          className="rounded border border-[var(--border)] px-2 py-1 font-medium hover:bg-[var(--accent)]">
          Démarrer un mésocycle
        </button>
      </div>
    );
  }
  const isDeload = meso.phase === "deload";
  const wk = meso.semaine_cycle ?? 1;
  const len = meso.cycle_len ?? 5;
  const acc = meso.accumulation_weeks ?? 4;
  return (
    <div className="space-y-2 rounded-[var(--radius)] border border-[var(--border)] bg-[var(--card)] p-3">
      <div className="flex items-center justify-between gap-2 text-sm">
        <span className="font-medium">
          Mésocycle ·{" "}
          {isDeload ? (
            <span className="text-[var(--warning)]">Deload</span>
          ) : (
            <>Accumulation <span className="tabular-nums">S{wk}/{acc}</span></>
          )}
        </span>
        <button type="button" onClick={onStop}
          className="rounded border border-[var(--border)] px-2 py-0.5 text-xs text-[var(--muted-foreground)] hover:bg-[var(--muted)]">
          Arrêter
        </button>
      </div>
      <div className="h-1.5 overflow-hidden rounded-full bg-[var(--muted)]">
        <div className="h-full rounded-full transition-all"
          style={{ width: `${(wk / len) * 100}%`, backgroundColor: isDeload ? "var(--warning)" : "var(--ring)" }} />
      </div>
      <p className="text-xs text-[var(--muted-foreground)]">
        {isDeload
          ? "Semaine de récupération : volume réduit, charge allégée."
          : "Le volume (séries) monte cette semaine ; la charge suit le poids suggéré."}
      </p>
    </div>
  );
}

/* ── Slot card ────────────────────────────────────────────── */
function SlotCard({
  slot, seance, onSetAdded, onRest,
}: {
  slot: SlotToday;
  seance: Seance | null;
  onSetAdded: () => Promise<void>;
  onRest: () => void;
}) {
  const setsForSlot = seance?.sets.filter((s) => s.exercice_id === slot.exercice_id) ?? [];
  const setsDone = setsForSlot.length;
  // Cible de la semaine si un mésocycle tourne (#110), sinon la cible de base.
  const setsTarget = slot.sets_target_semaine ?? slot.sets_target ?? null;
  const periodised = slot.sets_target_semaine != null && slot.sets_target_semaine !== slot.sets_target;
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
            {periodised && <span className="text-[var(--ring)]"> · sem.</span>}
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

      {slot.derniere_fois && (
        <p className="mt-1 text-xs text-[var(--muted-foreground)]">
          ↩︎ Dernière fois (
          {new Date(slot.derniere_fois.date + "T12:00:00").toLocaleDateString("fr-CA", {
            day: "numeric", month: "short",
          })}
          ) : <span className="text-[var(--foreground)]">{slot.derniere_fois.resume}</span>
        </p>
      )}

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
          onRest={onRest}
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
  seanceId, exerciceId, suggested, repsHint, onAdded, onRest,
}: {
  seanceId: number;
  exerciceId: number;
  suggested: number;
  repsHint: number;
  onAdded: () => Promise<void>;
  onRest: () => void;
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
      onRest(); // démarre le minuteur de repos (#106)
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

/* ── Rest timer (#106) ────────────────────────────────────── */
const REST_PRESETS = [60, 90, 120, 180];

function RestTimer({
  endsAt, duration, onPreset, onSkip,
}: {
  endsAt: number | null;
  duration: number;
  onPreset: (sec: number) => void;
  onSkip: () => void;
}) {
  const [now, setNow] = useState(() => Date.now());
  useEffect(() => {
    if (endsAt === null) return;
    const id = setInterval(() => setNow(Date.now()), 250);
    return () => clearInterval(id);
  }, [endsAt]);

  const remainingMs = endsAt !== null ? endsAt - now : 0;
  const remaining = Math.max(0, Math.ceil(remainingMs / 1000));
  const active = endsAt !== null && remainingMs > 0;
  const done = endsAt !== null && remainingMs <= 0;
  const pct = active ? Math.min(100, (remaining / duration) * 100) : done ? 100 : 0;
  const mmss = `${Math.floor(remaining / 60)}:${String(remaining % 60).padStart(2, "0")}`;

  return (
    <div className="rounded-[var(--radius)] border border-[var(--border)] bg-[var(--card)] p-3 space-y-2">
      <div className="flex items-center gap-3 text-sm">
        <span className="font-medium">⏳ Repos</span>
        {active && <span className="tabular-nums text-lg font-semibold">{mmss}</span>}
        {done && <span className="text-[var(--success)] font-medium">Repos terminé — c'est reparti 💪</span>}
        {endsAt === null && (
          <span className="text-xs text-[var(--muted-foreground)]">
            Démarre auto après chaque série (défaut {duration}s)
          </span>
        )}
        {endsAt !== null && (
          <button
            type="button"
            onClick={onSkip}
            className="ml-auto rounded border border-[var(--border)] px-2 py-0.5 text-xs hover:bg-[var(--muted)]"
          >
            {active ? "Passer" : "OK"}
          </button>
        )}
      </div>

      {active && (
        <div className="h-1.5 overflow-hidden rounded-full bg-[var(--muted)]">
          <div className="h-full bg-[var(--ring)] transition-all" style={{ width: `${pct}%` }} />
        </div>
      )}

      <div className="flex flex-wrap gap-1.5">
        {REST_PRESETS.map((sec) => (
          <button
            key={sec}
            type="button"
            onClick={() => onPreset(sec)}
            className={`rounded border px-2 py-0.5 text-xs transition-colors ${
              duration === sec
                ? "border-[var(--ring)] text-[var(--ring)]"
                : "border-[var(--border)] text-[var(--muted-foreground)] hover:bg-[var(--muted)]"
            }`}
          >
            {sec}s
          </button>
        ))}
      </div>
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
