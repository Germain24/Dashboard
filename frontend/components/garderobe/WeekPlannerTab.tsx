"use client";

/** Planificateur de tenues sur la semaine, lié à l'agenda (#79). */

import { useState } from "react";
import type { Vetement, WeekPlan, PlannerDay } from "@/lib/garderobe";
import { emojiForCategorie } from "@/lib/garderobe";
import { useSetPlannerDay, useWeekPlanner } from "@/lib/queries/garderobe";

const PLAN_SLOTS = ["Manteau", "Haut", "Pantalon", "Chaussures"] as const;
const SLOT_CATS: Record<string, string[]> = {
  Manteau: ["Manteau", "Veste"],
  Haut: ["Haut", "T-shirt", "Chemise", "Pull", "Shirt"],
  Pantalon: ["Pantalon", "Short", "Jean"],
  Chaussures: ["Chaussures", "Bottes", "Sneakers"],
};
const JOURS = ["Lun", "Mar", "Mer", "Jeu", "Ven", "Sam", "Dim"];

export function WeekPlannerTab({ wardrobe }: { wardrobe: Vetement[] }) {
  const [start, setStart] = useState<string | undefined>(undefined);
  const [savingDate, setSavingDate] = useState<string | null>(null);

  const planQ = useWeekPlanner(start);
  const plan: WeekPlan | null = planQ.data ?? null;
  const setDayMutation = useSetPlannerDay();

  const shiftWeek = (deltaDays: number) => {
    const base = plan ? new Date(plan.start) : new Date();
    base.setDate(base.getDate() + deltaDays);
    setStart(base.toISOString().slice(0, 10));
  };

  const setSlot = (day: PlannerDay, slot: string, vetId: string) => {
    const tenue: Record<string, string | null> = {};
    for (const s of PLAN_SLOTS) tenue[s] = day.tenue[s]?.id ?? null;
    tenue[slot] = vetId || null;
    setSavingDate(day.date);
    setDayMutation.mutate({ date: day.date, tenue }, {
      onSettled: () => setSavingDate(null),
    });
  };

  if (!plan) return <p className="text-sm text-[var(--muted-foreground)]">Chargement du planning…</p>;

  return (
    <div className="space-y-4 animate-fade-in-up">
      <div className="flex items-center justify-between">
        <button onClick={() => shiftWeek(-7)} className="rounded border border-[var(--border)] px-2 py-1 text-sm hover:bg-[var(--muted)]">← Semaine préc.</button>
        <span className="text-sm font-medium">
          Semaine du {new Date(plan.start).toLocaleDateString("fr-CA")}
        </span>
        <button onClick={() => shiftWeek(7)} className="rounded border border-[var(--border)] px-2 py-1 text-sm hover:bg-[var(--muted)]">Semaine suiv. →</button>
      </div>

      <div className="grid grid-cols-1 md:grid-cols-2 xl:grid-cols-4 gap-3">
        {plan.days.map((day) => (
          <div key={day.date} className="rounded-xl border border-[var(--border)] bg-[var(--card)] p-3 space-y-2">
            <div className="flex items-baseline justify-between">
              <span className="text-sm font-semibold">
                {JOURS[day.weekday]} {new Date(day.date).getDate()}
              </span>
              {savingDate === day.date && <span className="text-[10px] text-[var(--muted-foreground)]">…</span>}
            </div>

            {day.events.length > 0 && (
              <div className="space-y-0.5">
                {day.events.slice(0, 3).map((e, i) => (
                  <div key={i} className="text-[11px] text-[var(--muted-foreground)] truncate" title={e.titre}>
                    📅 {e.heure} {e.titre}
                  </div>
                ))}
              </div>
            )}

            <div className="space-y-1.5">
              {PLAN_SLOTS.map((slot) => {
                const candidates = wardrobe.filter((v) => (SLOT_CATS[slot] || []).includes(v.categorie));
                const current = day.tenue[slot];
                return (
                  <label key={slot} className="flex items-center gap-1.5 text-xs">
                    <span className="w-6 text-center" title={slot}>{emojiForCategorie(SLOT_CATS[slot][0])}</span>
                    <select
                      value={current?.id ?? ""}
                      onChange={(e) => void setSlot(day, slot, e.target.value)}
                      className="flex-1 rounded border border-[var(--border)] bg-transparent px-1.5 py-1 text-xs"
                    >
                      <option value="">—</option>
                      {candidates.map((v) => (
                        <option key={v.id} value={v.id}>{v.nom}</option>
                      ))}
                    </select>
                  </label>
                );
              })}
            </div>
          </div>
        ))}
      </div>
    </div>
  );
}
