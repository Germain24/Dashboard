"use client";
import { useState } from "react";
import dynamic from "next/dynamic";
import { CalendarDays, FileText, List, PieChart } from "lucide-react";
import { ErrorBoundary } from "@/components/ErrorBoundary";
import { ModuleHeader } from "@/components/layout";
import { TabLoading } from "@/components/ui/tab-loading";
import MoisTab from "@/components/budget/MoisTab";

const TransactionsTab = dynamic(() => import("@/components/budget/TransactionsTab"), {
  loading: TabLoading,
});
const EnveloppesTab = dynamic(() => import("@/components/budget/EnveloppesTab"), {
  loading: TabLoading,
});
const ContratsTab = dynamic(() => import("@/components/budget/ContratsTab"), {
  loading: TabLoading,
});

const TABS = [
  { id: "mois", label: "Historique", icon: CalendarDays },
  { id: "transactions", label: "Transactions", icon: List },
  { id: "enveloppes", label: "Enveloppes", icon: PieChart },
  { id: "contrats", label: "Contrats", icon: FileText },
];

export default function BudgetPage() {
  const [active, setActive] = useState("mois");
  return (
    <div className="space-y-0">
      <ModuleHeader
        title="Budget"
        subtitle="Dépenses & épargne"
        tabs={TABS}
        active={active}
        onChange={setActive}
      />
      <div key={active} className="p-6 animate-fade-in-up">
        <ErrorBoundary label="Budget">
          {active === "mois" && <MoisTab />}
          {active === "transactions" && <TransactionsTab />}
          {active === "enveloppes" && <EnveloppesTab />}
          {active === "contrats" && <ContratsTab />}
        </ErrorBoundary>
      </div>
    </div>
  );
}
