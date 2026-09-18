"use client";
/**
 * MoisTab — vue calendrier mensuelle (#84).
 * Grille 7 colonnes (lun→dim) avec les événements par jour.
 */

import { useMemo, useState } from "react";
import type { Evenement } from "@/lib/agenda";
import { couleurFor, formatHeure } from "@/lib/agenda";
import { useAgendaEvents } from "@/lib/queries/agenda";
import { Button } from "@/components/ui/button";
import { Spinner } from "@/components/ui/spinner";

function isoDate(d: Date): string {
  return `${d.getFullYear()}-${String(d.getMonth() + 1).padStart(2, "0")}-${String(d.getDate()).padStart(2, "0")}`;
}

/** Lundi de la grille (peut être dans le mois précédent). */
function gridStart(year: number, month: number): Date {
  const first = new Date(year, month, 1);
  const day = first.getDay(); // 0=dim
  const diff = day === 0 ? -6 : 1 - day;
  const d = new Date(first);
  d.setDate(first.getDate() + diff);
  d.setHours(0, 0, 0, 0);
  return d;
}

const DAY_LABELS = ["Lun", "Mar", "Mer", "Jeu", "Ven", "Sam", "Dim"];

function MonthDayCell({ date, month, today, events }: { date: Date; month: number; today: string; events: Evenement[] }) {
  const dateKey = isoDate(date);
  const inMonth = date.getMonth() === month;
  const dayEvents = events.slice(0, 3);
  return <div className={`min-h-[84px] bg-[var(--background)] p-1 ${inMonth ? "" : "opacity-40"}`}><div className={dateKey === today ? "inline-flex h-5 w-5 items-center justify-center rounded-full bg-[var(--ring)] text-[11px] font-semibold text-white" : "px-1 text-[11px] text-[var(--muted-foreground)]"}>{date.getDate()}</div><div className="mt-0.5 space-y-0.5">{dayEvents.map((event, index) => <div key={index} className="truncate rounded-[var(--radius-sm)] px-1 py-0.5 text-[10px] text-white" style={{ backgroundColor: couleurFor(event) }} title={`${event.titre} ${formatHeure(event.debut)}`}>{event.titre}</div>)}<MoreEvents count={events.length - 3} /></div></div>;
}

function MoreEvents({ count }: { count: number }) {
  if (count <= 0) return null;
  return <div className="px-1 text-[10px] text-[var(--muted-foreground)]">+{count}</div>;
}

export default function MoisTab() {
  const [cursor, setCursor] = useState(() => { const d = new Date(); return { y: d.getFullYear(), m: d.getMonth() }; });

  const days = useMemo(() => {
    const start = gridStart(cursor.y, cursor.m);
    return Array.from({ length: 42 }, (_, i) => {
      const d = new Date(start);
      d.setDate(start.getDate() + i);
      return d;
    });
  }, [cursor]);

  const eventsQ = useAgendaEvents(isoDate(days[0]) + "T00:00:00", isoDate(days[41]) + "T23:59:59");
  const events = useMemo<Evenement[]>(() => eventsQ.data ?? [], [eventsQ.data]);
  const loading = eventsQ.isLoading;

  const byDay = useMemo(() => {
    const m: Record<string, Evenement[]> = {};
    for (const ev of events) {
      const k = ev.debut.slice(0, 10);
      (m[k] ||= []).push(ev);
    }
    for (const k of Object.keys(m)) m[k].sort((a, b) => a.debut.localeCompare(b.debut));
    return m;
  }, [events]);

  const today = isoDate(new Date());
  const monthLabel = new Date(cursor.y, cursor.m, 1).toLocaleDateString("fr-CA", { month: "long", year: "numeric" });
  const shift = (delta: number) =>
    setCursor(({ y, m }) => {
      const d = new Date(y, m + delta, 1);
      return { y: d.getFullYear(), m: d.getMonth() };
    });

  return (
    <div className="space-y-3">
      <div className="flex items-center gap-2">
        <Button variant="secondary" size="sm" onClick={() => shift(-1)} aria-label="Mois précédent">‹</Button>
        <span className="text-sm font-medium flex-1 text-center capitalize">{monthLabel}</span>
        <Button variant="secondary" size="sm" onClick={() => shift(1)} aria-label="Mois suivant">›</Button>
        <Button variant="ghost" size="sm" onClick={() => { const d = new Date(); setCursor({ y: d.getFullYear(), m: d.getMonth() }); }}>
          Aujourd&apos;hui
        </Button>
      </div>

      {loading && <Spinner size="sm" label="Chargement…" />}

      <div className="grid grid-cols-7 gap-px bg-[var(--border)] rounded-[var(--radius)] overflow-hidden">
        {DAY_LABELS.map((l) => (
          <div key={l} className="bg-[var(--background)] text-center py-1.5 text-xs text-[var(--muted-foreground)]">{l}</div>
        ))}
        {days.map((date, index) => <MonthDayCell key={index} date={date} month={cursor.m} today={today} events={byDay[isoDate(date)] || []} />)}
      </div>
    </div>
  );
}
