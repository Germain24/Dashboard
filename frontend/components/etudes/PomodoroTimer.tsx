"use client";

/** Timer Pomodoro : crée automatiquement une session à la fin d'un cycle (#93). */

import { useEffect, useRef, useState } from "react";
import { createSession, type Cours } from "@/lib/etudes";

const DURATIONS = [25, 50];

export function PomodoroTimer({ cours, onLogged }: { cours: Cours[]; onLogged: () => void }) {
  const [workMin, setWorkMin] = useState(25);
  const [remaining, setRemaining] = useState(25 * 60); // secondes
  const [running, setRunning] = useState(false);
  const [coursId, setCoursId] = useState("");
  const [sujet, setSujet] = useState("");
  const [status, setStatus] = useState<string | null>(null);
  const tickRef = useRef<ReturnType<typeof setInterval> | null>(null);

  async function finishCycle() {
    setRunning(false);
    try {
      await createSession({
        cours_id: coursId ? Number(coursId) : undefined,
        duree_min: workMin,
        sujet: sujet || "Pomodoro",
      });
      setStatus(`✓ Session de ${workMin} min enregistrée.`);
      onLogged();
    } catch {
      setStatus("Erreur lors de l'enregistrement.");
    } finally {
      setRemaining(workMin * 60);
    }
  }

  // Réinitialise le compteur quand la durée change (hors session en cours).
  useEffect(() => {
    // eslint-disable-next-line react-hooks/set-state-in-effect
    if (!running) setRemaining(workMin * 60);
  }, [workMin, running]);

  useEffect(() => {
    if (!running) return;
    tickRef.current = setInterval(() => {
      setRemaining((r) => {
        if (r <= 1) {
          // Cycle terminé → log auto.
          if (tickRef.current) window.clearInterval(tickRef.current);
          void finishCycle();
          return 0;
        }
        return r - 1;
      });
    }, 1000);
    return () => { if (tickRef.current) clearInterval(tickRef.current); };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [running]);

  const mm = String(Math.floor(remaining / 60)).padStart(2, "0");
  const ss = String(remaining % 60).padStart(2, "0");
  const pct = 100 - (remaining / (workMin * 60)) * 100;

  return (
    <div className="rounded-lg border border-[var(--border)] bg-[var(--card)] p-4 space-y-3">
      <div className="flex items-center justify-between">
        <h3 className="text-sm font-semibold">🍅 Pomodoro</h3>
        <div className="flex gap-1">
          {DURATIONS.map((d) => (
            <button
              key={d}
              onClick={() => setWorkMin(d)}
              disabled={running}
              className={`px-2 py-0.5 rounded text-xs ${workMin === d ? "bg-[var(--primary)] text-[var(--primary-foreground)]" : "border border-[var(--border)]"} disabled:opacity-50`}
            >
              {d}min
            </button>
          ))}
        </div>
      </div>

      <div className="text-center">
        <div className="text-4xl font-bold tabular-nums">{mm}:{ss}</div>
        <div className="mt-2 h-1.5 rounded-full bg-[var(--border)] overflow-hidden">
          <div className="h-full bg-[var(--ring)] transition-all" style={{ width: `${pct}%` }} />
        </div>
      </div>

      <div className="flex gap-2">
        <select value={coursId} onChange={(e) => setCoursId(e.target.value)} disabled={running}
          className="flex-1 border rounded px-2 py-1 text-sm bg-[var(--card)] disabled:opacity-50">
          <option value="">— cours libre —</option>
          {cours.map((c) => <option key={c.id} value={c.id}>{c.code}</option>)}
        </select>
        <input value={sujet} onChange={(e) => setSujet(e.target.value)} disabled={running} placeholder="Sujet"
          className="flex-1 border rounded px-2 py-1 text-sm bg-transparent disabled:opacity-50" />
      </div>

      <div className="flex gap-2">
        {!running ? (
          <button onClick={() => { setStatus(null); setRunning(true); }}
            className="flex-1 px-3 py-1.5 bg-[var(--primary)] text-[var(--primary-foreground)] rounded text-sm hover:opacity-90">
            ▶ Démarrer
          </button>
        ) : (
          <button onClick={() => setRunning(false)}
            className="flex-1 px-3 py-1.5 border border-[var(--border)] rounded text-sm">
            ⏸ Pause
          </button>
        )}
        <button onClick={() => { setRunning(false); setRemaining(workMin * 60); setStatus(null); }}
          className="px-3 py-1.5 border border-[var(--border)] rounded text-sm">
          ↺
        </button>
      </div>

      {status && <div className="text-xs text-[var(--muted-foreground)]">{status}</div>}
    </div>
  );
}
