"use client";
import { useTabParam } from "@/lib/useTabParam";
import dynamic from "next/dynamic";
import { CalendarDays, FileText, List, PieChart } from "lucide-react";
import { ErrorBoundary } from "@/components/ErrorBoundary";
import { ModuleHeader, ModuleTabPanel } from "@/components/layout";
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
const TAB_PANEL_ID = "budget-tab-panel";

export default function BudgetPage() {
  const [active, setActive] = useTabParam<string>("mois");
  const content = (
    {
      mois: <MoisTab />,
      transactions: <TransactionsTab />,
      enveloppes: <EnveloppesTab />,
      contrats: <ContratsTab />,
    } as Record<string, React.ReactNode>
  )[active];
  return (
    <div className="space-y-0">
      <ModuleHeader
        title="Budget"
        subtitle="Dépenses & épargne"
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
        <ErrorBoundary label="Budget">{content}</ErrorBoundary>
      </ModuleTabPanel>
    </div>
  );
}
