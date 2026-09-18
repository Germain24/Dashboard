"use client";
import { useTabParam } from "@/lib/useTabParam";
import dynamic from "next/dynamic";
import { ChefHat, CalendarDays, ShoppingCart, Package } from "lucide-react";
import { ErrorBoundary } from "@/components/ErrorBoundary";
import { ModuleHeader, ModuleTabPanel } from "@/components/layout";
import { TabLoading } from "@/components/ui/tab-loading";
import RecettesTab from "@/components/cuisine/RecettesTab";

const PlanSemaineTab = dynamic(() => import("@/components/cuisine/PlanSemaineTab"), {
  loading: TabLoading,
});
const CoursesTab = dynamic(() => import("@/components/cuisine/CoursesTab"), {
  loading: TabLoading,
});
const GardeMangerTab = dynamic(() => import("@/components/cuisine/GardeMangerTab"), {
  loading: TabLoading,
});

const TABS = [
  { id: "recettes", label: "Recettes", icon: ChefHat },
  { id: "plan", label: "Plan semaine", icon: CalendarDays },
  { id: "courses", label: "Courses", icon: ShoppingCart },
  { id: "garde-manger", label: "Garde-manger", icon: Package },
];
const TAB_PANEL_ID = "cuisine-tab-panel";

export default function CuisinePage() {
  const [active, setActive] = useTabParam<string>("recettes");
  const content = (
    {
      recettes: <RecettesTab />,
      plan: <PlanSemaineTab />,
      courses: <CoursesTab />,
      "garde-manger": <GardeMangerTab />,
    } as Record<string, React.ReactNode>
  )[active];
  return (
    <div className="space-y-0">
      <ModuleHeader
        title="Cuisine"
        subtitle="Recettes & meal planning"
        tabs={TABS}
        active={active}
        onChange={setActive}
        panelId={TAB_PANEL_ID}
      />
      <ModuleTabPanel
        key={active}
        panelId={TAB_PANEL_ID}
        activeTab={active}
        className="p-6 animate-fade-in-up"
      >
        <ErrorBoundary label="Cuisine">{content}</ErrorBoundary>
      </ModuleTabPanel>
    </div>
  );
}
