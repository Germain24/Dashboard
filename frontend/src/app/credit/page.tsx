"use client";

import { useTabParam } from "@/lib/useTabParam";
import { Route, Plane } from "lucide-react";
import { CreditTab } from "@/components/finance/CreditTab";
import { VoyageBudgetTab } from "@/components/finance/VoyageBudgetTab";
import { ModuleHeader, ModuleTabPanel } from "@/components/layout";
import { ErrorBoundary } from "@/components/ErrorBoundary";

const TABS = [
  { id: "feuille-de-route", label: "Feuille de route", icon: Route },
  { id: "voyage", label: "Voyage finançable", icon: Plane },
];
const TAB_PANEL_ID = "credit-tab-panel";

export default function CreditPage() {
  const [active, setActive] = useTabParam<string>("feuille-de-route");
  return (
    <div>
      <ModuleHeader
        title="Marge de crédit"
        subtitle="Feuille de route pour maximiser ta marge de crédit totale"
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
        <ErrorBoundary label="Marge de crédit">
          {active === "feuille-de-route" && <CreditTab />}
          {active === "voyage" && <VoyageBudgetTab />}
        </ErrorBoundary>
      </ModuleTabPanel>
    </div>
  );
}
