'use client'
import { useState } from 'react'
import { CheckSquare, Grid3X3, CalendarDays, Settings2 } from 'lucide-react'
import { ErrorBoundary } from '@/components/ErrorBoundary'
import { ModuleHeader } from '@/components/layout'
import AujourdhuiTab from '@/components/habitudes/AujourdhuiTab'
import HeatmapTab from '@/components/habitudes/HeatmapTab'
import MoisTab from '@/components/habitudes/MoisTab'
import GestionTab from '@/components/habitudes/GestionTab'

const TABS = [
  { id: 'aujourd-hui', label: "Aujourd'hui", icon: CheckSquare },
  { id: 'mois', label: 'Mois', icon: CalendarDays },
  { id: 'heatmap', label: 'Heatmap', icon: Grid3X3 },
  { id: 'gestion', label: 'Gérer', icon: Settings2 },
]

export default function HabitudesPage() {
  const [active, setActive] = useState('aujourd-hui')
  return (
    <div className="space-y-0 animate-fade-in">
      <ModuleHeader
        title="Habitudes"
        subtitle="Streaks & suivi quotidien"
        tabs={TABS}
        active={active}
        onChange={setActive}
      />
      <div key={active} className="p-6 animate-fade-in-up">
        <ErrorBoundary label="Habitudes">
          {active === 'aujourd-hui' && <AujourdhuiTab />}
          {active === 'mois' && <MoisTab />}
          {active === 'heatmap' && <HeatmapTab />}
          {active === 'gestion' && <GestionTab />}
        </ErrorBoundary>
      </div>
    </div>
  )
}
