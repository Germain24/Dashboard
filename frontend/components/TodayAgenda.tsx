"use client";

/** Aperçu « aujourd'hui » sur l'accueil : prochains événements + tâches urgentes (#90). */

import { useEffect, useState } from "react";
import Link from "next/link";
import { fetchToday, couleurFor, formatHeure, type AgendaJour } from "@/lib/agenda";

export function TodayAgenda() {
  const [data, setData] = useState<AgendaJour | null>(null);
  const [failed, setFailed] = useState(false);

  useEffect(() => {
    fetchToday().then(setData).catch(() => setFailed(true));
  }, []);

  if (failed || !data) return null;

  const now = new Date();
  const upcoming = [...data.evenements, ...(data.seance_entrainement ? [data.seance_entrainement] : [])]
    .filter((e) => new Date(e.fin ?? e.debut) >= now)
    .sort((a, b) => a.debut.localeCompare(b.debut))
    .slice(0, 4);

  const urgentes = data.taches_urgentes.length;

  if (upcoming.length === 0 && urgentes === 0) return null;

  return (
    <section aria-label="Aujourd'hui" className="mb-8 animate-fade-in">
      <div className="mb-3 flex items-center justify-between">
        <h2 className="text-xs font-medium uppercase tracking-widest text-[var(--muted-foreground)]">
          Aujourd&apos;hui
        </h2>
        <Link href="/agenda" className="text-xs text-[var(--muted-foreground)] hover:text-[var(--foreground)]">
          Voir l&apos;agenda →
        </Link>
      </div>

      <div className="rounded-xl border border-[var(--border)] bg-[var(--card)] p-4 space-y-3">
        {upcoming.length > 0 ? (
          <ul className="space-y-2">
            {upcoming.map((e, i) => (
              <li key={i} className="flex items-center gap-3 text-sm">
                <span className="h-2.5 w-2.5 rounded-full shrink-0" style={{ backgroundColor: couleurFor(e) }} />
                <span className="tabular-nums text-[var(--muted-foreground)] w-12 shrink-0">{formatHeure(e.debut)}</span>
                <span className="truncate">{e.titre}</span>
                {e.lieu && <span className="text-xs text-[var(--muted-foreground)] truncate">· {e.lieu}</span>}
              </li>
            ))}
          </ul>
        ) : (
          <p className="text-sm text-[var(--muted-foreground)]">Aucun événement à venir aujourd&apos;hui.</p>
        )}

        {urgentes > 0 && (
          <div className="pt-1 text-xs">
            <span className="rounded-md bg-[color-mix(in_srgb,var(--destructive)_12%,transparent)] text-[var(--destructive)] px-2 py-0.5 font-medium">
              ⚠ {urgentes} tâche{urgentes > 1 ? "s" : ""} urgente{urgentes > 1 ? "s" : ""}
            </span>
          </div>
        )}
      </div>
    </section>
  );
}
