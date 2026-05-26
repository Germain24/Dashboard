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
import { Tabs, TabsList, TabsTrigger, TabsContent } from "@/components/ui/tabs";
import { Badge } from "@/components/ui/badge";
import { Spinner } from "@/components/ui/spinner";
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
  const [microsOpen, setMicrosOpen] = useState(false);

  const reloadAll = useCallback(async () => {
    const [g, ms] = await Promise.all([santeApi.getGoal(), santeApi.listMesures(180)]);
    setGoal(g);
    setMesures(ms);
    try {
      const p = await santeApi.getPlanToday();
      setPlan(p);
    } catch {
      setPlan(null);
    }
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

  const onGeneratePlan = async (
    opts: { intensity?: string; budget_max_daily?: number; force?: boolean } = {},
  ) => {
    const today = todayKey();
    const p = await santeApi.generatePlan({ date: today, ...opts });
    setPlan(p);
    return p;
  };

  const onSaveMesure = async (m: {
    date: string;
    poids?: number;
    photo_url?: string;
    note?: string;
  }) => {
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

  if (loading) return <Spinner label="Chargement de la santé…" />;
  if (error) return <p className="text-sm text-[var(--destructive)]">⚠ {error}</p>;

  return (
    <div className="space-y-4">
      <header className="flex items-center gap-3">
        <Apple className="h-5 w-5 shrink-0" />
        <h1 className="text-xl font-semibold tracking-tight">Santé / Nutrition</h1>
        {goal?.poids_cible && (
          <Badge className="ml-auto">
            Cible {goal.poids_cible.toFixed(1)} kg
            {goal.body_fat_target_pct ? ` · ${goal.body_fat_target_pct}% MG` : ""}
          </Badge>
        )}
      </header>

      <Tabs value={tab} onValueChange={(v) => setTab(v as Tab)}>
        <TabsList>
          <TabsTrigger value="jour">🥗 Jour</TabsTrigger>
          <TabsTrigger value="tendance">📈 Tendance</TabsTrigger>
          <TabsTrigger value="composition">⚖️ Composition</TabsTrigger>
          <TabsTrigger value="objectif">🎯 Objectif</TabsTrigger>
        </TabsList>

        <TabsContent value="jour">
          <JourTab
            plan={plan}
            goal={goal}
            onGenerate={onGeneratePlan}
            onPlanUpdated={(p) => setPlan(p)}
            onOpenMicros={() => setMicrosOpen(true)}
          />
        </TabsContent>
        <TabsContent value="tendance">
          <TendanceTab mesures={mesures} projection={projection} goal={goal} />
        </TabsContent>
        <TabsContent value="composition">
          <CompositionTab mesures={mesures} onSave={onSaveMesure} />
        </TabsContent>
        <TabsContent value="objectif">
          {goal && <GoalTab goal={goal} onSave={onSaveGoal} />}
        </TabsContent>
      </Tabs>

      <MicrosDrawer
        open={microsOpen}
        onClose={() => setMicrosOpen(false)}
        targets={plan?.targets ?? {}}
        totals={plan?.totals ?? {}}
      />
    </div>
  );
}
