"use client";

import { useState } from "react";
import { Route, Plane } from "lucide-react";
import { CreditTab } from "@/components/finance/CreditTab";
import { VoyageBudgetTab } from "@/components/finance/VoyageBudgetTab";
import { ModuleHeader } from "@/components/layout";
import { ErrorBoundary } from "@/components/ErrorBoundary";

const TABS = [
  { id: "feuille-de-route", label: "Feuille de route", icon: Route },
  { id: "voyage", label: "Voyage finançable", icon: Plane },
];

export default function CreditPage() {
  const [active, setActive] = useState("feuille-de-route");
  return (
    <div>
      <ModuleHeader
        title="Marge de crédit"
        subtitle="Feuille de route pour maximiser ta marge de crédit totale"
        tabs={TABS}
        active={active}
        onChange={setActive}
      />
      <div key={active} className="p-6 animate-fade-in-up">
        <ErrorBoundary label="Marge de crédit">
          {active === "feuille-de-route" && <CreditTab />}
          {active === "voyage" && <VoyageBudgetTab />}
        </ErrorBoundary>
      </div>
    </div>
  );
}
