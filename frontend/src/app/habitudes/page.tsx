"use client";
import { useState } from "react";
import dynamic from "next/dynamic";
import { CheckSquare, Grid3X3, CalendarDays, Settings2 } from "lucide-react";
import { ErrorBoundary } from "@/components/ErrorBoundary";
import { ModuleHeader } from "@/components/layout";
import { TabLoading } from "@/components/ui/tab-loading";
import AujourdhuiTab from "@/components/habitudes/AujourdhuiTab";

const HeatmapTab = dynamic(() => import("@/components/habitudes/HeatmapTab"), {
  loading: TabLoading,
});
const MoisTab = dynamic(() => import("@/components/habitudes/MoisTab"), { loading: TabLoading });
const GestionTab = dynamic(() => import("@/components/habitudes/GestionTab"), {
  loading: TabLoading,
});

const TABS = [
  { id: "aujourd-hui", label: "Aujourd'hui", icon: CheckSquare },
  { id: "mois", label: "Mois", icon: CalendarDays },
  { id: "heatmap", label: "Heatmap", icon: Grid3X3 },
  { id: "gestion", label: "Gérer", icon: Settings2 },
];

export default function HabitudesPage() {
  const [active, setActive] = useState("aujourd-hui");
  return (
    <div className="space-y-0">
      <ModuleHeader
        title="Habitudes"
        subtitle="Streaks & suivi quotidien"
        tabs={TABS}
        active={active}
        onChange={setActive}
      />
      <div key={active} className="p-6 animate-fade-in-up">
        <ErrorBoundary label="Habitudes">
          {active === "aujourd-hui" && <AujourdhuiTab />}
          {active === "mois" && <MoisTab />}
          {active === "heatmap" && <HeatmapTab />}
          {active === "gestion" && <GestionTab />}
        </ErrorBoundary>
      </div>
    </div>
  );
}
