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
import type { AgendaJour } from "@/lib/agenda";
import { fetchToday } from "@/lib/agenda";
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

  const TABS: { id: Tab; label: string }[] = [
    { id: "jour", label: "📅 Aujourd'hui" },
    { id: "semaine", label: "🗓 Semaine" },
    { id: "taches", label: "✅ Tâches" },
  ];

  return (
    <div className="max-w-5xl mx-auto px-4 py-6">
      {/* Titre + résumé rapide */}
      <div className="flex items-start justify-between mb-6">
        <div>
          <h1 className="text-2xl font-bold">Agenda</h1>
          {todayData && (
            <p className="text-sm text-gray-500 mt-1">
              {todayData.taches_urgentes.length > 0 && (
                <span className="text-red-500 font-medium mr-3">
                  ⚠ {todayData.taches_urgentes.length} tâche{todayData.taches_urgentes.length > 1 ? "s" : ""} urgente{todayData.taches_urgentes.length > 1 ? "s" : ""}
                </span>
              )}
              {todayData.slots_libres.length > 0 && (
                <span className="text-green-600">
                  🟢 {todayData.slots_libres.length} slot{todayData.slots_libres.length > 1 ? "s" : ""} libre{todayData.slots_libres.length > 1 ? "s" : ""} aujourd'hui
                </span>
              )}
            </p>
          )}
        </div>
      </div>

      {/* Onglets */}
      <div className="flex border-b mb-6">
        {TABS.map((t) => (
          <button
            key={t.id}
            onClick={() => setTab(t.id)}
            className={`px-5 py-2.5 text-sm font-medium border-b-2 -mb-px transition-colors ${
              tab === t.id
                ? "border-blue-600 text-blue-600"
                : "border-transparent text-gray-500 hover:text-gray-700"
            }`}
          >
            {t.label}
          </button>
        ))}
      </div>

      {/* Contenu */}
      {error && (
        <div className="p-4 bg-red-50 border border-red-200 rounded text-red-700 text-sm mb-4">
          Erreur : {error}
        </div>
      )}

      {tab === "jour" && (
        loading ? (
          <div className="text-gray-400 text-sm text-center py-12">Chargement du planning…</div>
        ) : todayData ? (
          <JourTab data={todayData} />
        ) : null
      )}

      {tab === "semaine" && <SemaineTab />}

      {tab === "taches" && <TachesTab />}
    </div>
  );
}
