'use client'
import { useState } from 'react'
import { CheckSquare, Grid3X3, CalendarDays, Settings2 } from 'lucide-react'
import { ErrorBoundary } from '@/components/ErrorBoundary'
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
      <div className="px-6 py-5 border-b border-[var(--border)]">
        <div className="mb-4">
          <h1 className="text-xl font-semibold tracking-tight">Habitudes</h1>
          <p className="text-sm text-[var(--muted-foreground)] mt-0.5">Streaks & suivi quotidien</p>
        </div>
        <div className="flex gap-1">
          {TABS.map(tab => {
            const Icon = tab.icon
            return (
              <button key={tab.id} onClick={() => setActive(tab.id)}
                className={`flex items-center gap-1.5 px-3 py-2 text-sm font-medium rounded-md transition-all duration-200 cursor-pointer ${
                  active === tab.id
                    ? 'text-[var(--ring)] bg-[color-mix(in_srgb,var(--ring)_10%,transparent)]'
                    : 'text-[var(--muted-foreground)] hover:text-[var(--foreground)] hover:bg-[var(--muted)]'
                }`}>
                <Icon size={15} />{tab.label}
              </button>
            )
          })}
        </div>
      </div>
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
