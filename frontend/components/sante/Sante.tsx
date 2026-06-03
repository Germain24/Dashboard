"use client";

import { useCallback, useEffect, useState } from "react";
import { Sun, TrendingUp, Activity, Target, Camera } from "lucide-react";
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
import { ProgressionTab } from "./ProgressionTab";
import { MicrosDrawer } from "./MicrosDrawer";

type Tab = "jour" | "tendance" | "composition" | "objectif" | "progression";

const TABS: { id: Tab; label: string; Icon: React.ElementType }[] = [
  { id: "jour", label: "Jour", Icon: Sun },
  { id: "tendance", label: "Tendance", Icon: TrendingUp },
  { id: "composition", label: "Composition", Icon: Activity },
  { id: "progression", label: "Progression", Icon: Camera },
  { id: "objectif", label: "Objectif", Icon: Target },
];

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

  if (loading) {
    return (
      <div className="p-6 space-y-4 animate-fade-in">
        {[1, 2, 3].map((i) => (
          <div key={i} className="h-20 rounded-xl border border-[var(--border)] bg-[var(--card)] skeleton-shimmer" />
        ))}
      </div>
    );
  }
  if (error) return <div className="p-6 text-[var(--destructive)]">⚠ {error}</div>;

  return (
    <div className="space-y-0 animate-fade-in">
      <div className="px-6 py-5 border-b border-[var(--border)]">
        <div className="mb-4 flex items-start justify-between">
          <div>
            <h1 className="text-xl font-semibold tracking-tight">Santé</h1>
            <p className="text-sm text-[var(--muted-foreground)] mt-0.5">Nutrition &amp; mesures corporelles</p>
          </div>
          {goal?.poids_cible && (
            <span className="text-xs rounded-md bg-[var(--muted)] px-2.5 py-1 text-[var(--muted-foreground)]">
              Cible {goal.poids_cible.toFixed(1)} kg
              {goal.body_fat_target_pct ? ` · ${goal.body_fat_target_pct}% MG` : ""}
            </span>
          )}
        </div>
        <div className="flex gap-1">
          {TABS.map(({ id, label, Icon }) => (
            <button
              key={id}
              onClick={() => setTab(id)}
              className={`flex items-center gap-1.5 px-3 py-2 text-sm font-medium rounded-md transition-all duration-200 ${
                tab === id
                  ? "text-[var(--ring)] bg-[color-mix(in_srgb,var(--ring)_10%,transparent)]"
                  : "text-[var(--muted-foreground)] hover:text-[var(--foreground)] hover:bg-[var(--muted)]"
              }`}
            >
              <Icon size={15} />{label}
            </button>
          ))}
        </div>
      </div>

      <div key={tab} className="p-6 animate-fade-in-up">
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
        {tab === "progression" && <ProgressionTab />}
        {tab === "objectif" && goal && (
          <GoalTab goal={goal} onSave={onSaveGoal} />
        )}
      </div>

      <MicrosDrawer
        open={microsOpen}
        onClose={() => setMicrosOpen(false)}
        targets={plan?.targets ?? {}}
        totals={plan?.totals ?? {}}
      />
    </div>
  );
}
