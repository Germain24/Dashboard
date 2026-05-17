"use client";

import { useState } from "react";
import {
  type NutritionGoal,
  type PlanResponse,
  MACRO_KEYS,
  MACRO_UNITS,
  INTENSITY_LABELS,
} from "@/lib/sante";
import { MacroBar } from "./MacroBar";

type Props = {
  plan: PlanResponse | null;
  goal: NutritionGoal | null;
  onGenerate: (opts?: { intensity?: string; budget_max_daily?: number; force?: boolean }) => Promise<PlanResponse>;
  onOpenMicros: () => void;
};

export function JourTab({ plan, goal, onGenerate, onOpenMicros }: Props) {
  const [intensity, setIntensity] = useState<string>(plan?.intensite ?? "medium");
  const [budget, setBudget] = useState<string>(
    plan?.budget_max_daily !== undefined ? String(plan.budget_max_daily) : "18",
  );
  const [generating, setGenerating] = useState(false);
  const [err, setErr] = useState<string | null>(null);

  const handleGenerate = async (force = false) => {
    setGenerating(true);
    setErr(null);
    try {
      await onGenerate({
        intensity,
        budget_max_daily: budget ? parseFloat(budget) : undefined,
        force,
      });
    } catch (e: any) {
      setErr(e?.message ?? "Erreur de génération");
    } finally {
      setGenerating(false);
    }
  };

  if (!plan) {
    return (
      <div className="space-y-4">
        <div className="rounded border border-[var(--border)] p-4 bg-[var(--muted)]/50">
          <p className="text-sm">Aucun plan pour aujourd'hui. Génère-en un :</p>
          <div className="mt-3 flex flex-wrap items-end gap-3">
            <label className="text-xs flex flex-col">
              Intensité
              <select
                value={intensity}
                onChange={(e) => setIntensity(e.target.value)}
                className="mt-1 rounded border border-[var(--border)] bg-transparent px-2 py-1 text-sm"
              >
                {Object.entries(INTENSITY_LABELS).map(([k, label]) => (
                  <option key={k} value={k}>{label}</option>
                ))}
              </select>
            </label>
            <label className="text-xs flex flex-col">
              Budget (CAD/j)
              <input
                type="number"
                step="0.5"
                value={budget}
                onChange={(e) => setBudget(e.target.value)}
                className="mt-1 w-24 rounded border border-[var(--border)] bg-transparent px-2 py-1 text-sm"
              />
            </label>
            <button
              onClick={() => handleGenerate(false)}
              disabled={generating}
              className="rounded bg-[var(--primary)] text-[var(--primary-foreground)] px-3 py-1.5 text-sm font-medium disabled:opacity-50"
            >
              {generating ? "…" : "✨ Générer un plan"}
            </button>
          </div>
          {err && <div className="mt-2 text-sm text-red-500">⚠ {err}</div>}
        </div>
      </div>
    );
  }

  const totals = plan.totals ?? {};
  const targets = plan.targets ?? {};

  return (
    <div className="space-y-4">
      {/* Bandeau état */}
      <div className="rounded border border-[var(--border)] p-3 flex flex-wrap items-center gap-3 text-sm">
        <span className="font-medium">{new Date(plan.date).toLocaleDateString("fr-CA")}</span>
        <span className="text-[var(--muted-foreground)]">
          Poids : {plan.poids_used.toFixed(1)} kg
        </span>
        <span className="text-[var(--muted-foreground)]">
          Intensité : <strong>{INTENSITY_LABELS[plan.intensite] ?? plan.intensite}</strong>
          {plan.intensity_was_default && (
            <span className="ml-1 text-xs opacity-70">(défaut)</span>
          )}
        </span>
        <span className="text-[var(--muted-foreground)]">
          Budget : {plan.budget_max_daily.toFixed(2)} CAD
        </span>
        <div className="ml-auto flex gap-2">
          <select
            value={intensity}
            onChange={(e) => setIntensity(e.target.value)}
            className="rounded border border-[var(--border)] bg-transparent px-2 py-1 text-xs"
          >
            {Object.entries(INTENSITY_LABELS).map(([k, label]) => (
              <option key={k} value={k}>{label}</option>
            ))}
          </select>
          <input
            type="number"
            step="0.5"
            value={budget}
            onChange={(e) => setBudget(e.target.value)}
            className="w-20 rounded border border-[var(--border)] bg-transparent px-2 py-1 text-xs"
            title="Budget CAD/j"
          />
          <button
            onClick={() => handleGenerate(true)}
            disabled={generating}
            className="rounded bg-[var(--primary)] text-[var(--primary-foreground)] px-2 py-1 text-xs disabled:opacity-50"
          >
            {generating ? "…" : "🔄 Re-générer"}
          </button>
        </div>
      </div>

      {plan.warning && (
        <div className="rounded border border-amber-500/40 bg-amber-500/10 px-3 py-2 text-sm text-amber-700 dark:text-amber-300">
          ⚠ {plan.warning}
        </div>
      )}

      {/* Barres macros */}
      <div className="grid gap-2">
        {MACRO_KEYS.map((k) => (
          <MacroBar
            key={k}
            label={k}
            unit={MACRO_UNITS[k] ?? ""}
            current={totals[k] ?? 0}
            target={targets[k] ?? 0}
          />
        ))}
        <MacroBar
          label="Prix"
          unit="CAD"
          current={totals["Prix"] ?? sumPrix(plan)}
          target={plan.budget_max_daily}
          isMax
        />
      </div>

      <div className="flex flex-wrap gap-2">
        <button
          onClick={onOpenMicros}
          className="rounded border border-[var(--border)] px-3 py-1.5 text-sm hover:bg-[var(--accent)]"
        >
          🔬 Voir tous les micronutriments
        </button>
      </div>

      {/* Tableau du plan */}
      <div className="rounded border border-[var(--border)] overflow-hidden">
        <table className="w-full text-sm">
          <thead className="bg-[var(--muted)]/50 text-[var(--muted-foreground)] text-xs uppercase">
            <tr>
              <th className="text-left px-3 py-2">Aliment</th>
              <th className="text-right px-3 py-2">Quantité</th>
              <th className="text-right px-3 py-2">kcal</th>
              <th className="text-right px-3 py-2">Prot.</th>
              <th className="text-right px-3 py-2">Lip.</th>
              <th className="text-right px-3 py-2">Gluc.</th>
              <th className="text-right px-3 py-2">CAD</th>
            </tr>
          </thead>
          <tbody>
            {plan.items.length === 0 && (
              <tr><td colSpan={7} className="px-3 py-4 text-center text-[var(--muted-foreground)]">
                Aucun item — clique sur Re-générer.
              </td></tr>
            )}
            {plan.items.map((it) => (
              <tr key={it.aliment} className="border-t border-[var(--border)]">
                <td className="px-3 py-1.5">{it.aliment}</td>
                <td className="px-3 py-1.5 text-right">{it.quantite_str}</td>
                <td className="px-3 py-1.5 text-right">{it.calories.toFixed(0)}</td>
                <td className="px-3 py-1.5 text-right">{it.proteines.toFixed(1)}</td>
                <td className="px-3 py-1.5 text-right">{it.lipides.toFixed(1)}</td>
                <td className="px-3 py-1.5 text-right">{it.glucides.toFixed(1)}</td>
                <td className="px-3 py-1.5 text-right">{it.prix.toFixed(2)}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>

      {err && <div className="text-sm text-red-500">⚠ {err}</div>}
    </div>
  );
}

function sumPrix(plan: PlanResponse): number {
  return plan.items.reduce((s, i) => s + i.prix, 0);
}
