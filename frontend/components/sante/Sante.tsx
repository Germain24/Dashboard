"use client";

import { useCallback, useEffect, useState } from "react";
import { Apple } from "lucide-react";
import {
  santeApi,
  type MesureSante,
  type NutritionGoal,
  type PlanResponse,
  type ProjectionResponse,
  todayKey,
} from "@/lib/sante";
import { JourTab } from "./JourTab";
import { TendanceTab } from "./TendanceTab";
import { CompositionTab } from "./CompositionTab";
import { GoalTab } from "./GoalTab";
import { MicrosDrawer } from "./MicrosDrawer";

type Tab = "jour" | "tendance" | "composition" | "objectif";

export function Sante() {
  const [tab, setTab] = useState<Tab>("jour");
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  const [goal, setGoal] = useState<NutritionGoal | null>(null);
  const [mesures, setMesures] = useState<MesureSante[]>([]);
  const [plan, setPlan] = useState<PlanResponse | null>(null);
  const [projection, setProjection] = useState<ProjectionResponse | null>(null);

  // Drawer micros
  const [microsOpen, setMicrosOpen] = useState(false);

  const reloadAll = useCallback(async () => {
    const [g, ms] = await Promise.all([santeApi.getGoal(), santeApi.listMesures(180)]);
    setGoal(g);
    setMesures(ms);
    // Plan du jour (peut ne pas exister)
    try {
      const p = await santeApi.getPlanToday();
      setPlan(p);
    } catch {
      setPlan(null);
    }
    // Projection (peut échouer si pas de poids cible)
    if (g.poids_cible) {
      try {
        const proj = await santeApi.getProjection();
        setProjection(proj);
      } catch {
        setProjection(null);
      }
    } else {
      setProjection(null);
    }
  }, []);

  useEffect(() => {
    let cancelled = false;
    (async () => {
      try {
        await reloadAll();
        if (cancelled) return;
        setLoading(false);
      } catch (e: any) {
        if (cancelled) return;
        setError(e?.message ?? "Erreur de chargement");
        setLoading(false);
      }
    })();
    return () => { cancelled = true; };
  }, [reloadAll]);

  const onGeneratePlan = async (opts: { intensity?: string; budget_max_daily?: number; force?: boolean } = {}) => {
    const today = todayKey();
    const p = await santeApi.generatePlan({ date: today, ...opts });
    setPlan(p);
    // Si pas de mesure pour aujourd'hui, on met à jour celle d'aujourd'hui en silencieux
    return p;
  };

  const onSaveMesure = async (m: { date: string; poids?: number; photo_url?: string; note?: string }) => {
    await santeApi.upsertMesure(m);
    await reloadAll();
  };

  const onSaveGoal = async (patch: any) => {
    const g = await santeApi.updateGoal(patch);
    setGoal(g);
    if (g.poids_cible) {
      try {
        const proj = await santeApi.getProjection();
        setProjection(proj);
      } catch {
        setProjection(null);
      }
    }
  };

  if (loading) return <div className="flex items-center gap-2"><Apple className="h-5 w-5" /> Chargement…</div>;
  if (error) return <div className="text-red-500">⚠ {error}</div>;

  return (
    <div className="space-y-4">
      <header className="flex items-center gap-3">
        <Apple className="h-6 w-6" />
        <h1 className="text-2xl font-semibold tracking-tight">Santé / Nutrition</h1>
        {goal?.poids_cible && (
          <span className="ml-auto text-xs rounded bg-[var(--muted)] px-2 py-1 text-[var(--muted-foreground)]">
            Cible {goal.poids_cible.toFixed(1)} kg
            {goal.body_fat_target_pct ? ` · ${goal.body_fat_target_pct}% MG` : ""}
          </span>
        )}
      </header>

      <nav className="flex gap-1 border-b border-[var(--border)]">
        {([
          ["jour", "🥗 Jour"],
          ["tendance", "📈 Tendance"],
          ["composition", "⚖️ Composition"],
          ["objectif", "🎯 Objectif"],
        ] as [Tab, string][]).map(([k, label]) => (
          <button
            key={k}
            onClick={() => setTab(k)}
            className={`px-3 py-2 text-sm -mb-px border-b-2 ${tab === k ? "border-blue-500 text-[var(--foreground)]" : "border-transparent text-[var(--muted-foreground)] hover:text-[var(--foreground)]"}`}
          >
            {label}
          </button>
        ))}
      </nav>

      {tab === "jour" && (
        <JourTab
          plan={plan}
          goal={goal}
          onGenerate={onGeneratePlan}
          onPlanUpdated={(p) => setPlan(p)}
          onOpenMicros={() => setMicrosOpen(true)}
        />
      )}
      {tab === "tendance" && (
        <TendanceTab mesures={mesures} projection={projection} goal={goal} />
      )}
      {tab === "composition" && (
        <CompositionTab mesures={mesures} onSave={onSaveMesure} />
      )}
      {tab === "objectif" && goal && (
        <GoalTab goal={goal} onSave={onSaveGoal} />
      )}

      <MicrosDrawer
        open={microsOpen}
        onClose={() => setMicrosOpen(false)}
        targets={plan?.targets ?? {}}
        totals={plan?.totals ?? {}}
      />
    </div>
  );
}
