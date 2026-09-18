"use client";

/** Agenda — composant principal (orchestrateur + onglets). */

import {
  CalendarDays,
  CalendarRange,
  CalendarClock,
  GraduationCap,
  ListTodo,
  SlidersHorizontal,
} from "lucide-react";
import type { AgendaJour } from "@/lib/agenda";
import { useAgendaToday } from "@/lib/queries/agenda";
import { useTabParam } from "@/lib/useTabParam";
import { ModuleHeader, ModuleTabPanel } from "@/components/layout";
import JourTab from "./JourTab";
import SemaineTab from "./SemaineTab";
import MoisTab from "./MoisTab";
import SemesterTab from "./SemesterTab";
import TachesTab from "./TachesTab";
import PreferencesTab from "./PreferencesTab";
import { AgendaError, AgendaIndicators, AgendaTabContent } from "./AgendaParts";

type Tab = "jour" | "semaine" | "mois" | "taches" | "cours" | "preferences";
const TABS: { id: Tab; label: string; Icon: React.ElementType }[] = [
  { id: "jour", label: "Aujourd'hui", Icon: CalendarDays },
  { id: "semaine", label: "Semaine", Icon: CalendarRange },
  { id: "mois", label: "Mois", Icon: CalendarClock },
  { id: "taches", label: "Tâches", Icon: ListTodo },
  { id: "cours", label: "Cours", Icon: GraduationCap },
  { id: "preferences", label: "Préférences", Icon: SlidersHorizontal },
];
const TAB_PANEL_ID = "agenda-tab-panel";

function TabView({ tab, loading, data }: { tab: Tab; loading: boolean; data: AgendaJour | null }) {
  return (
    <AgendaTabContent
      tab={tab}
      loading={loading}
      data={data}
      onRender={(current) => <TabPanel tab={current as Tab} data={data} />}
    />
  );
}

function TabPanel({ tab, data }: { tab: Tab; data: AgendaJour | null }) {
  const panels: Record<Tab, React.ReactNode> = {
    jour: data ? <JourTab data={data} /> : null,
    semaine: <SemaineTab />,
    mois: <MoisTab />,
    taches: <TachesTab />,
    cours: <SemesterTab />,
    preferences: <PreferencesTab />,
  };
  return panels[tab];
}

export default function Agenda() {
  const [tab, setTab] = useTabParam<Tab>("jour");
  const todayQ = useAgendaToday();
  const data = todayQ.data ?? null;
  const error = todayQ.isError ? todayQ.error.message : null;
  const tabs = TABS.map((item) => ({ id: item.id, label: item.label, icon: item.Icon }));
  return (
    <div className="space-y-0">
      <ModuleHeader
        title="Agenda"
        subtitle="Événements & tâches"
        tabs={tabs}
        active={tab}
        onChange={(id) => setTab(id as Tab)}
        panelId={TAB_PANEL_ID}
        actions={<AgendaIndicators data={data} />}
      />
      <ModuleTabPanel
        key={tab}
        panelId={TAB_PANEL_ID}
        activeTab={tab}
        className="animate-fade-in-up p-6"
      >
        <AgendaError message={error} />
        <TabView tab={tab} loading={todayQ.isLoading} data={data} />
      </ModuleTabPanel>
    </div>
  );
}
