'use client'
import { useState } from 'react'
import { CalendarDays, List, PieChart } from 'lucide-react'
import { ErrorBoundary } from '@/components/ErrorBoundary'
import { ModuleHeader } from '@/components/layout'
import MoisTab from '@/components/budget/MoisTab'
import TransactionsTab from '@/components/budget/TransactionsTab'
import EnveloppesTab from '@/components/budget/EnveloppesTab'

const TABS = [
  { id: 'mois', label: 'Historique', icon: CalendarDays },
  { id: 'transactions', label: 'Transactions', icon: List },
  { id: 'enveloppes', label: 'Enveloppes', icon: PieChart },
]

export default function BudgetPage() {
  const [active, setActive] = useState('mois')
  return (
    <div className="space-y-0 animate-fade-in">
      <ModuleHeader
        title="Budget"
        subtitle="Dépenses & épargne"
        tabs={TABS}
        active={active}
        onChange={setActive}
      />
      <div key={active} className="p-6 animate-fade-in-up">
        <ErrorBoundary label="Budget">
          {active === 'mois' && <MoisTab />}
          {active === 'transactions' && <TransactionsTab />}
          {active === 'enveloppes' && <EnveloppesTab />}
        </ErrorBoundary>
      </div>
    </div>
  )
}
