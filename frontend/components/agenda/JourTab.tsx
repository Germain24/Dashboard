"use client";
/**
 * JourTab — timeline horaire du jour.
 * Affiche événements + séance entraînement + slots libres.
 * Boucle CONV 7 : seance_entrainement vient du bridge in-process via GET /agenda/today.
 */

import { useState } from "react";
import type { AgendaJour, Evenement, SlotLibre } from "@/lib/agenda";
import { couleurFor, formatHeure } from "@/lib/agenda";
import { Button } from "@/components/ui/button";

const HOURS = Array.from({ length: 16 }, (_, i) => i + 7); // 7h → 22h

function minutesSinceMidnight(iso: string): number {
  const d = new Date(iso);
  return d.getHours() * 60 + d.getMinutes();
}

function EventBlock({ ev, dayStart = 7 * 60 }: { ev: Evenement; dayStart?: number }) {
  const start = minutesSinceMidnight(ev.debut);
  const end = ev.fin ? minutesSinceMidnight(ev.fin) : start + 60;
  const top = ((start - dayStart) / 60) * 64;
  const height = Math.max(((end - start) / 60) * 64, 28);
  const color = couleurFor(ev);

  return (
    <div
      className="absolute left-16 right-2 rounded-[var(--radius-sm)] px-2 py-1 text-white text-xs overflow-hidden"
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
      className="absolute left-16 right-2 rounded-[var(--radius-sm)] border border-dashed border-[var(--success)] bg-[var(--success-muted)] px-2 py-1 text-[var(--success-foreground)] text-xs"
      style={{ top, height }}
    >
      🟢 Libre {slot.duree_min} min
    </div>
  );
}

export default function JourTab({ data }: { data: AgendaJour }) {
  const [showSlots, setShowSlots] = useState(true);

  const allEvents: Evenement[] = [...data.evenements];
  // Séance loggée (horaire réel) → timeline ; séance planifiée (flexible,
  // fin=null) → badge seulement, elle se fait à n'importe quel moment.
  if (data.seance_entrainement?.fin) allEvents.push(data.seance_entrainement);
  allEvents.sort((a, b) => a.debut.localeCompare(b.debut));

  const dayStart = 7 * 60;

  return (
    <div className="space-y-3">
      <div className="flex items-center justify-between">
        <h2 className="text-base font-semibold capitalize">
          {new Date(data.date).toLocaleDateString("fr-CA", {
            weekday: "long", day: "numeric", month: "long",
          })}
        </h2>
        <Button
          variant="secondary"
          size="sm"
          onClick={() => setShowSlots((s) => !s)}
        >
          {showSlots ? "Masquer slots" : "Afficher slots"}
        </Button>
      </div>

      {/* Badge séance du jour */}
      {data.seance_entrainement && (
        <div className="rounded-[var(--radius)] border border-[var(--warning-muted)] bg-[var(--warning-muted)] p-3 text-sm">
          <span className="font-semibold text-[var(--warning-foreground)]">
            🏋️ {data.seance_entrainement.titre}
          </span>
          {data.seance_entrainement.description && (
            <span className="ml-2 text-[var(--warning)]">
              {data.seance_entrainement.description}
            </span>
          )}
        </div>
      )}

      {/* Timeline */}
      <div className="relative overflow-x-hidden" style={{ height: `${16 * 64}px` }}>
        {HOURS.map((h) => (
          <div
            key={h}
            className="absolute left-0 right-0 flex items-center"
            style={{ top: (h - 7) * 64 }}
          >
            <span className="w-14 text-right text-xs text-[var(--muted-foreground)] pr-2">
              {h}h
            </span>
            <div className="flex-1 border-t border-[var(--border)]" />
          </div>
        ))}

        {showSlots &&
          data.slots_libres.map((s, i) => (
            <SlotBlock key={i} slot={s} dayStart={dayStart} />
          ))}

        {allEvents.map((ev, i) => (
          <EventBlock key={i} ev={ev} dayStart={dayStart} />
        ))}
      </div>
    </div>
  );
}
