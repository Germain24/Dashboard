"use client";

import { useState } from "react";
import { Dumbbell, ClipboardList, BarChart2, Activity, CalendarDays } from "lucide-react";
import { todayKey } from "@/lib/entrainement";
import { useExercices, useIntensityToday, useProgram, useSessions } from "@/lib/queries/entrainement";
import { ModuleHeader } from "@/components/layout";
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

  const today = todayKey();
  const from = new Date();
  from.setDate(from.getDate() - 30);
  const fromKey = `${from.getFullYear()}-${String(from.getMonth() + 1).padStart(2, "0")}-${String(from.getDate()).padStart(2, "0")}`;

  const programQ = useProgram();
  const exercicesQ = useExercices();
  const sessionsQ = useSessions({ from: fromKey, to: today });
  const intensityQ = useIntensityToday();

  const program = programQ.data ?? null;
  const exercices = exercicesQ.data ?? [];
  const sessions = sessionsQ.data ?? [];
  const intensity = intensityQ.data ?? null;
  const loading = programQ.isLoading || exercicesQ.isLoading || sessionsQ.isLoading || intensityQ.isLoading;
  const firstError = [programQ, exercicesQ, sessionsQ, intensityQ].find((q) => q.isError);
  const error = firstError ? ((firstError.error as Error)?.message ?? "Erreur de chargement") : null;

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
      <ModuleHeader
        title="Entraînement"
        subtitle="Séances & progression"
        tabs={TABS.map((t) => ({ id: t.id, label: t.label, icon: t.Icon }))}
        active={tab}
        onChange={(id) => setTab(id as Tab)}
        actions={
          todayJour ? (
            <span className="text-xs rounded-[var(--radius-full)] bg-[var(--muted)] px-2.5 py-1 text-[var(--muted-foreground)]">
              Aujourd&apos;hui : <strong>{todayJour.label}</strong>
              {intensity && (
                <span className="ml-2 opacity-70">· intensité {intensity.intensity}</span>
              )}
            </span>
          ) : undefined
        }
      />

      <div key={tab} className="p-6 animate-fade-in-up">
        {tab === "aujourdhui" && (
          <AujourdhuiTab />
        )}
        {tab === "programme" && program && (
          <ProgrammeTab
            program={program}
            exercices={exercices}
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
