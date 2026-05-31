'use client'
import { useState } from 'react'
import { RecettesTab } from '@/components/cuisine/RecettesTab'
import { PlanSemaineTab } from '@/components/cuisine/PlanSemaineTab'
import { CoursesTab } from '@/components/cuisine/CoursesTab'

type Tab = 'recettes' | 'plan' | 'courses'

export default function CuisinePage() {
  const [tab, setTab] = useState<Tab>('recettes')

  return (
    <div className="p-6 space-y-6">
      <h1 className="text-2xl font-semibold tracking-tight">Cuisine</h1>

      <nav className="flex gap-1 border-b border-[var(--border)]">
        {([
          ['recettes', '🍽️ Recettes'],
          ['plan', '📅 Plan semaine'],
          ['courses', '🛒 Courses'],
        ] as [Tab, string][]).map(([k, label]) => (
          <button
            key={k}
            onClick={() => setTab(k)}
            className={`px-3 py-2 text-sm -mb-px border-b-2 ${
              tab === k
                ? 'border-blue-500 text-[var(--foreground)]'
                : 'border-transparent text-[var(--muted-foreground)] hover:text-[var(--foreground)]'
            }`}
          >
            {label}
          </button>
        ))}
      </nav>

      <div>
        {tab === 'recettes' && <RecettesTab />}
        {tab === 'plan' && <PlanSemaineTab />}
        {tab === 'courses' && <CoursesTab />}
      </div>
    </div>
  )
}
