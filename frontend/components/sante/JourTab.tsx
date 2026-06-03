"use client";

import { useState } from "react";
import {
  type NutritionGoal,
  type PlanResponse,
  MACRO_KEYS,
  MACRO_UNITS,
  INTENSITY_LABELS,
  santeApi,
} from "@/lib/sante";
import { MacroBar } from "./MacroBar";
import { ConsoDrawer } from "./ConsoDrawer";
import { WaterWidget } from "./WaterWidget";
import { SleepWidget } from "./SleepWidget";
import { NutritionQualityWidget } from "./NutritionQualityWidget";
import { WorkoutBurnWidget } from "./WorkoutBurnWidget";
import { Button } from "@/components/ui/button";

type Props = {
  plan: PlanResponse | null;
  goal: NutritionGoal | null;
  onGenerate: (opts?: { intensity?: string; budget_max_daily?: number; force?: boolean }) => Promise<PlanResponse>;
  onPlanUpdated?: (p: PlanResponse) => void;
  onOpenMicros: () => void;
};

export function JourTab({ plan, goal, onGenerate, onPlanUpdated, onOpenMicros }: Props) {
  const [intensity, setIntensity] = useState<string>(plan?.intensite ?? "medium");
  const [budget, setBudget] = useState<string>(
    plan?.budget_max_daily !== undefined ? String(plan.budget_max_daily) : "18",
  );
  const [generating, setGenerating] = useState(false);
  const [savingConso, setSavingConso] = useState(false);
  const [consoDrawerOpen, setConsoDrawerOpen] = useState(false);
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

  // "J'ai suivi le plan" → consumed_grams = quantites du plan
  const handleConsommeLePlan = async () => {
    if (!plan) return;
    setSavingConso(true);
    setErr(null);
    try {
      const consumed_grams: Record<string, number> = {};
      for (const it of plan.items) consumed_grams[it.aliment] = it.quantite_g;
      const updated = await santeApi.patchPlan(plan.date, { consumed_grams });
      onPlanUpdated?.(updated);
    } catch (e: any) {
      setErr(e?.message ?? "Erreur enregistrement conso");
    } finally {
      setSavingConso(false);
    }
  };

  // Edition manuelle (drawer)
  const handleSaveConso = async (grams: Record<string, number>) => {
    if (!plan) return;
    const updated = await santeApi.patchPlan(plan.date, { consumed_grams: grams });
    onPlanUpdated?.(updated);
  };

  if (!plan) {
    return (
      <div className="space-y-4 animate-fade-in-up">
        <div className="rounded-xl border border-[var(--border)] p-4 bg-[var(--card)] card-hover">
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
            <Button
              onClick={() => handleGenerate(false)}
              disabled={generating}
              size="sm"
            >
              {generating ? "…" : "✨ Générer un plan"}
            </Button>
          </div>
          {err && <div className="mt-2 text-sm text-[var(--destructive)]">⚠ {err}</div>}
        </div>
      </div>
    );
  }

  const totals = plan.totals ?? {};
  const targets = plan.targets ?? {};
  const consumed = plan.consumed ?? null;
  const consoEnregistree = consumed !== null && Object.keys(consumed).some((k) => k.endsWith("_g"));

  return (
    <div className="space-y-4 animate-fade-in-up">
      <div className="grid gap-3 sm:grid-cols-2">
        <WaterWidget />
        <SleepWidget />
      </div>
      <NutritionQualityWidget />
      <WorkoutBurnWidget consumedCalories={consumed?.["Calories"] as number | undefined} />
      {/* Bandeau état */}
      <div className="rounded-xl border border-[var(--border)] bg-[var(--card)] p-3 flex flex-wrap items-center gap-3 text-sm card-hover">
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
        <span
          className={`text-xs rounded px-2 py-0.5 ${
            consoEnregistree
              ? "bg-[var(--success-muted)] text-[var(--success)]"
              : "bg-[var(--warning-muted)] text-[var(--warning)]"
          }`}
          title={
            consoEnregistree
              ? "Ta conso d'aujourd'hui est enregistrée — la compensation J+1 fonctionnera."
              : "Conso non enregistrée — la compensation J+1 ne marchera pas tant que tu n'as pas validé."
          }
        >
          {consoEnregistree ? "✓ Conso enregistrée" : "⚠ Conso non enregistrée"}
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
          <Button
            onClick={() => handleGenerate(true)}
            disabled={generating}
            variant="secondary"
            size="sm"
          >
            {generating ? "…" : "🔄 Re-générer"}
          </Button>
        </div>
      </div>

      {plan.warning && (
        <div className="rounded border border-[var(--warning)]/40 bg-[var(--warning-muted)] px-3 py-2 text-sm text-[var(--warning)]">
          ⚠ {plan.warning}
        </div>
      )}

      {/* Barres macros */}
      <div className="grid gap-2 stagger">
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

      {/* Actions principales */}
      <div className="flex flex-wrap gap-2">
        <Button
          onClick={handleConsommeLePlan}
          disabled={savingConso}
          variant="success"
          size="sm"
          title="Copie le plan d'aujourd'hui dans consumed pour activer la compensation J+1"
        >
          {savingConso ? "…" : consoEnregistree ? "✓ J'ai suivi le plan (re-enregistrer)" : "✓ J'ai suivi le plan"}
        </Button>
        <Button
          onClick={() => setConsoDrawerOpen(true)}
          variant="secondary"
          size="sm"
        >
          ✏️ Ajuster ce que j'ai mangé
        </Button>
        <Button
          onClick={onOpenMicros}
          variant="secondary"
          size="sm"
        >
          🔬 Voir tous les micronutriments
        </Button>
      </div>

      {/* Tableau du plan */}
      <div className="rounded-xl border border-[var(--border)] overflow-hidden animate-fade-in-up">
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

      {err && <div className="text-sm text-[var(--destructive)]">⚠ {err}</div>}

      <ConsoDrawer
        open={consoDrawerOpen}
        onClose={() => setConsoDrawerOpen(false)}
        planItems={plan.items}
        initialConsumed={consumed}
        onSave={handleSaveConso}
      />
    </div>
  );
}

function sumPrix(plan: PlanResponse): number {
  return plan.items.reduce((s, i) => s + i.prix, 0);
}
