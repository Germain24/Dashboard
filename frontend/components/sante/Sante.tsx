"use client";

import { useEffect } from "react";
import dynamic from "next/dynamic";
import { useTabParam } from "@/lib/useTabParam";
import { TrendingUp, Activity, Target, Camera, ShoppingCart, Package } from "lucide-react";
import type { MesureSante, NutritionGoal, NutritionGoalUpdate } from "@/lib/sante";
import {
  useMesures,
  useNutritionGoal,
  useProjection,
  useUpdateNutritionGoal,
  useUpsertMesure,
} from "@/lib/queries/sante";
import { ModuleHeader, ModuleTabPanel } from "@/components/layout";
import { santeApi } from "@/lib/sante";
import { GoalBadge, SanteError, SanteLoading, SanteTabs } from "./SanteParts";
import { TabLoading } from "@/components/ui/tab-loading";

const GardeMangerTab = dynamic(() => import("@/components/cuisine/GardeMangerTab"), { loading: TabLoading });

type Tab = "fenetre" | "tendance" | "composition" | "objectif" | "progression" | "garde-manger";
const TABS: { id: Tab; label: string; Icon: React.ElementType }[] = [
  { id: "fenetre", label: "Courses", Icon: ShoppingCart },
  { id: "tendance", label: "Tendance", Icon: TrendingUp },
  { id: "composition", label: "Composition", Icon: Activity },
  { id: "progression", label: "Progression", Icon: Camera },
  { id: "objectif", label: "Objectif", Icon: Target },
  { id: "garde-manger", label: "Garde-manger", Icon: Package },
];
const TAB_PANEL_ID = "sante-tab-panel";

function latestWeight(measures: MesureSante[]): number | null {
  return (
    [...measures]
      .filter((measure) => measure.poids != null)
      .sort((a, b) => b.date.localeCompare(a.date))[0]?.poids ?? null
  );
}

function projectionFor(goal: NutritionGoal | null, data: ReturnType<typeof useProjection>["data"]) {
  return goal?.poids_cible ? (data ?? null) : null;
}

function queryError(
  goalQ: ReturnType<typeof useNutritionGoal>,
  measuresQ: ReturnType<typeof useMesures>,
): string | null {
  const error = goalQ.error ?? measuresQ.error;
  if (!error) return null;
  return error instanceof Error ? error.message : "Erreur de chargement";
}

function SanteBody({
  loading,
  tab,
  goal,
  mesures,
  projection,
  lastWeight,
  onSaveMesure,
  onSaveGoal,
}: {
  loading: boolean;
  tab: Tab;
  goal: NutritionGoal | null;
  mesures: MesureSante[];
  projection: ReturnType<typeof projectionFor>;
  lastWeight: number | null;
  onSaveMesure: (measure: {
    date: string;
    poids?: number;
    photo_url?: string;
    note?: string;
  }) => Promise<void>;
  onSaveGoal: (patch: NutritionGoalUpdate) => Promise<void>;
}) {
  return (
    <ModuleTabPanel key={tab} panelId={TAB_PANEL_ID} activeTab={tab}>
      {loading ? (
        <SanteLoading />
      ) : (
        tab === "garde-manger" ? (
          <div className="animate-fade-in-up p-6"><GardeMangerTab /></div>
        ) : (
          <div className="animate-fade-in-up p-6">
            <SanteTabs
              tab={tab}
              goal={goal}
              mesures={mesures}
              projection={projection}
              lastWeight={lastWeight}
              onSaveMesure={onSaveMesure}
              onSaveGoal={onSaveGoal}
            />
          </div>
        )
      )}
    </ModuleTabPanel>
  );
}

export function Sante() {
  const [tab, setTab] = useTabParam<Tab>("fenetre");
  useEffect(() => {
    if (tab !== "fenetre") return;
    void santeApi.refreshStorePricingIfStale().catch(() => undefined);
  }, [tab]);
  const goalQ = useNutritionGoal();
  const mesuresQ = useMesures(180);
  const projectionQ = useProjection();
  const upsertMesure = useUpsertMesure();
  const updateGoal = useUpdateNutritionGoal();
  const goal = goalQ.data ?? null;
  const mesures = mesuresQ.data ?? [];
  const error = tab === "garde-manger" ? null : queryError(goalQ, mesuresQ);
  const saveMesure = async (measure: {
    date: string;
    poids?: number;
    photo_url?: string;
    note?: string;
  }) => {
    await upsertMesure.mutateAsync(measure);
  };
  const saveGoal = async (patch: NutritionGoalUpdate) => {
    await updateGoal.mutateAsync(patch);
  };
  const tabs = TABS.map((item) => ({ id: item.id, label: item.label, icon: item.Icon }));
  return (
    <>
      <SanteError message={error} />
      <SanteContent
        error={error}
        tabs={tabs}
        tab={tab}
        setTab={setTab}
        goal={goal}
        mesures={mesures}
        projection={projectionFor(goal, projectionQ.data)}
        lastWeight={latestWeight(mesures)}
        loading={tab !== "garde-manger" && (goalQ.isLoading || mesuresQ.isLoading)}
        onSaveMesure={saveMesure}
        onSaveGoal={saveGoal}
      />
    </>
  );
}

function SanteContent({
  error,
  tabs,
  tab,
  setTab,
  goal,
  mesures,
  projection,
  lastWeight,
  loading,
  onSaveMesure,
  onSaveGoal,
}: {
  error: string | null;
  tabs: { id: Tab; label: string; icon: React.ElementType }[];
  tab: Tab;
  setTab: (tab: Tab) => void;
  goal: NutritionGoal | null;
  mesures: MesureSante[];
  projection: ReturnType<typeof projectionFor>;
  lastWeight: number | null;
  loading: boolean;
  onSaveMesure: (measure: {
    date: string;
    poids?: number;
    photo_url?: string;
    note?: string;
  }) => Promise<void>;
  onSaveGoal: (patch: NutritionGoalUpdate) => Promise<void>;
}) {
  if (error) return null;
  return (
    <div className="space-y-0">
      <ModuleHeader
        title="Santé"
        subtitle="Nutrition & mesures corporelles"
        tabs={tabs}
        active={tab}
        onChange={(id) => setTab(id as Tab)}
        panelId={TAB_PANEL_ID}
        actions={<GoalBadge goal={goal} />}
      />
      <SanteBody
        loading={loading}
        tab={tab}
        goal={goal}
        mesures={mesures}
        projection={projection}
        lastWeight={lastWeight}
        onSaveMesure={onSaveMesure}
        onSaveGoal={onSaveGoal}
      />
    </div>
  );
}
