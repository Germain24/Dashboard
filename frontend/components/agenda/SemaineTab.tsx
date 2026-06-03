"use client";
/**
 * SemaineTab — vue semaine (7 colonnes × créneaux 30 min).
 * Affiche les événements (ponctuels + récurrences virtuelles + entraînement).
 */

import { useEffect, useMemo, useState } from "react";
import type { Evenement } from "@/lib/agenda";
import { couleurFor, fetchEvents, formatHeure, overlappingKeys, exportIcsUrl, syncIcalUrl, CATEGORIE_COLORS } from "@/lib/agenda";
import { Button } from "@/components/ui/button";
import { Spinner } from "@/components/ui/spinner";

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

const HOURS = Array.from({ length: 15 }, (_, i) => i + 7);
const DAY_LABELS = ["Lun", "Mar", "Mer", "Jeu", "Ven", "Sam", "Dim"];

export default function SemaineTab() {
  const [weekStart, setWeekStart] = useState<Date>(() => startOfWeek(new Date()));
  const [events, setEvents] = useState<Evenement[]>([]);
  const [loading, setLoading] = useState(false);
  const [hidden, setHidden] = useState<Set<string>>(new Set());

  const weekDates = Array.from({ length: 7 }, (_, i) => {
    const d = new Date(weekStart);
    d.setDate(weekStart.getDate() + i);
    return d;
  });

  useEffect(() => {
    setLoading(true);
    const from = isoDate(weekDates[0]) + "T00:00:00";
    const to = isoDate(weekDates[6]) + "T23:59:59";
    fetchEvents(from, to)
      .then(setEvents)
      .catch(console.error)
      .finally(() => setLoading(false));
  // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [weekStart]);

  function prevWeek() {
    setWeekStart((d) => { const n = new Date(d); n.setDate(d.getDate() - 7); return n; });
  }
  function nextWeek() {
    setWeekStart((d) => { const n = new Date(d); n.setDate(d.getDate() + 7); return n; });
  }

  async function handleGoogleSync() {
    const url = window.prompt("Adresse secrète au format iCal (Google Calendar) :");
    if (!url) return;
    try {
      const r = await syncIcalUrl(url);
      window.alert(`Sync : ${r.created_events} ajouté(s), ${r.skipped_duplicates} déjà présent(s).`);
      setWeekStart((d) => new Date(d));
    } catch {
      window.alert("Sync impossible (URL invalide ou inaccessible).");
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
    const ds = isoDate(date);
    return events.filter((ev) => ev.debut.startsWith(ds) && !hidden.has(catOf(ev)));
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
      {/* Nav semaine */}
      <div className="flex items-center gap-2">
        <Button variant="secondary" size="sm" onClick={prevWeek} aria-label="Semaine précédente">‹</Button>
        <span className="text-sm font-medium flex-1 text-center">
          Semaine du{" "}
          {weekDates[0].toLocaleDateString("fr-CA", { day: "numeric", month: "long" })}
          {" au "}
          {weekDates[6].toLocaleDateString("fr-CA", { day: "numeric", month: "long", year: "numeric" })}
        </span>
        <Button variant="secondary" size="sm" onClick={nextWeek} aria-label="Semaine suivante">›</Button>
        <Button
          variant="ghost"
          size="sm"
          onClick={() => setWeekStart(startOfWeek(new Date()))}
        >
          Aujourd&apos;hui
        </Button>
        <a
          href={exportIcsUrl(isoDate(weekDates[0]) + "T00:00:00", isoDate(weekDates[6]) + "T23:59:59")}
          className="rounded-md px-2.5 py-1 text-sm text-[var(--muted-foreground)] hover:text-[var(--foreground)] hover:bg-[var(--muted)]"
          title="Exporter cette semaine au format .ics"
        >
          ⬇ .ics
        </a>
        <Button
          variant="ghost"
          size="sm"
          onClick={() => void handleGoogleSync()}
          title="Importer un calendrier Google via son URL .ics secrète"
        >
          ⇄ Google
        </Button>
      </div>

      {/* Filtres / légende par catégorie (#88) */}
      {presentCats.length > 0 && (
        <div className="flex flex-wrap gap-1.5">
          {presentCats.map((c) => {
            const active = !hidden.has(c);
            const color = CATEGORIE_COLORS[c] || "#6B7280";
            return (
              <button
                key={c}
                onClick={() => toggleCat(c)}
                aria-pressed={active}
                className={`inline-flex items-center gap-1.5 rounded-full border px-2.5 py-1 text-xs transition-opacity ${active ? "border-[var(--border)]" : "border-transparent opacity-40"}`}
              >
                <span className="h-2.5 w-2.5 rounded-full" style={{ backgroundColor: color }} />
                {c}
              </button>
            );
          })}
        </div>
      )}

      {loading && <Spinner size="sm" label="Chargement…" />}

      {conflictKeys.size > 0 && (
        <div className="rounded-[var(--radius-sm)] border border-[var(--destructive)]/40 bg-[color-mix(in_srgb,var(--destructive)_8%,transparent)] px-3 py-1.5 text-xs text-[var(--destructive)]">
          ⚠ {conflictKeys.size} événement{conflictKeys.size > 1 ? "s" : ""} en chevauchement cette semaine.
        </div>
      )}

      {/* Grille */}
      <div className="overflow-x-auto">
        <div
          className="grid gap-px bg-[var(--border)] rounded-[var(--radius)] overflow-hidden"
          style={{ gridTemplateColumns: `56px repeat(7, minmax(88px, 1fr))` }}
        >
          {/* Header */}
          <div className="bg-[var(--background)]" />
          {weekDates.map((d, i) => (
            <div
              key={i}
              className="bg-[var(--background)] text-center py-2"
            >
              <div className="text-xs text-[var(--muted-foreground)]">{DAY_LABELS[i]}</div>
              <div
                className={
                  isoDate(d) === today
                    ? "mx-auto mt-0.5 flex h-6 w-6 items-center justify-center rounded-full bg-[var(--ring)] text-xs font-semibold text-white"
                    : "text-sm font-medium text-[var(--foreground)]"
                }
              >
                {d.getDate()}
              </div>
            </div>
          ))}

          {/* Créneaux horaires */}
          {HOURS.map((h) => (
            <>
              <div
                key={`h${h}`}
                className="bg-[var(--background)] text-right pr-2 text-xs text-[var(--muted-foreground)] pt-1"
              >
                {h}h
              </div>
              {weekDates.map((d, di) => {
                const dayEvs = eventsForDay(d).filter(
                  (ev) => new Date(ev.debut).getHours() === h,
                );
                return (
                  <div
                    key={`${h}-${di}`}
                    className="bg-[var(--background)] min-h-[36px] border-t border-[var(--border)] p-0.5"
                  >
                    {dayEvs.map((ev, ei) => {
                      const conflict = conflictKeys.has(keyOf(ev));
                      return (
                        <div
                          key={ei}
                          className={`rounded-[var(--radius-sm)] px-1 py-0.5 text-white text-xs mb-0.5 truncate ${conflict ? "ring-2 ring-[var(--destructive)]" : ""}`}
                          style={{ backgroundColor: couleurFor(ev) }}
                          title={`${conflict ? "⚠ Chevauchement — " : ""}${ev.titre} ${formatHeure(ev.debut)}${ev.fin ? " – " + formatHeure(ev.fin) : ""}`}
                        >
                          {conflict ? "⚠ " : ""}{formatHeure(ev.debut)} {ev.titre}
                        </div>
                      );
                    })}
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
