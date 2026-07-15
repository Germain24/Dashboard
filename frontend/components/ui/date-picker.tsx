"use client";

import * as React from "react";
import { CalendarIcon, ChevronLeft, ChevronRight } from "lucide-react";
import { cn } from "@/lib/utils";

/** Calendrier déroulant : clique sur le champ -> une grille de mois s'ouvre,
 *  clique sur un jour -> sélectionné et le panneau se ferme. Remplace
 *  `<input type="date">` dont le picker natif varie trop d'un navigateur à
 *  l'autre (parfois juste une petite icône peu visible). */

const JOURS = ["L", "M", "M", "J", "V", "S", "D"];
const MOIS = [
  "Janvier", "Février", "Mars", "Avril", "Mai", "Juin",
  "Juillet", "Août", "Septembre", "Octobre", "Novembre", "Décembre",
];

function parseDate(value: string): Date | null {
  if (!value) return null;
  const [y, m, d] = value.split("-").map(Number);
  if (!y || !m || !d) return null;
  return new Date(y, m - 1, d);
}

function toValue(d: Date): string {
  const y = d.getFullYear();
  const m = String(d.getMonth() + 1).padStart(2, "0");
  const day = String(d.getDate()).padStart(2, "0");
  return `${y}-${m}-${day}`;
}

function formatAffichage(value: string): string {
  const d = parseDate(value);
  if (!d) return "";
  return new Intl.DateTimeFormat("fr-FR", { day: "numeric", month: "short", year: "numeric" }).format(d);
}

// Grille lundi -> dimanche, avec des cases vides avant le 1er du mois.
function joursDuMois(anneeMois: Date): (Date | null)[] {
  const annee = anneeMois.getFullYear();
  const mois = anneeMois.getMonth();
  const premier = new Date(annee, mois, 1);
  const nbJours = new Date(annee, mois + 1, 0).getDate();
  const decalage = (premier.getDay() + 6) % 7; // 0 = lundi
  const cases: (Date | null)[] = Array(decalage).fill(null);
  for (let j = 1; j <= nbJours; j++) cases.push(new Date(annee, mois, j));
  return cases;
}

export function DatePicker({
  value, onChange, min, label, id,
}: {
  value: string;
  onChange: (v: string) => void;
  min?: string;
  label?: string;
  id?: string;
}) {
  const [open, setOpen] = React.useState(false);
  const selected = parseDate(value);
  const minDate = min ? parseDate(min) : null;
  const [moisAffiche, setMoisAffiche] = React.useState(() => selected ?? minDate ?? new Date());
  const ref = React.useRef<HTMLDivElement>(null);

  React.useEffect(() => {
    if (!open) return;
    const onPointerDown = (e: MouseEvent) => {
      if (ref.current && !ref.current.contains(e.target as Node)) setOpen(false);
    };
    const onKeyDown = (e: KeyboardEvent) => {
      if (e.key === "Escape") setOpen(false);
    };
    document.addEventListener("mousedown", onPointerDown);
    document.addEventListener("keydown", onKeyDown);
    return () => {
      document.removeEventListener("mousedown", onPointerDown);
      document.removeEventListener("keydown", onKeyDown);
    };
  }, [open]);

  const estDesactive = (d: Date) => (minDate ? d < minDate : false);
  const estSelectionne = (d: Date) => selected !== null && toValue(d) === toValue(selected);

  return (
    <div className="relative" ref={ref}>
      {label && (
        <label htmlFor={id} className="text-sm">
          {label}
        </label>
      )}
      <button
        type="button"
        id={id}
        onClick={() => setOpen((o) => !o)}
        className={cn(
          "mt-1 flex w-full items-center justify-between gap-2 rounded-lg border border-[var(--border)]",
          "bg-[var(--background)] p-1.5 text-left text-sm",
        )}
      >
        <span className={value ? "" : "text-[var(--muted-foreground)]"}>
          {value ? formatAffichage(value) : "Choisir une date"}
        </span>
        <CalendarIcon className="h-4 w-4 shrink-0 text-[var(--muted-foreground)]" />
      </button>

      {open && (
        <div className="absolute z-20 mt-1 w-64 rounded-lg border border-[var(--border)] bg-[var(--card)] p-2 shadow-lg">
          <div className="mb-2 flex items-center justify-between">
            <button
              type="button"
              onClick={() => setMoisAffiche((m) => new Date(m.getFullYear(), m.getMonth() - 1, 1))}
              className="rounded p-1 hover:bg-[var(--muted)]"
              aria-label="Mois précédent"
            >
              <ChevronLeft className="h-4 w-4" />
            </button>
            <span className="text-sm font-medium">
              {MOIS[moisAffiche.getMonth()]} {moisAffiche.getFullYear()}
            </span>
            <button
              type="button"
              onClick={() => setMoisAffiche((m) => new Date(m.getFullYear(), m.getMonth() + 1, 1))}
              className="rounded p-1 hover:bg-[var(--muted)]"
              aria-label="Mois suivant"
            >
              <ChevronRight className="h-4 w-4" />
            </button>
          </div>
          <div className="grid grid-cols-7 gap-0.5 text-center text-xs text-[var(--muted-foreground)]">
            {JOURS.map((j, i) => (
              <span key={i}>{j}</span>
            ))}
          </div>
          <div className="grid grid-cols-7 gap-0.5">
            {joursDuMois(moisAffiche).map((d, i) => (
              <button
                type="button"
                key={i}
                disabled={!d || estDesactive(d)}
                onClick={() => {
                  if (!d) return;
                  onChange(toValue(d));
                  setOpen(false);
                }}
                className={cn(
                  "aspect-square rounded text-sm",
                  !d && "invisible",
                  d && !estDesactive(d) && "hover:bg-[var(--muted)]",
                  d && estDesactive(d) && "cursor-not-allowed text-[var(--muted-foreground)] opacity-40",
                  d && estSelectionne(d) && "bg-[var(--primary)] text-[var(--primary-foreground)] hover:bg-[var(--primary)]",
                )}
              >
                {d?.getDate()}
              </button>
            ))}
          </div>
        </div>
      )}
    </div>
  );
}
