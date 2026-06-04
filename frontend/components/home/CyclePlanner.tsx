"use client";

/**
 * Carte « Nouveau cycle » + aperçu du planning automatique.
 *
 * Apparaît sur le dashboard les jours de cuisine (jeu/dim). Au clic : appelle
 * /agenda/plan/preview (lecture seule), montre le planning proposé par jour +
 * les blocs non placés, puis « Valider » écrit via /agenda/plan/commit.
 * Le push Google Calendar est différé (bouton désactivé).
 * Voir docs/superpowers/specs/2026-06-04-agenda-auto-planner-design.md
 */

import { useEffect, useRef, useState } from "react";
import Link from "next/link";
import { toast } from "sonner";
import { CalendarPlus, TriangleAlert } from "lucide-react";
import {
  planPreview,
  planCommit,
  planPush,
  gcalStatus,
  PLAN_TYPE_COLOR,
  type PlanProposition,
  type PlanBloc,
} from "@/lib/agenda";

const COOKING_DAYS = [0, 4]; // dimanche=0, jeudi=4 (Date.getDay)

function hhmm(iso: string): string {
  return iso.slice(11, 16);
}

function dayLabel(date: string): string {
  const d = new Date(date + "T00:00:00");
  return d.toLocaleDateString("fr-CA", { weekday: "long", day: "numeric", month: "long" });
}

function groupByDay(blocs: PlanBloc[]): { date: string; items: PlanBloc[] }[] {
  const map = new Map<string, PlanBloc[]>();
  for (const b of blocs) {
    if (!map.has(b.date)) map.set(b.date, []);
    map.get(b.date)!.push(b);
  }
  return [...map.entries()].map(([date, items]) => ({ date, items }));
}

export function CyclePlanner() {
  const [cookingDay, setCookingDay] = useState(false);
  const [open, setOpen] = useState(false);
  const [loading, setLoading] = useState(false);
  const [committing, setCommitting] = useState(false);
  const [committed, setCommitted] = useState(false);
  const [plan, setPlan] = useState<PlanProposition | null>(null);
  const [gcalOk, setGcalOk] = useState(false);
  const [pushing, setPushing] = useState(false);
  const dialogRef = useRef<HTMLDivElement>(null);
  const restoreRef = useRef<HTMLElement | null>(null);

  useEffect(() => {
    setCookingDay(COOKING_DAYS.includes(new Date().getDay()));
    gcalStatus()
      .then((s) => setGcalOk(s.configured))
      .catch(() => setGcalOk(false));
  }, []);

  // Gestion focus + fermeture quand le modal est ouvert (sans onClick sur div).
  useEffect(() => {
    if (!open) return;
    restoreRef.current = document.activeElement as HTMLElement | null;
    dialogRef.current?.focus();
    function onKey(e: KeyboardEvent) {
      if (e.key === "Escape") setOpen(false);
    }
    function onPointer(e: MouseEvent) {
      if (dialogRef.current && !dialogRef.current.contains(e.target as Node)) setOpen(false);
    }
    document.addEventListener("keydown", onKey);
    document.addEventListener("mousedown", onPointer);
    return () => {
      document.removeEventListener("keydown", onKey);
      document.removeEventListener("mousedown", onPointer);
      restoreRef.current?.focus();
    };
  }, [open]);

  async function openPreview() {
    setLoading(true);
    try {
      const p = await planPreview();
      setPlan(p);
      setOpen(true);
    } catch {
      toast.error("Impossible de calculer le planning (backend indisponible ?).");
    } finally {
      setLoading(false);
    }
  }

  async function validate() {
    setCommitting(true);
    try {
      const res = await planCommit();
      toast.success(`${res.created} blocs ajoutés à l'agenda.`);
      setCommitted(true);
      setOpen(false);
    } catch {
      toast.error("Échec de l'écriture dans l'agenda. Réessaie.");
    } finally {
      setCommitting(false);
    }
  }

  async function push() {
    setPushing(true);
    try {
      const res = await planPush();
      toast.success(`${res.pushed} blocs envoyés sur Google Agenda.`);
    } catch {
      toast.error("Échec de l'envoi vers Google Agenda.");
    } finally {
      setPushing(false);
    }
  }

  if (!cookingDay) return null;

  return (
    <section className="mt-8 animate-fade-in">
      <div className="flex flex-wrap items-center justify-between gap-3 rounded-xl border border-[color-mix(in_srgb,var(--ring)_30%,var(--border))] bg-[var(--card)] px-4 py-3.5">
        <div className="flex items-start gap-3">
          <span className="mt-0.5 flex h-8 w-8 shrink-0 items-center justify-center rounded-md bg-[color-mix(in_srgb,var(--ring)_12%,transparent)]">
            <CalendarPlus className="h-4 w-4 text-[var(--nav-active-fg)]" aria-hidden="true" />
          </span>
          <div>
            <h2 className="font-display text-base font-semibold">
              {committed ? "Cycle planifié" : "Nouveau cycle de cuisine"}
            </h2>
            <p className="text-sm text-[var(--muted-foreground)]">
              {committed
                ? "Tes prochains jours sont remplis dans l'agenda."
                : "Planifie sport, repas, révision et cuisine jusqu'au prochain jour de cuisine."}
            </p>
          </div>
        </div>
        {committed ? (
          <div className="flex shrink-0 items-center gap-2">
            {gcalOk && (
              <button
                type="button"
                onClick={() => void push()}
                disabled={pushing}
                className="rounded-md bg-[var(--primary)] px-3 py-1.5 text-sm font-medium text-[var(--primary-foreground)] transition-opacity hover:opacity-90 disabled:opacity-60"
              >
                {pushing ? "Envoi…" : "Envoyer sur Google Agenda"}
              </button>
            )}
            <Link
              href="/agenda"
              className="rounded-md border border-[var(--border)] px-3 py-1.5 text-sm font-medium transition-colors hover:bg-[var(--muted)]"
            >
              Voir l'agenda
            </Link>
          </div>
        ) : (
          <button
            type="button"
            onClick={() => void openPreview()}
            disabled={loading}
            className="shrink-0 rounded-md bg-[var(--primary)] px-3 py-1.5 text-sm font-medium text-[var(--primary-foreground)] transition-opacity hover:opacity-90 disabled:opacity-60"
          >
            {loading ? "Calcul…" : "Voir le planning"}
          </button>
        )}
      </div>

      {open && plan && (
        <div className="fixed inset-0 z-50 flex items-start justify-center bg-black/40 p-4 pt-[8vh]">
          <div
            ref={dialogRef}
            role="dialog"
            aria-modal="true"
            aria-labelledby="plan-title"
            tabIndex={-1}
            className="flex max-h-[80vh] w-full max-w-lg flex-col overflow-hidden rounded-xl border border-[var(--border)] bg-[var(--card)] shadow-[var(--shadow-lg)] focus:outline-none"
          >
            <div className="flex items-center justify-between border-b border-[var(--border)] px-4 py-3">
              <h2 id="plan-title" className="font-display text-base font-semibold">
                Planning proposé
              </h2>
              <span className="text-xs text-[var(--muted-foreground)]">
                {dayLabel(plan.fenetre.debut)} → {dayLabel(plan.fenetre.fin)}
              </span>
            </div>

            <div className="flex-1 overflow-y-auto px-4 py-3">
              {plan.non_places.length > 0 && (
                <div className="mb-3 flex items-start gap-2 rounded-md bg-[var(--warning-muted)] px-3 py-2 text-xs text-[var(--warning-foreground)]">
                  <TriangleAlert className="mt-0.5 h-3.5 w-3.5 shrink-0" aria-hidden="true" />
                  <div>
                    <p className="font-medium">Non placé (agenda trop chargé) :</p>
                    <ul className="list-disc pl-4">
                      {plan.non_places.map((m) => (
                        <li key={m}>{m}</li>
                      ))}
                    </ul>
                  </div>
                </div>
              )}

              {groupByDay(plan.blocs).map(({ date, items }) => (
                <div key={date} className="mb-3 last:mb-0">
                  <h3 className="mb-1 text-xs font-medium uppercase tracking-wider text-[var(--muted-foreground)] first-letter:uppercase">
                    {dayLabel(date)}
                  </h3>
                  <ul className="space-y-1">
                    {items.map((b, i) => (
                      <li key={`${b.debut}-${i}`} className="flex items-center gap-2.5 text-sm">
                        <span
                          className="h-2 w-2 shrink-0 rounded-full"
                          style={{ backgroundColor: PLAN_TYPE_COLOR[b.type] ?? "var(--muted-foreground)" }}
                          aria-hidden="true"
                        />
                        <span className="w-24 shrink-0 tabular-nums text-[var(--muted-foreground)]">
                          {hhmm(b.debut)}–{hhmm(b.fin)}
                        </span>
                        <span className="min-w-0 flex-1 truncate">{b.titre}</span>
                      </li>
                    ))}
                  </ul>
                </div>
              ))}
            </div>

            <div className="flex items-center justify-between gap-2 border-t border-[var(--border)] px-4 py-3">
              <span className="text-xs text-[var(--muted-foreground)]">
                {gcalOk
                  ? "Après validation : envoi possible vers Google Agenda."
                  : "Écrit dans l'agenda local."}
              </span>
              <button
                type="button"
                onClick={() => void validate()}
                disabled={committing}
                className="rounded-md bg-[var(--primary)] px-4 py-1.5 text-sm font-medium text-[var(--primary-foreground)] transition-opacity hover:opacity-90 disabled:opacity-60"
              >
                {committing ? "Écriture…" : "Valider"}
              </button>
            </div>
          </div>
        </div>
      )}
    </section>
  );
}
