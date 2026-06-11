"use client";

/** Widgets de séance : bannière mésocycle (#110), minuteur de repos (#106),
 *  barre de fin de séance. Extraits d'AujourdhuiTab (#522). */

import { useEffect, useState } from "react";
import type { Mesocycle } from "@/lib/entrainement";
import { Button } from "@/components/ui/button";

export function MesocycleBanner({ meso, onStart, onStop }: {
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

const REST_PRESETS = [60, 90, 120, 180];

export function RestTimer({
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

export function FinishBar({ startedAt, onFinish }: {
  startedAt: Date;
  onFinish: (duree_min: number) => void;
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
