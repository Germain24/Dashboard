"use client";
/**
 * Agenda — composant principal (orchestrateur + onglets).
 *
 * Onglets :
 *   📅 Aujourd'hui  — timeline du jour + séance entraînement (boucle CONV 7)
 *   🗓 Semaine      — grille 7 jours
 *   ✅ Tâches       — liste priorisée
 */

import { useEffect, useState } from "react";
import { CalendarDays } from "lucide-react";
import type { AgendaJour } from "@/lib/agenda";
import { fetchToday } from "@/lib/agenda";
import { Tabs, TabsList, TabsTrigger, TabsContent } from "@/components/ui/tabs";
import { Badge } from "@/components/ui/badge";
import { Spinner } from "@/components/ui/spinner";
import JourTab from "./JourTab";
import SemaineTab from "./SemaineTab";
import TachesTab from "./TachesTab";

type Tab = "jour" | "semaine" | "taches";

export default function Agenda() {
  const [tab, setTab] = useState<Tab>("jour");
  const [todayData, setTodayData] = useState<AgendaJour | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    fetchToday()
      .then(setTodayData)
      .catch((e) => setError(e.message))
      .finally(() => setLoading(false));
  }, []);

  return (
    <div className="space-y-4">
      <header className="flex items-center gap-3">
        <CalendarDays className="h-5 w-5 shrink-0" />
        <h1 className="text-xl font-semibold tracking-tight">Agenda</h1>
        {todayData && todayData.taches_urgentes.length > 0 && (
          <Badge variant="destructive" className="ml-auto">
            ⚠ {todayData.taches_urgentes.length} urgente
            {todayData.taches_urgentes.length > 1 ? "s" : ""}
          </Badge>
        )}
      </header>

      {error && (
        <div className="rounded-[var(--radius)] border border-[var(--destructive-muted)] bg-[var(--destructive-muted)] px-4 py-3 text-sm text-[var(--destructive)]">
          Erreur : {error}
        </div>
      )}

      <Tabs value={tab} onValueChange={(v) => setTab(v as Tab)}>
        <TabsList>
          <TabsTrigger value="jour">📅 Aujourd&apos;hui</TabsTrigger>
          <TabsTrigger value="semaine">🗓 Semaine</TabsTrigger>
          <TabsTrigger value="taches">✅ Tâches</TabsTrigger>
        </TabsList>

        <TabsContent value="jour">
          {loading ? (
            <Spinner label="Chargement du planning…" className="py-12 justify-center" />
          ) : todayData ? (
            <JourTab data={todayData} />
          ) : null}
        </TabsContent>

        <TabsContent value="semaine">
          <SemaineTab />
        </TabsContent>

        <TabsContent value="taches">
          <TachesTab />
        </TabsContent>
      </Tabs>
    </div>
  );
}
