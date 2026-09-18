"use client";

import { useState } from "react";
import { type NutritionGoal, type NutritionGoalUpdate } from "@/lib/sante";

type Props = {
  goal: NutritionGoal;
  onSave: (p: NutritionGoalUpdate) => Promise<void>;
};

const DAY_LABELS = ["Lun", "Mar", "Mer", "Jeu", "Ven", "Sam", "Dim"];

export function GoalTab({ goal, onSave }: Props) {
  const [poidsCible, setPoidsCible] = useState(goal.poids_cible?.toString() ?? "");
  const [bfTarget, setBfTarget] = useState(goal.body_fat_target_pct?.toString() ?? "");
  const [dateCible, setDateCible] = useState(goal.date_cible ?? "");
  const [type, setType] = useState(goal.type);
  const [surplusSport, setSurplusSport] = useState(goal.surplus_kcal_sport.toString());
  const [restFactor, setRestFactor] = useState(goal.rest_factor.toString());
  const [sportDays, setSportDays] = useState<number[]>(goal.sport_days);
  const [noteVal, setNoteVal] = useState(goal.note ?? "");
  const [saving, setSaving] = useState(false);
  const [msg, setMsg] = useState<string | null>(null);

  const toggleDay = (d: number) => {
    setSportDays((prev) => prev.includes(d) ? prev.filter((x) => x !== d) : [...prev, d].sort());
  };

  const handleSave = async () => {
    setSaving(true);
    setMsg(null);
    try {
      await onSave({
        poids_cible: poidsCible ? parseFloat(poidsCible) : null,
        body_fat_target_pct: bfTarget ? parseFloat(bfTarget) : null,
        date_cible: dateCible || null,
        type,
        surplus_kcal_sport: parseFloat(surplusSport),
        rest_factor: parseFloat(restFactor),
        sport_days: sportDays,
        note: noteVal || null,
      });
      setMsg("Enregistré ✔");
    } catch (e: any) {
      setMsg(`⚠ ${e?.message ?? "Erreur"}`);
    } finally {
      setSaving(false);
    }
  };

  return (
    <div className="space-y-4">
      <div className="rounded border border-[var(--border)] p-4 space-y-3">
        <h2 className="font-medium">Objectif & paramètres nutrition</h2>

        <div className="grid sm:grid-cols-3 gap-3">
          <label className="text-xs flex flex-col">
            Poids cible (kg)
            <input
              type="number"
              step="0.1"
              value={poidsCible}
              onChange={(e) => setPoidsCible(e.target.value)}
              className="mt-1 rounded border border-[var(--border)] bg-transparent px-2 py-1 text-sm"
              placeholder="ex. 71"
            />
          </label>
          <label className="text-xs flex flex-col">
            Masse grasse cible (%)
            <input
              type="number"
              step="0.5"
              value={bfTarget}
              onChange={(e) => setBfTarget(e.target.value)}
              className="mt-1 rounded border border-[var(--border)] bg-transparent px-2 py-1 text-sm"
              placeholder="ex. 10"
            />
          </label>
          <label className="text-xs flex flex-col">
            Date cible
            <input
              type="date"
              value={dateCible}
              onChange={(e) => setDateCible(e.target.value)}
              className="mt-1 rounded border border-[var(--border)] bg-transparent px-2 py-1 text-sm"
            />
          </label>
          <label className="text-xs flex flex-col">
            Type
            <select
              value={type}
              onChange={(e) => setType(e.target.value)}
              className="mt-1 rounded border border-[var(--border)] bg-transparent px-2 py-1 text-sm"
            >
              <option value="bulk">Bulk (prise)</option>
              <option value="maintain">Maintien</option>
              <option value="cut">Cut (sèche)</option>
            </select>
          </label>
          <label className="text-xs flex flex-col">
            Surplus kcal jour sport
            <input
              type="number"
              step="50"
              value={surplusSport}
              onChange={(e) => setSurplusSport(e.target.value)}
              className="mt-1 rounded border border-[var(--border)] bg-transparent px-2 py-1 text-sm"
            />
          </label>
          <label className="text-xs flex flex-col">
            Facteur jour repos (× maintenance)
            <input
              type="number"
              step="0.05"
              value={restFactor}
              onChange={(e) => setRestFactor(e.target.value)}
              className="mt-1 rounded border border-[var(--border)] bg-transparent px-2 py-1 text-sm"
            />
          </label>
        </div>

        <div>
          <div className="text-xs mb-1">Jours d'entraînement</div>
          <div className="flex gap-1.5">
            {DAY_LABELS.map((label, idx) => {
              const on = sportDays.includes(idx);
              return (
                <button
                  key={idx}
                  type="button"
                  onClick={() => toggleDay(idx)}
                  className={`px-2.5 py-1 rounded text-xs border ${
                    on
                      ? "border-[var(--ring)] bg-[var(--ring)]/10 text-[var(--ring)]"
                      : "border-[var(--border)] text-[var(--muted-foreground)]"
                  }`}
                >
                  {label}
                </button>
              );
            })}
          </div>
        </div>

        <label className="text-xs flex flex-col">
          Note
          <textarea
            value={noteVal}
            onChange={(e) => setNoteVal(e.target.value)}
            rows={2}
            className="mt-1 rounded border border-[var(--border)] bg-transparent px-2 py-1 text-sm"
            placeholder="contexte de l'objectif, motivation, contraintes…"
          />
        </label>

        <div className="flex items-center gap-3">
          <button
            onClick={handleSave}
            disabled={saving}
            className="rounded bg-[var(--primary)] text-[var(--primary-foreground)] px-3 py-1.5 text-sm font-medium disabled:opacity-50"
          >
            {saving ? "…" : "💾 Enregistrer"}
          </button>
          {msg && <span className="text-xs">{msg}</span>}
        </div>
      </div>
    </div>
  );
}
