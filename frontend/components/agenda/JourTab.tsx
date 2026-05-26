"use client";
/**
 * JourTab — timeline horaire du jour.
 * Affiche événements + séance entraînement + slots libres.
 * Boucle CONV 7 : seance_entrainement vient du bridge in-process via GET /agenda/today.
 */

import { useState } from "react";
import type { AgendaJour, Evenement, SlotLibre } from "@/lib/agenda";
import { couleurFor, formatHeure } from "@/lib/agenda";

const HOURS = Array.from({ length: 16 }, (_, i) => i + 7); // 7h → 22h

function minutesSinceMidnight(iso: string): number {
  const d = new Date(iso);
  return d.getHours() * 60 + d.getMinutes();
}

function EventBlock({ ev, dayStart = 7 * 60 }: { ev: Evenement; dayStart?: number }) {
  const start = minutesSinceMidnight(ev.debut);
  const end = ev.fin ? minutesSinceMidnight(ev.fin) : start + 60;
  const top = ((start - dayStart) / 60) * 64; // 64px/heure
  const height = Math.max(((end - start) / 60) * 64, 28);
  const color = couleurFor(ev);

  return (
    <div
      className="absolute left-16 right-2 rounded px-2 py-1 text-white text-xs overflow-hidden shadow"
      style={{ top, height, backgroundColor: color, opacity: ev.is_virtual ? 0.85 : 1 }}
      title={`${ev.titre}${ev.lieu ? ` — ${ev.lieu}` : ""}${ev.description ? `\n${ev.description}` : ""}`}
    >
      <div className="font-semibold truncate">{ev.titre}</div>
      <div className="opacity-80">{formatHeure(ev.debut)}{ev.fin ? ` – ${formatHeure(ev.fin)}` : ""}</div>
      {ev.lieu && <div className="opacity-70 truncate">{ev.lieu}</div>}
    </div>
  );
}

function SlotBlock({ slot, dayStart = 7 * 60 }: { slot: SlotLibre; dayStart?: number }) {
  const start = minutesSinceMidnight(slot.debut);
  const end = minutesSinceMidnight(slot.fin);
  const top = ((start - dayStart) / 60) * 64;
  const height = Math.max(((end - start) / 60) * 64, 20);
  return (
    <div
      className="absolute left-16 right-2 rounded border border-dashed border-green-400 bg-green-50 px-2 py-1 text-green-700 text-xs"
      style={{ top, height }}
    >
      🟢 Libre {slot.duree_min} min
    </div>
  );
}

export default function JourTab({ data }: { data: AgendaJour }) {
  const [showSlots, setShowSlots] = useState(true);

  const allEvents: Evenement[] = [...data.evenements];
  if (data.seance_entrainement) allEvents.push(data.seance_entrainement);
  allEvents.sort((a, b) => a.debut.localeCompare(b.debut));

  const dayStart = 7 * 60;

  return (
    <div>
      {/* Header */}
      <div className="flex items-center justify-between mb-4">
        <h2 className="text-lg font-semibold capitalize">
          {new Date(data.date).toLocaleDateString("fr-CA", { weekday: "long", day: "numeric", month: "long" })}
        </h2>
        <button
          onClick={() => setShowSlots(s => !s)}
          className="text-sm px-3 py-1 rounded border border-gray-300 hover:bg-gray-50"
        >
          {showSlots ? "Masquer slots libres" : "Afficher slots libres"}
        </button>
      </div>

      {/* Séance du jour (badge spécial) */}
      {data.seance_entrainement && (
        <div className="mb-3 p-3 rounded-lg bg-amber-50 border border-amber-200 text-sm">
          <span className="font-semibold text-amber-800">🏋️ {data.seance_entrainement.titre}</span>
          {data.seance_entrainement.description && (
            <span className="ml-2 text-amber-600">{data.seance_entrainement.description}</span>
          )}
        </div>
      )}

      {/* Timeline */}
      <div className="relative overflow-x-hidden" style={{ height: `${16 * 64}px` }}>
        {/* Lignes horaires */}
        {HOURS.map(h => (
          <div key={h} className="absolute left-0 right-0 flex items-center" style={{ top: (h - 7) * 64 }}>
            <span className="w-14 text-right text-xs text-gray-400 pr-2">{h}h</span>
            <div className="flex-1 border-t border-gray-100" />
          </div>
        ))}

        {/* Slots libres */}
        {showSlots && data.slots_libres.map((s, i) => (
          <SlotBlock key={i} slot={s} dayStart={dayStart} />
        ))}

        {/* Événements (par-dessus les slots) */}
        {allEvents.map((ev, i) => (
          <EventBlock key={i} ev={ev} dayStart={dayStart} />
        ))}
      </div>
    </div>
  );
}
