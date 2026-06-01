'use client'
import { useState } from 'react'
import { CalendarDays, List, PieChart } from 'lucide-react'
import MoisTab from '@/components/budget/MoisTab'
import TransactionsTab from '@/components/budget/TransactionsTab'
import EnveloppesTab from '@/components/budget/EnveloppesTab'

const TABS = [
  { id: 'mois', label: 'Ce mois', icon: CalendarDays },
  { id: 'transactions', label: 'Transactions', icon: List },
  { id: 'enveloppes', label: 'Enveloppes', icon: PieChart },
]

export default function BudgetPage() {
  const [active, setActive] = useState('mois')
  return (
    <div className="space-y-0 animate-fade-in">
      <div className="px-6 py-5 border-b border-[var(--border)]">
        <div className="mb-4">
          <h1 className="text-xl font-semibold tracking-tight">Budget</h1>
          <p className="text-sm text-[var(--muted-foreground)] mt-0.5">Dépenses & épargne</p>
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
        {active === 'mois' && <MoisTab />}
        {active === 'transactions' && <TransactionsTab />}
        {active === 'enveloppes' && <EnveloppesTab />}
      </div>
    </div>
  )
}
