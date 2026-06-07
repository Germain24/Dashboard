'use client'
import { useState } from 'react'
import { ChefHat, CalendarDays, ShoppingCart, Package } from 'lucide-react'
import RecettesTab from '@/components/cuisine/RecettesTab'
import PlanSemaineTab from '@/components/cuisine/PlanSemaineTab'
import CoursesTab from '@/components/cuisine/CoursesTab'
import GardeMangerTab from '@/components/cuisine/GardeMangerTab'

const TABS = [
  { id: 'recettes', label: 'Recettes', icon: ChefHat },
  { id: 'plan', label: 'Plan semaine', icon: CalendarDays },
  { id: 'courses', label: 'Courses', icon: ShoppingCart },
  { id: 'garde-manger', label: 'Garde-manger', icon: Package },
]

export default function CuisinePage() {
  const [active, setActive] = useState('recettes')
  return (
    <div className="space-y-0 animate-fade-in">
      <div className="px-6 py-5 border-b border-[var(--border)]">
        <div className="mb-4">
          <h1 className="text-xl font-semibold tracking-tight">Cuisine</h1>
          <p className="text-sm text-[var(--muted-foreground)] mt-0.5">Recettes & meal planning</p>
        </div>
        <div className="flex flex-wrap gap-1">
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
        {active === 'recettes' && <RecettesTab />}
        {active === 'plan' && <PlanSemaineTab />}
        {active === 'courses' && <CoursesTab />}
        {active === 'garde-manger' && <GardeMangerTab />}
      </div>
    </div>
  )
}
