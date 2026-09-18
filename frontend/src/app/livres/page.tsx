"use client";
import { useTabParam } from "@/lib/useTabParam";
import { Library, BarChart3 } from "lucide-react";
import { ErrorBoundary } from "@/components/ErrorBoundary";
import { ModuleHeader, ModuleTabPanel } from "@/components/layout";
import BibliothequeTab from "@/components/livres/BibliothequeTab";
import StatsTab from "@/components/livres/StatsTab";

const TABS = [
  { id: "bibliotheque", label: "Bibliothèque", icon: Library },
  { id: "stats", label: "Stats & défi", icon: BarChart3 },
];
const TAB_PANEL_ID = "livres-tab-panel";

export default function LivresPage() {
  const [active, setActive] = useTabParam<string>("bibliotheque");
  return (
    <div className="space-y-0">
      <ModuleHeader
        title="Livres"
        subtitle="Bibliothèque personnelle"
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
        <ErrorBoundary label="Livres">
          {active === "bibliotheque" && <BibliothequeTab />}
          {active === "stats" && <StatsTab />}
        </ErrorBoundary>
      </ModuleTabPanel>
    </div>
  );
}
