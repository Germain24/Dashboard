"use client";

import { useTabParam } from "@/lib/useTabParam";
import {
  TRAINING_TAB_PANEL_ID,
  TrainingError,
  TrainingHeader,
  TrainingLoading,
  TrainingTabContent,
  useTrainingPageData,
  type Tab,
} from "./EntrainementParts";
import { ModuleTabPanel } from "@/components/layout";

export function Entrainement() {
  const [tab, setTab] = useTabParam<Tab>("aujourdhui");
  const page = useTrainingPageData();

  if (page.loading) return <TrainingLoading />;
  if (page.error) return <TrainingError message={page.error} />;

  return (
    <div className="space-y-0">
      <TrainingHeader
        tab={tab}
        onTabChange={setTab}
        todayJour={page.todayJour}
        intensity={page.intensity}
      />

      <ModuleTabPanel
        key={tab}
        panelId={TRAINING_TAB_PANEL_ID}
        activeTab={tab}
        className="p-6 animate-fade-in-up"
      >
        <TrainingTabContent
          tab={tab}
          program={page.program}
          exercices={page.exercices}
          sessions={page.sessions}
        />
      </ModuleTabPanel>
    </div>
  );
}
