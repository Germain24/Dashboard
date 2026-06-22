"use client";
/**
 * Agenda — composant principal (orchestrateur + onglets).
 *
 * Onglets :
 *   Aujourd'hui  — timeline du jour + séance entraînement
 *   Semaine      — grille 7 jours
 *   Tâches       — liste priorisée
 */

import { useState } from "react";
import { CalendarDays, CalendarRange, CalendarClock, SlidersHorizontal } from "lucide-react";
import { useAgendaToday } from "@/lib/queries/agenda";
import { ModuleHeader } from "@/components/layout";
import JourTab from "./JourTab";
import SemaineTab from "./SemaineTab";
import MoisTab from "./MoisTab";
import PreferencesTab from "./PreferencesTab";

type Tab = "jour" | "semaine" | "mois" | "preferences";

const TABS: { id: Tab; label: string; Icon: React.ElementType }[] = [
  { id: "jour", label: "Aujourd'hui", Icon: CalendarDays },
  { id: "semaine", label: "Semaine", Icon: CalendarRange },
  { id: "mois", label: "Mois", Icon: CalendarClock },
  { id: "preferences", label: "Préférences", Icon: SlidersHorizontal },
];

export default function Agenda() {
  const [tab, setTab] = useState<Tab>("jour");
  const todayQ = useAgendaToday();
  const todayData = todayQ.data ?? null;
  const loading = todayQ.isLoading;
  const error = todayQ.isError ? (todayQ.error as Error).message : null;

  return (
    <div className="space-y-0 animate-fade-in">
      <ModuleHeader
        title="Agenda"
        subtitle="Événements & tâches"
        tabs={TABS.map((t) => ({ id: t.id, label: t.label, icon: t.Icon }))}
        active={tab}
        onChange={(id) => setTab(id as Tab)}
        actions={
          todayData ? (
            <div className="flex gap-2 text-xs">
              {todayData.taches_urgentes.length > 0 && (
                <span className="rounded-[var(--radius-full)] bg-[color-mix(in_srgb,var(--destructive)_12%,transparent)] text-[var(--destructive)] px-2.5 py-1 font-medium">
                  ⚠ {todayData.taches_urgentes.length} urgente{todayData.taches_urgentes.length > 1 ? "s" : ""}
                </span>
              )}
              {todayData.slots_libres.length > 0 && (
                <span className="rounded-[var(--radius-full)] bg-[color-mix(in_srgb,var(--success,#16a34a)_12%,transparent)] text-[var(--success,#16a34a)] px-2.5 py-1">
                  {todayData.slots_libres.length} slot{todayData.slots_libres.length > 1 ? "s" : ""} libre{todayData.slots_libres.length > 1 ? "s" : ""}
                </span>
              )}
            </div>
          ) : undefined
        }
      />

      <div key={tab} className="p-6 animate-fade-in-up">
        {error && (
          <div className="rounded-xl border border-[var(--destructive)]/30 bg-[color-mix(in_srgb,var(--destructive)_8%,transparent)] px-4 py-3 text-sm text-[var(--destructive)] mb-4">
            Erreur : {error}
          </div>
        )}

        {tab === "jour" && (
          loading ? (
            <div className="space-y-3">
              {[1, 2, 3].map((i) => (
                <div key={i} className="h-16 rounded-xl border border-[var(--border)] bg-[var(--card)] skeleton-shimmer" />
              ))}
            </div>
          ) : todayData ? (
            <JourTab data={todayData} />
          ) : null
        )}

        {tab === "semaine" && <SemaineTab />}
        {tab === "mois" && <MoisTab />}
        {tab === "preferences" && <PreferencesTab />}
      </div>
    </div>
  );
}
