"use client";

import { useTabParam } from "@/lib/useTabParam";
import { BookOpen, AlarmClock, Clock, Award, BarChart3, Brain, Sparkles } from "lucide-react";
import { ModuleHeader, ModuleTabPanel } from "@/components/layout";
import { CoursTab } from "./CoursTab";
import { DeadlinesTab } from "./DeadlinesTab";
import { GpaTab } from "./GpaTab";
import { SessionsTab } from "./SessionsTab";
import { StatistiquesTab } from "./StatistiquesTab";
import { RevisionTab } from "./RevisionTab";
import { CompetencesTab } from "./CompetencesTab";

type Tab = "cours" | "deadlines" | "sessions" | "stats" | "revision" | "gpa" | "competences";

const TABS: { id: Tab; label: string; Icon: React.ElementType }[] = [
  { id: "cours", label: "Cours", Icon: BookOpen },
  { id: "deadlines", label: "Deadlines", Icon: AlarmClock },
  { id: "sessions", label: "Sessions", Icon: Clock },
  { id: "stats", label: "Stats", Icon: BarChart3 },
  { id: "revision", label: "Révision", Icon: Brain },
  { id: "gpa", label: "GPA", Icon: Award },
  { id: "competences", label: "Compétences", Icon: Sparkles },
];
const TAB_PANEL_ID = "etudes-tab-panel";

export function Etudes() {
  const [tab, setTab] = useTabParam<Tab>("cours");

  return (
    <div className="space-y-0">
      <ModuleHeader
        title="Études"
        subtitle="Cours, évaluations & GPA"
        tabs={TABS.map((t) => ({ id: t.id, label: t.label, icon: t.Icon }))}
        active={tab}
        onChange={(id) => setTab(id as Tab)}
        panelId={TAB_PANEL_ID}
      />

      <ModuleTabPanel
        key={tab}
        panelId={TAB_PANEL_ID}
        activeTab={tab}
        className="p-6 animate-fade-in-up"
      >
        {tab === "cours" && <CoursTab />}
        {tab === "deadlines" && <DeadlinesTab />}
        {tab === "gpa" && <GpaTab />}
        {tab === "sessions" && <SessionsTab />}
        {tab === "stats" && <StatistiquesTab />}
        {tab === "revision" && <RevisionTab />}
        {tab === "competences" && <CompetencesTab />}
      </ModuleTabPanel>
    </div>
  );
}
