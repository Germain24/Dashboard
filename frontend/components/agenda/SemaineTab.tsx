"use client";
/**
 * SemaineTab — vue semaine (7 colonnes × créneaux 30 min).
 * Affiche les événements (ponctuels + récurrences virtuelles + entraînement).
 */

import { useEffect, useState } from "react";
import type { Evenement } from "@/lib/agenda";
import { couleurFor, fetchEvents, formatHeure } from "@/lib/agenda";

/** Date locale YYYY-MM-DD — N'utilise PAS toISOString() qui convertit en UTC.
 *  En soirée à Montréal (UTC-4), toISOString() renverrait le lendemain,
 *  ce qui décale les événements d'une colonne vers la droite.
 */
function isoDate(d: Date): string {
  const y = d.getFullYear();
  const m = String(d.getMonth() + 1).padStart(2, "0");
  const day = String(d.getDate()).padStart(2, "0");
  return `${y}-${m}-${day}`;
}

function startOfWeek(d: Date): Date {
  const day = d.getDay(); // 0=Sun
  const diff = day === 0 ? -6 : 1 - day; // adjust to Mon
  const mon = new Date(d);
  mon.setDate(d.getDate() + diff);
  mon.setHours(0, 0, 0, 0);
  return mon;
}

const HOURS = Array.from({ length: 15 }, (_, i) => i + 7); // 7h…21h
const DAY_LABELS = ["Lun", "Mar", "Mer", "Jeu", "Ven", "Sam", "Dim"];

export default function SemaineTab() {
  const [weekStart, setWeekStart] = useState<Date>(() => startOfWeek(new Date()));
  const [events, setEvents] = useState<Evenement[]>([]);
  const [loading, setLoading] = useState(false);

  const weekDates = Array.from({ length: 7 }, (_, i) => {
    const d = new Date(weekStart);
    d.setDate(weekStart.getDate() + i);
    return d;
  });

  useEffect(() => {
    setLoading(true);
    // Dates locales (pas UTC) pour éviter le décalage de fuseau horaire
    const from = isoDate(weekDates[0]) + "T00:00:00";
    const to   = isoDate(weekDates[6]) + "T23:59:59";
    fetchEvents(from, to)
      .then(setEvents)
      .catch(console.error)
      .finally(() => setLoading(false));
  }, [weekStart]);

  function prevWeek() { setWeekStart(d => { const n = new Date(d); n.setDate(d.getDate() - 7); return n; }); }
  function nextWeek() { setWeekStart(d => { const n = new Date(d); n.setDate(d.getDate() + 7); return n; }); }

  function eventsForDay(date: Date): Evenement[] {
    const ds = isoDate(date);
    return events.filter(ev => ev.debut.startsWith(ds));
  }

  const today = isoDate(new Date());

  return (
    <div>
      {/* Nav semaine */}
      <div className="flex items-center gap-3 mb-4">
        <button onClick={prevWeek} className="px-2 py-1 border rounded hover:bg-gray-50">‹</button>
        <span className="font-medium text-sm">
          Semaine du {weekDates[0].toLocaleDateString("fr-CA", { day: "numeric", month: "long" })}
          {" au "}{weekDates[6].toLocaleDateString("fr-CA", { day: "numeric", month: "long", year: "numeric" })}
        </span>
        <button onClick={nextWeek} className="px-2 py-1 border rounded hover:bg-gray-50">›</button>
        <button
          onClick={() => setWeekStart(startOfWeek(new Date()))}
          className="ml-auto text-xs text-blue-600 hover:underline"
        >
          Aujourd'hui
        </button>
      </div>

      {loading && <div className="text-sm text-gray-400 mb-2">Chargement…</div>}

      {/* Grille */}
      <div className="overflow-x-auto">
        <div className="grid gap-px bg-gray-200 rounded overflow-hidden" style={{ gridTemplateColumns: `64px repeat(7, minmax(100px,1fr))` }}>
          {/* Header */}
          <div className="bg-white" />
          {weekDates.map((d, i) => (
            <div
              key={i}
              className={`bg-white text-center py-2 text-xs font-semibold ${isoDate(d) === today ? "text-blue-600" : "text-gray-600"}`}
            >
              <div>{DAY_LABELS[i]}</div>
              <div className={`text-base ${isoDate(d) === today ? "bg-blue-600 text-white rounded-full w-7 h-7 flex items-center justify-center mx-auto" : ""}`}>
                {d.getDate()}
              </div>
            </div>
          ))}

          {/* Créneaux horaires */}
          {HOURS.map(h => (
            <>
              <div key={`h${h}`} className="bg-white text-right pr-2 text-xs text-gray-400 pt-1">{h}h</div>
              {weekDates.map((d, di) => {
                const dayEvs = eventsForDay(d).filter(ev => {
                  const evH = new Date(ev.debut).getHours();
                  return evH === h;
                });
                return (
                  <div key={`${h}-${di}`} className="bg-white min-h-[40px] border-t border-gray-50 p-0.5">
                    {dayEvs.map((ev, ei) => (
                      <div
                        key={ei}
                        className="rounded px-1 py-0.5 text-white text-xs mb-0.5 truncate"
                        style={{ backgroundColor: couleurFor(ev) }}
                        title={`${ev.titre} ${formatHeure(ev.debut)}${ev.fin ? " – " + formatHeure(ev.fin) : ""}`}
                      >
                        {formatHeure(ev.debut)} {ev.titre}
                      </div>
                    ))}
                  </div>
                );
              })}
            </>
          ))}
        </div>
      </div>
    </div>
  );
}
