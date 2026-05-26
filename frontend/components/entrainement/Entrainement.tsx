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
import { Tabs, TabsList, TabsTrigger, TabsContent } from "@/components/ui/tabs";
import { Badge } from "@/components/ui/badge";
import { Spinner } from "@/components/ui/spinner";
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

  if (loading) return <Spinner label="Chargement de l'entraînement…" />;
  if (error) return <p className="text-sm text-[var(--destructive)]">⚠ {error}</p>;

  const todayWeekday = new Date().getDay() === 0 ? 6 : new Date().getDay() - 1;
  const todayJour = program?.jours.find((j) => j.weekday === todayWeekday);

  return (
    <div className="space-y-4">
      <header className="flex items-center gap-3">
        <Dumbbell className="h-5 w-5 shrink-0" />
        <h1 className="text-xl font-semibold tracking-tight">Entraînement</h1>
        {todayJour && (
          <Badge className="ml-auto">
            {todayJour.label}
            {intensity && (
              <span className="ml-1 opacity-70">· intensité {intensity.intensity}</span>
            )}
          </Badge>
        )}
      </header>

      <Tabs value={tab} onValueChange={(v) => setTab(v as Tab)}>
        <TabsList>
          <TabsTrigger value="aujourdhui">🏋️ Aujourd&apos;hui</TabsTrigger>
          <TabsTrigger value="programme">📅 Programme</TabsTrigger>
          <TabsTrigger value="progression">📈 Progression</TabsTrigger>
          <TabsTrigger value="cardio">🏃 Cardio</TabsTrigger>
          <TabsTrigger value="calendrier">🗓️ Calendrier</TabsTrigger>
        </TabsList>

        <TabsContent value="aujourdhui">
          <AujourdhuiTab onSessionsChanged={reloadAll} />
        </TabsContent>
        <TabsContent value="programme">
          {program && (
            <ProgrammeTab
              program={program}
              exercices={exercices}
              onProgramChanged={reloadAll}
            />
          )}
        </TabsContent>
        <TabsContent value="progression">
          <ProgressionTab exercices={exercices} />
        </TabsContent>
        <TabsContent value="cardio">
          <CardioTab />
        </TabsContent>
        <TabsContent value="calendrier">
          <CalendrierTab sessions={sessions} program={program} />
        </TabsContent>
      </Tabs>
    </div>
  );
}
