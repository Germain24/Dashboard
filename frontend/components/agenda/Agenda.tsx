"use client";
/**
 * Agenda — composant principal (orchestrateur + onglets).
 *
 * Onglets :
 *   Aujourd'hui  — timeline du jour + séance entraînement
 *   Semaine      — grille 7 jours
 *   Tâches       — liste priorisée
 */

import { useEffect, useState } from "react";
import { CalendarDays, CalendarRange, CheckSquare } from "lucide-react";
import type { AgendaJour } from "@/lib/agenda";
import { fetchToday } from "@/lib/agenda";
import JourTab from "./JourTab";
import SemaineTab from "./SemaineTab";
import TachesTab from "./TachesTab";

type Tab = "jour" | "semaine" | "taches";

const TABS: { id: Tab; label: string; Icon: React.ElementType }[] = [
  { id: "jour", label: "Aujourd'hui", Icon: CalendarDays },
  { id: "semaine", label: "Semaine", Icon: CalendarRange },
  { id: "taches", label: "Tâches", Icon: CheckSquare },
];

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
    <div className="space-y-0 animate-fade-in">
      <div className="px-6 py-5 border-b border-[var(--border)]">
        <div className="mb-4 flex items-start justify-between">
          <div>
            <h1 className="text-xl font-semibold tracking-tight">Agenda</h1>
            <p className="text-sm text-[var(--muted-foreground)] mt-0.5">Événements &amp; tâches</p>
          </div>
          {todayData && (
            <div className="flex gap-2 text-xs">
              {todayData.taches_urgentes.length > 0 && (
                <span className="rounded-md bg-[color-mix(in_srgb,var(--destructive)_12%,transparent)] text-[var(--destructive)] px-2.5 py-1 font-medium">
                  ⚠ {todayData.taches_urgentes.length} urgente{todayData.taches_urgentes.length > 1 ? "s" : ""}
                </span>
              )}
              {todayData.slots_libres.length > 0 && (
                <span className="rounded-md bg-[color-mix(in_srgb,var(--success,#16a34a)_12%,transparent)] text-[var(--success,#16a34a)] px-2.5 py-1">
                  {todayData.slots_libres.length} slot{todayData.slots_libres.length > 1 ? "s" : ""} libre{todayData.slots_libres.length > 1 ? "s" : ""}
                </span>
              )}
            </div>
          )}
        </div>
        <div className="flex gap-1">
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
        {tab === "taches" && <TachesTab />}
      </div>
    </div>
  );
}
