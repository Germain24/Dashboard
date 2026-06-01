"use client";

import { useState } from "react";
import { TrendingUp, BarChart3, RefreshCw, Star, LayoutGrid, CreditCard } from "lucide-react";
import { PortefeuilleTab } from "./PortefeuilleTab";
import { SuiviTab } from "./SuiviTab";
import { CompositionTab } from "./CompositionTab";
import { BuffettTab } from "./BuffettTab";
import { RebalancingTab } from "./RebalancingTab";
import { TransactionsTab } from "./TransactionsTab";

type Tab = "suivi" | "portefeuille" | "composition" | "rebalancing" | "buffett" | "transactions";

const TABS: { id: Tab; label: string; icon: React.ElementType }[] = [
  { id: "suivi",        label: "Suivi",        icon: TrendingUp },
  { id: "portefeuille", label: "Portefeuille",  icon: BarChart3 },
  { id: "composition",  label: "Composition",   icon: LayoutGrid },
  { id: "rebalancing",  label: "Rebalancing",   icon: RefreshCw },
  { id: "buffett",      label: "Buffett",       icon: Star },
  { id: "transactions", label: "Transactions",  icon: CreditCard },
];

export function Finance() {
  const [active, setActive] = useState<Tab>("suivi");

  return (
    <div className="space-y-0 animate-fade-in">
      {/* Header */}
      <div className="px-6 py-5 border-b border-[var(--border)]">
        <div className="mb-4">
          <h1 className="text-xl font-semibold tracking-tight">Finance</h1>
          <p className="text-sm text-[var(--muted-foreground)] mt-0.5">Portefeuille long terme</p>
        </div>

        {/* Tabs — style Linear */}
        <div className="flex gap-1 flex-wrap">
          {TABS.map((tab) => {
            const Icon = tab.icon;
            return (
              <button
                key={tab.id}
                onClick={() => setActive(tab.id)}
                className={`flex items-center gap-1.5 px-3 py-2 text-sm font-medium rounded-md transition-all duration-200 ${
                  active === tab.id
                    ? "text-[var(--ring)] bg-[color-mix(in_srgb,var(--ring)_10%,transparent)]"
                    : "text-[var(--muted-foreground)] hover:text-[var(--foreground)] hover:bg-[var(--muted)]"
                }`}
              >
                <Icon size={15} />
                {tab.label}
              </button>
            );
          })}
        </div>
      </div>

      {/* Content — re-mounts on tab change for fade-in-up */}
      <div key={active} className="p-6 animate-fade-in-up">
        {active === "suivi"        && <SuiviTab />}
        {active === "portefeuille" && <PortefeuilleTab />}
        {active === "composition"  && <CompositionTab />}
        {active === "rebalancing"  && <RebalancingTab />}
        {active === "buffett"      && <BuffettTab />}
        {active === "transactions" && <TransactionsTab />}
      </div>
    </div>
  );
}
