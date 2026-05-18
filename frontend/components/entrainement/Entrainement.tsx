"use client";

import { useCallback, useEffect, useState } from "react";
import { Dumbbell } from "lucide-react";
import {
  entrainementApi,
  type Exercice,
  type IntensityResponse,
  type Programme,
  type Seance,
  todayKey,
} from "@/lib/entrainement";
import { AujourdhuiTab } from "./AujourdhuiTab";
import { ProgrammeTab } from "./ProgrammeTab";
import { ProgressionTab } from "./ProgressionTab";
import { CardioTab } from "./CardioTab";
import { CalendrierTab } from "./CalendrierTab";

type Tab = "aujourdhui" | "programme" | "progression" | "cardio" | "calendrier";

export function Entrainement() {
  const [tab, setTab] = useState<Tab>("aujourdhui");
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  const [program, setProgram] = useState<Programme | null>(null);
  const [exercices, setExercices] = useState<Exercice[]>([]);
  const [sessions, setSessions] = useState<Seance[]>([]);
  const [intensity, setIntensity] = useState<IntensityResponse | null>(null);

  const reloadAll = useCallback(async () => {
    const today = todayKey();
    const from = new Date();
    from.setDate(from.getDate() - 30);
    const fromKey = `${from.getFullYear()}-${String(from.getMonth() + 1).padStart(2, "0")}-${String(from.getDate()).padStart(2, "0")}`;

    const [p, ex, ss, i] = await Promise.all([
      entrainementApi.getProgram(),
      entrainementApi.listExercices(),
      entrainementApi.listSessions({ from: fromKey, to: today }),
      entrainementApi.getIntensityToday(),
    ]);
    setProgram(p);
    setExercices(ex);
    setSessions(ss);
    setIntensity(i);
  }, []);

  useEffect(() => {
    let cancelled = false;
    (async () => {
      try {
        await reloadAll();
        if (cancelled) return;
        setLoading(false);
      } catch (e: any) {
        if (cancelled) return;
        setError(e?.message ?? "Erreur de chargement");
        setLoading(false);
      }
    })();
    return () => { cancelled = true; };
  }, [reloadAll]);

  if (loading) {
    return <div className="flex items-center gap-2"><Dumbbell className="h-5 w-5" /> Chargement…</div>;
  }
  if (error) return <div className="text-red-500">⚠ {error}</div>;

  const todayWeekday = new Date().getDay() === 0 ? 6 : new Date().getDay() - 1;
  const todayJour = program?.jours.find((j) => j.weekday === todayWeekday);

  return (
    <div className="space-y-4">
      <header className="flex items-center gap-3">
        <Dumbbell className="h-6 w-6" />
        <h1 className="text-2xl font-semibold tracking-tight">Entraînement</h1>
        {todayJour && (
          <span className="ml-auto text-xs rounded bg-[var(--muted)] px-2 py-1 text-[var(--muted-foreground)]">
            Aujourd&apos;hui : <strong>{todayJour.label}</strong>
            {intensity && (
              <span className="ml-2 opacity-70">· intensité {intensity.intensity}</span>
            )}
          </span>
        )}
      </header>

      <nav className="flex gap-1 border-b border-[var(--border)] flex-wrap">
        {([
          ["aujourdhui", "🏋️ Aujourd'hui"],
          ["programme", "📅 Programme"],
          ["progression", "📈 Progression"],
          ["cardio", "🏃 Cardio"],
          ["calendrier", "🗓️ Calendrier"],
        ] as [Tab, string][]).map(([k, label]) => (
          <button
            key={k}
            onClick={() => setTab(k)}
            className={`px-3 py-2 text-sm -mb-px border-b-2 ${tab === k ? "border-blue-500 text-[var(--foreground)]" : "border-transparent text-[var(--muted-foreground)] hover:text-[var(--foreground)]"}`}
          >
            {label}
          </button>
        ))}
      </nav>

      {tab === "aujourdhui" && (
        <AujourdhuiTab
          program={program}
          exercices={exercices}
          sessions={sessions}
          intensity={intensity}
          onSessionsChanged={reloadAll}
        />
      )}
      {tab === "programme" && program && (
        <ProgrammeTab
          program={program}
          exercices={exercices}
          onProgramChanged={reloadAll}
        />
      )}
      {tab === "progression" && (
        <ProgressionTab exercices={exercices} />
      )}
      {tab === "cardio" && (
        <CardioTab />
      )}
      {tab === "calendrier" && (
        <CalendrierTab sessions={sessions} program={program} />
      )}
    </div>
  );
}
