"use client";

import { useState } from "react";
import { Sun, TrendingUp, Activity, Target, Camera } from "lucide-react";
import { todayKey } from "@/lib/sante";
import {
  useGeneratePlan,
  useMesures,
  useNutritionGoal,
  usePlanToday,
  useProjection,
  useUpdateNutritionGoal,
  useUpsertMesure,
} from "@/lib/queries/sante";
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

  // Drawer micros
  const [microsOpen, setMicrosOpen] = useState(false);

  const goalQ = useNutritionGoal();
  const mesuresQ = useMesures(180);
  const planQ = usePlanToday();
  const projectionQ = useProjection();
  const generateMutation = useGeneratePlan();
  const upsertMesureMutation = useUpsertMesure();
  const updateGoalMutation = useUpdateNutritionGoal();

  const goal = goalQ.data ?? null;
  const mesures = mesuresQ.data ?? [];
  // Plan du jour et projection peuvent légitimement ne pas exister (404).
  const plan = planQ.data ?? null;
  const projection = goal?.poids_cible ? projectionQ.data ?? null : null;
  const loading = goalQ.isLoading || mesuresQ.isLoading;
  const error =
    goalQ.isError || mesuresQ.isError
      ? (((goalQ.error ?? mesuresQ.error) as Error)?.message ?? "Erreur de chargement")
      : null;

  const onGeneratePlan = async (opts: { intensity?: string; budget_max_daily?: number; force?: boolean } = {}) => {
    const today = todayKey();
    return generateMutation.mutateAsync({ date: today, ...opts });
  };

  const onSaveMesure = async (m: { date: string; poids?: number; photo_url?: string; note?: string }) => {
    await upsertMesureMutation.mutateAsync(m);
  };

  const onSaveGoal = async (patch: any) => {
    await updateGoalMutation.mutateAsync(patch);
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
            onPlanUpdated={() => {}}
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
