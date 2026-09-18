"use client";

import { Activity, BarChart2, CalendarDays, ClipboardList, Dumbbell } from "lucide-react";
import { ModuleHeader } from "@/components/layout";
import {
  todayKey,
  type Exercice,
  type IntensityResponse,
  type Programme,
  type ProgrammeJour,
  type Seance,
} from "@/lib/entrainement";
import { queryError } from "./AujourdhuiTabController";
import {
  useExercices,
  useIntensityToday,
  useProgram,
  useSessions,
} from "@/lib/queries/entrainement";
import { AujourdhuiTab } from "./AujourdhuiTab";
import { CardioTab } from "./CardioTab";
import { CalendrierTab } from "./CalendrierTab";
import { ProgressionTab } from "./ProgressionTab";
import { ProgrammeTab } from "./ProgrammeTab";

export type Tab = "aujourdhui" | "programme" | "progression" | "cardio" | "calendrier";

type TrainingPageData = {
  program: Programme | null;
  exercices: Exercice[];
  sessions: Seance[];
  intensity: IntensityResponse | null;
  loading: boolean;
  error: string | null;
  todayJour: ProgrammeJour | undefined;
};

export const TABS: { id: Tab; label: string; Icon: React.ElementType }[] = [
  { id: "aujourdhui", label: "Aujourd'hui", Icon: Dumbbell },
  { id: "programme", label: "Programme", Icon: ClipboardList },
  { id: "progression", label: "Progression", Icon: BarChart2 },
  { id: "cardio", label: "Cardio", Icon: Activity },
  { id: "calendrier", label: "Calendrier", Icon: CalendarDays },
];
export const TRAINING_TAB_PANEL_ID = "entrainement-tab-panel";

export function useTrainingPageData(): TrainingPageData {
  const today = todayKey();
  const fromKey = daysAgoKey(30);
  const programQ = useProgram();
  const exercicesQ = useExercices();
  const sessionsQ = useSessions({ from: fromKey, to: today });
  const intensityQ = useIntensityToday();
  const queries = [programQ, exercicesQ, sessionsQ, intensityQ];
  const firstError = queries.find((query) => query.isError);
  const program = valueOr(programQ.data, null);

  return {
    program,
    exercices: valueOr(exercicesQ.data, []),
    sessions: valueOr(sessionsQ.data, []),
    intensity: valueOr(intensityQ.data, null),
    loading: queries.some((query) => query.isLoading),
    error: firstError ? queryError(firstError.error, true) : null,
    todayJour: findTodayJour(program),
  };
}

function valueOr<T>(value: T | undefined, fallback: T): T {
  return value ?? fallback;
}

function findTodayJour(program: Programme | null): ProgrammeJour | undefined {
  if (!program) return undefined;
  return program.jours.find((jour) => jour.weekday === weekdayToday());
}

function daysAgoKey(days: number): string {
  const date = new Date();
  date.setDate(date.getDate() - days);
  return `${date.getFullYear()}-${String(date.getMonth() + 1).padStart(2, "0")}-${String(date.getDate()).padStart(2, "0")}`;
}

function weekdayToday(): number {
  const day = new Date().getDay();
  return day === 0 ? 6 : day - 1;
}

export function TrainingLoading() {
  return (
    <div className="p-6 space-y-4 animate-fade-in">
      {[1, 2, 3].map((item) => (
        <div
          key={item}
          className="h-20 rounded-xl border border-[var(--border)] bg-[var(--card)] skeleton-shimmer"
        />
      ))}
    </div>
  );
}

export function TrainingError({ message }: { message: string }) {
  return <div className="p-6 text-[var(--destructive)]">⚠ {message}</div>;
}

export function TrainingHeader({
  tab,
  onTabChange,
  todayJour,
  intensity,
}: {
  tab: Tab;
  onTabChange: (tab: Tab) => void;
  todayJour: ProgrammeJour | undefined;
  intensity: IntensityResponse | null;
}) {
  return (
    <ModuleHeader
      title="Entraînement"
      subtitle="Séances & progression"
      tabs={TABS.map((item) => ({ id: item.id, label: item.label, icon: item.Icon }))}
      active={tab}
      onChange={(id) => onTabChange(id as Tab)}
      panelId={TRAINING_TAB_PANEL_ID}
      actions={todayJour ? <TodayBadge jour={todayJour} intensity={intensity} /> : undefined}
    />
  );
}

function TodayBadge({
  jour,
  intensity,
}: {
  jour: ProgrammeJour;
  intensity: IntensityResponse | null;
}) {
  return (
    <span className="text-xs rounded-[var(--radius-full)] bg-[var(--muted)] px-2.5 py-1 text-[var(--muted-foreground)]">
      Aujourd&apos;hui : <strong>{jour.label}</strong>
      {intensity && <span className="ml-2 opacity-70">· intensité {intensity.intensity}</span>}
    </span>
  );
}

export function TrainingTabContent({
  tab,
  program,
  exercices,
  sessions,
}: {
  tab: Tab;
  program: Programme | null;
  exercices: Exercice[];
  sessions: Seance[];
}) {
  const views: Record<Tab, () => React.ReactNode> = {
    aujourdhui: () => <AujourdhuiTab />,
    programme: () => (program ? <ProgrammeTab program={program} exercices={exercices} /> : null),
    progression: () => <ProgressionTab exercices={exercices} />,
    cardio: () => <CardioTab />,
    calendrier: () => <CalendrierTab sessions={sessions} program={program} />,
  };
  return views[tab]();
}
