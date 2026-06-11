'use client'
import { useState } from 'react'
import { Library, BarChart3 } from 'lucide-react'
import { ErrorBoundary } from '@/components/ErrorBoundary'
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
      <div className="px-6 py-5 border-b border-[var(--border)]">
        <div className="mb-4">
          <h1 className="text-xl font-semibold tracking-tight">Livres</h1>
          <p className="text-sm text-[var(--muted-foreground)] mt-0.5">Bibliothèque personnelle</p>
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
        <ErrorBoundary label="Livres">
          {active === 'bibliotheque' && <BibliothequeTab />}
          {active === 'stats' && <StatsTab />}
        </ErrorBoundary>
      </div>
    </div>
  )
}
