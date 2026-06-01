"use client";

import { useCallback, useEffect, useState } from "react";
import { Dumbbell, ClipboardList, BarChart2, Activity, CalendarDays } from "lucide-react";
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

const TABS: { id: Tab; label: string; Icon: React.ElementType }[] = [
  { id: "aujourdhui", label: "Aujourd'hui", Icon: Dumbbell },
  { id: "programme", label: "Programme", Icon: ClipboardList },
  { id: "progression", label: "Progression", Icon: BarChart2 },
  { id: "cardio", label: "Cardio", Icon: Activity },
  { id: "calendrier", label: "Calendrier", Icon: CalendarDays },
];

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
    return (
      <div className="p-6 space-y-4 animate-fade-in">
        {[1, 2, 3].map((i) => (
          <div key={i} className="h-20 rounded-xl border border-[var(--border)] bg-[var(--card)] skeleton-shimmer" />
        ))}
      </div>
    );
  }
  if (error) return <div className="p-6 text-[var(--destructive)]">⚠ {error}</div>;

  const todayWeekday = new Date().getDay() === 0 ? 6 : new Date().getDay() - 1;
  const todayJour = program?.jours.find((j) => j.weekday === todayWeekday);

  return (
    <div className="space-y-0 animate-fade-in">
      <div className="px-6 py-5 border-b border-[var(--border)]">
        <div className="mb-4 flex items-start justify-between">
          <div>
            <h1 className="text-xl font-semibold tracking-tight">Entraînement</h1>
            <p className="text-sm text-[var(--muted-foreground)] mt-0.5">Séances &amp; progression</p>
          </div>
          {todayJour && (
            <span className="text-xs rounded-md bg-[var(--muted)] px-2.5 py-1 text-[var(--muted-foreground)]">
              Aujourd&apos;hui : <strong>{todayJour.label}</strong>
              {intensity && (
                <span className="ml-2 opacity-70">· intensité {intensity.intensity}</span>
              )}
            </span>
          )}
        </div>
        <div className="flex gap-1 flex-wrap">
          {TABS.map(({ id, label, Icon }) => (
            <button
              key={id}
              onClick={() => setTab(id)}
              className={`flex items-center gap-1.5 px-3 py-2 text-sm font-medium rounded-md transition-all duration-200 ${
                tab === id
                  ? "text-[var(--ring)] bg-[color-mix(in_srgb,var(--ring)_10%,transparent)]"
                  : "text-[var(--muted-foreground)] hover:text-[var(--foreground)] hover:bg-[var(--muted)]"
              }`}
            >
              <Icon size={15} />{label}
            </button>
          ))}
        </div>
      </div>

      <div key={tab} className="p-6 animate-fade-in-up">
        {tab === "aujourdhui" && (
          <AujourdhuiTab onSessionsChanged={reloadAll} />
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
    </div>
  );
}
