"use client";
/**
 * SemaineTab — vue semaine (7 colonnes × créneaux 30 min).
 * Affiche les événements (ponctuels + récurrences virtuelles + entraînement).
 */

import { useMemo, useState } from "react";
import { toast } from "sonner";
import type { Evenement } from "@/lib/agenda";
import { overlappingKeys, exportIcsUrl } from "@/lib/agenda";
import { useAgendaEvents, useGcalPull, useGcalStatus, useIcalSource, useSyncIcalSource, useSyncIcalUrl } from "@/lib/queries/agenda";
import { WeekFilters, WeekGrid, WeekStatus, WeekToolbar } from "./SemaineParts";

function isoDate(d: Date): string {
  const y = d.getFullYear();
  const m = String(d.getMonth() + 1).padStart(2, "0");
  const day = String(d.getDate()).padStart(2, "0");
  return `${y}-${m}-${day}`;
}

function startOfWeek(d: Date): Date {
  const day = d.getDay();
  const diff = day === 0 ? -6 : 1 - day;
  const mon = new Date(d);
  mon.setDate(d.getDate() + diff);
  mon.setHours(0, 0, 0, 0);
  return mon;
}

export default function SemaineTab() {
  const [weekStart, setWeekStart] = useState<Date>(() => startOfWeek(new Date()));
  const [hidden, setHidden] = useState<Set<string>>(new Set());

  const gcalReady = useGcalStatus().data?.configured ?? false;
  const icalSource = useIcalSource().data;
  const gcalPullMutation = useGcalPull();
  const syncIcalMutation = useSyncIcalUrl();
  const syncWorkCalendar = useSyncIcalSource();

  const weekDates = Array.from({ length: 7 }, (_, i) => {
    const d = new Date(weekStart);
    d.setDate(weekStart.getDate() + i);
    return d;
  });

  const eventsQ = useAgendaEvents(
    isoDate(weekDates[0]) + "T00:00:00",
    isoDate(weekDates[6]) + "T23:59:59",
  );
  const events = useMemo<Evenement[]>(() => eventsQ.data ?? [], [eventsQ.data]);
  const loading = eventsQ.isLoading;

  function prevWeek() {
    setWeekStart((d) => { const n = new Date(d); n.setDate(d.getDate() - 7); return n; });
  }
  function nextWeek() {
    setWeekStart((d) => { const n = new Date(d); n.setDate(d.getDate() + 7); return n; });
  }

  async function handleGoogleSync() {
    try {
      if (gcalReady) {
        // Intégration OAuth : import direct depuis Google Calendar.
        const from = isoDate(weekDates[0]) + "T00:00:00";
        const to = isoDate(weekDates[6]) + "T23:59:59";
        const r = await gcalPullMutation.mutateAsync({ from, to });
        toast.success(`Google Calendar : ${r.created_events} ajouté(s), ${r.updated_events} mis à jour, ${r.skipped_duplicates} inchangé(s).`);
      } else {
        // Repli sans OAuth : adresse secrète .ics.
        const url = window.prompt("Adresse secrète HTTPS au format iCal (Google Calendar) :");
        if (!url) return;
        const r = await syncIcalMutation.mutateAsync(url);
        toast.success(`Sync : ${r.created_events} ajouté(s), ${r.updated_events} mis à jour, ${r.skipped_duplicates} inchangé(s).`);
      }
    } catch (error) {
      toast.error(error instanceof Error ? error.message : "Sync Google impossible.");
    }
  }

  async function handleIcalSync() {
    if (!icalSource?.configured) {
      toast.error("Ajoute le lien iCal dans Agenda → Préférences avant de synchroniser.");
      return;
    }
    try {
      const r = await syncWorkCalendar.mutateAsync();
      toast.success(`Travail : ${r.created_events} ajouté(s), ${r.updated_events} mis à jour, ${r.deleted_events} retiré(s), ${r.skipped_duplicates} inchangé(s).`);
    } catch (error) {
      toast.error(error instanceof Error ? error.message : "Synchronisation iCal impossible.");
    }
  }

  const catOf = (ev: Evenement) => ev.categorie || "autre";
  const presentCats = useMemo(
    () => Array.from(new Set(events.map(catOf))).sort(),
    [events],
  );
  const toggleCat = (c: string) =>
    setHidden((h) => {
      const n = new Set(h);
      if (n.has(c)) n.delete(c); else n.add(c);
      return n;
    });

  function eventsForDay(date: Date): Evenement[] {
    const start = new Date(date.getFullYear(), date.getMonth(), date.getDate()).getTime();
    const end = start + 24 * 60 * 60_000;
    return events.filter((ev) => {
      if (hidden.has(catOf(ev))) return false;
      const eventStart = new Date(ev.debut).getTime();
      const eventEnd = ev.fin ? new Date(ev.fin).getTime() : eventStart + 60 * 60_000;
      return eventStart < end && eventEnd > start;
    });
  }

  // Conflits d'horaire (#87) : on calcule par jour pour ne pas croiser deux jours différents.
  const conflictKeys = useMemo(() => {
    const set = new Set<string>();
    for (const d of weekDates) {
      for (const k of overlappingKeys(eventsForDay(d))) set.add(k);
    }
    return set;
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [events, hidden]);
  const keyOf = (e: Evenement) => (e.id != null ? String(e.id) : e.debut + "|" + e.titre);

  const today = isoDate(new Date());

  return (
    <div className="space-y-3">
      <WeekToolbar weekDates={weekDates} gcalReady={gcalReady} iCalConfigured={Boolean(icalSource?.configured)} iCalSyncing={syncWorkCalendar.isPending} exportUrl={exportIcsUrl(isoDate(weekDates[0]) + "T00:00:00", isoDate(weekDates[6]) + "T23:59:59")} onPrev={prevWeek} onNext={nextWeek} onToday={() => setWeekStart(startOfWeek(new Date()))} onGoogle={() => void handleGoogleSync()} onIcal={() => void handleIcalSync()} />

      <WeekFilters categories={presentCats} hidden={hidden} toggle={toggleCat} />

      <WeekStatus loading={loading} conflicts={conflictKeys.size} />

      <WeekGrid weekDates={weekDates} today={today} eventsForDay={eventsForDay} conflictKeys={conflictKeys} keyOf={keyOf} />
    </div>
  );
}
