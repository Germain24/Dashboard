'use client'
import { useState } from 'react'
import { ChefHat, CalendarDays, ShoppingCart, Package } from 'lucide-react'
import { ErrorBoundary } from '@/components/ErrorBoundary'
import { ModuleHeader } from '@/components/layout'
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
      <ModuleHeader
        title="Cuisine"
        subtitle="Recettes & meal planning"
        tabs={TABS}
        active={active}
        onChange={setActive}
      />
      <div key={active} className="p-6 animate-fade-in-up">
        <ErrorBoundary label="Cuisine">
          {active === 'recettes' && <RecettesTab />}
          {active === 'plan' && <PlanSemaineTab />}
          {active === 'courses' && <CoursesTab />}
          {active === 'garde-manger' && <GardeMangerTab />}
        </ErrorBoundary>
      </div>
    </div>
  )
}
