'use client'
import { useState } from 'react'
import { Library, BarChart3 } from 'lucide-react'
import { ErrorBoundary } from '@/components/ErrorBoundary'
import { ModuleHeader } from '@/components/layout'
import BibliothequeTab from '@/components/livres/BibliothequeTab'
import StatsTab from '@/components/livres/StatsTab'

const TABS = [
  { id: 'bibliotheque', label: 'Bibliothèque', icon: Library },
  { id: 'stats', label: 'Stats & défi', icon: BarChart3 },
]

export default function LivresPage() {
  const [active, setActive] = useState('bibliotheque')
  return (
    <div className="space-y-0 animate-fade-in">
      <ModuleHeader
        title="Livres"
        subtitle="Bibliothèque personnelle"
        tabs={TABS}
        active={active}
        onChange={setActive}
      />
      <div key={active} className="p-6 animate-fade-in-up">
        <ErrorBoundary label="Livres">
          {active === 'bibliotheque' && <BibliothequeTab />}
          {active === 'stats' && <StatsTab />}
        </ErrorBoundary>
      </div>
    </div>
  )
}
