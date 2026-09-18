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

const HOURS = Array.from({ length: 24 }, (_, i) => i); // journée complète, nuits comprises

function minutesSinceMidnight(iso: string): number {
  const d = new Date(iso);
  return d.getHours() * 60 + d.getMinutes();
}

const eventTitle = (ev: Evenement) => `${ev.titre}${ev.lieu ? ` — ${ev.lieu}` : ""}${ev.description ? `\n${ev.description}` : ""}`;

function EventDetails({ ev }: { ev: Evenement }) {
  return <><div className="font-semibold truncate">{ev.titre}</div><div className="opacity-80">{formatHeure(ev.debut)}{ev.fin ? ` – ${formatHeure(ev.fin)}` : ""}</div>{ev.lieu && <div className="opacity-70 truncate">{ev.lieu}</div>}</>;
}

function EventBlock({ ev, date }: { ev: Evenement; date: string }) {
  const [year, month, day] = date.split("-").map(Number);
  const dayStart = new Date(year, month - 1, day);
  const dayEnd = new Date(year, month - 1, day + 1);
  const startDate = new Date(ev.debut);
  const endDate = ev.fin ? new Date(ev.fin) : new Date(startDate.getTime() + 60 * 60_000);
  const visibleStart = Math.max(startDate.getTime(), dayStart.getTime());
  const visibleEnd = Math.min(endDate.getTime(), dayEnd.getTime());
  if (visibleEnd <= visibleStart) return null;
  const start = new Date(visibleStart);
  const top = ((start.getHours() * 60 + start.getMinutes()) / 60) * 64;
  const height = Math.max(((visibleEnd - visibleStart) / 3_600_000) * 64, 20);
  const color = couleurFor(ev);

  return (
    <div
      className="absolute left-16 right-2 rounded-[var(--radius-sm)] px-2 py-1 text-white text-xs overflow-hidden"
      style={{ top, height, backgroundColor: color, opacity: ev.is_virtual ? 0.85 : 1 }}
      title={eventTitle(ev)}
    >
      <EventDetails ev={ev} />
    </div>
  );
}

function SlotBlock({ slot }: { slot: SlotLibre }) {
  const start = minutesSinceMidnight(slot.debut);
  const end = minutesSinceMidnight(slot.fin);
  const top = (start / 60) * 64;
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

function buildEvents(data: AgendaJour): Evenement[] {
  const events = [...data.evenements];
  if (data.seance_entrainement?.fin) events.push(data.seance_entrainement);
  return events.sort((a, b) => a.debut.localeCompare(b.debut));
}

function TrainingBadge({ event }: { event: Evenement | null }) {
  if (!event) return null;
  return <div className="rounded-[var(--radius)] border border-[var(--warning-muted)] bg-[var(--warning-muted)] p-3 text-sm"><span className="font-semibold text-[var(--warning-foreground)]">🏋️ {event.titre}</span>{event.description && <span className="ml-2 text-[var(--warning)]">{event.description}</span>}</div>;
}

function DayTimeline({ data, events, showSlots }: { data: AgendaJour; events: Evenement[]; showSlots: boolean }) {
  return <div className="relative overflow-x-hidden" style={{ height: `${24 * 64}px` }}>{HOURS.map((h) => <div key={h} className="absolute left-0 right-0 flex items-center" style={{ top: h * 64 }}><span className="w-14 pr-2 text-right text-xs text-[var(--muted-foreground)]">{h}h</span><div className="flex-1 border-t border-[var(--border)]" /></div>)}{showSlots && data.slots_libres.map((slot, index) => <SlotBlock key={index} slot={slot} />)}{events.map((event, index) => <EventBlock key={index} ev={event} date={data.date} />)}</div>;
}

export default function JourTab({ data }: { data: AgendaJour }) {
  const [showSlots, setShowSlots] = useState(true);

  const allEvents = buildEvents(data);

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
      <TrainingBadge event={data.seance_entrainement} />

      {/* Timeline */}
      <DayTimeline data={data} events={allEvents} showSlots={showSlots} />
    </div>
  );
}
