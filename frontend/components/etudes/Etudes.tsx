"use client";

import { useState } from "react";
import { BookOpen, AlarmClock, Clock, Award, BarChart3, Brain } from "lucide-react";
import { ModuleHeader } from "@/components/layout";
import { CoursTab } from "./CoursTab";
import { DeadlinesTab } from "./DeadlinesTab";
import { GpaTab } from "./GpaTab";
import { SessionsTab } from "./SessionsTab";
import { StatistiquesTab } from "./StatistiquesTab";
import { RevisionTab } from "./RevisionTab";

type Tab = "cours" | "deadlines" | "sessions" | "stats" | "revision" | "gpa";

const TABS: { id: Tab; label: string; Icon: React.ElementType }[] = [
  { id: "cours", label: "Cours", Icon: BookOpen },
  { id: "deadlines", label: "Deadlines", Icon: AlarmClock },
  { id: "sessions", label: "Sessions", Icon: Clock },
  { id: "stats", label: "Stats", Icon: BarChart3 },
  { id: "revision", label: "Révision", Icon: Brain },
  { id: "gpa", label: "GPA", Icon: Award },
];

export function Etudes() {
  const [tab, setTab] = useState<Tab>("cours");

  return (
    <div className="space-y-0 animate-fade-in">
      <ModuleHeader
        title="Études"
        subtitle="Cours, évaluations & GPA"
        tabs={TABS.map((t) => ({ id: t.id, label: t.label, icon: t.Icon }))}
        active={tab}
        onChange={(id) => setTab(id as Tab)}
      />

      <div key={tab} className="p-6 animate-fade-in-up">
        {tab === "cours" && <CoursTab />}
        {tab === "deadlines" && <DeadlinesTab />}
        {tab === "gpa" && <GpaTab />}
        {tab === "sessions" && <SessionsTab />}
        {tab === "stats" && <StatistiquesTab />}
        {tab === "revision" && <RevisionTab />}
      </div>
    </div>
  );
}
