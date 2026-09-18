"use client";

import { useTabParam } from "@/lib/useTabParam";
import { Calendar, FileText } from "lucide-react";
import { ErrorBoundary } from "@/components/ErrorBoundary";
import { ModuleHeader, ModuleTabPanel } from "@/components/layout";
import DocumentsTab from "@/components/documents/DocumentsTab";
import EcheancesTab from "@/components/documents/EcheancesTab";

const TABS = [
  { id: "documents", label: "Documents", icon: FileText },
  { id: "echeances", label: "Échéances", icon: Calendar },
] as const;

type Tab = (typeof TABS)[number]["id"];
const TAB_PANEL_ID = "documents-tab-panel";

export default function DocumentsPage() {
  const [tab, setTab] = useTabParam<Tab>("documents");

  return (
    <div className="space-y-0">
      <ModuleHeader
        title="Documents"
        subtitle="Coffre-fort administratif"
        tabs={TABS.map((t) => ({ id: t.id, label: t.label, icon: t.icon }))}
        active={tab}
        onChange={(id) => setTab(id as Tab)}
        panelId={TAB_PANEL_ID}
      />

      <ModuleTabPanel panelId={TAB_PANEL_ID} activeTab={tab} className="p-6 animate-fade-in-up">
        <ErrorBoundary label="Documents">
          {tab === "documents" ? <DocumentsTab /> : <EcheancesTab />}
        </ErrorBoundary>
      </ModuleTabPanel>
    </div>
  );
}
