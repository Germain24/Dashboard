'use client'
import { useState } from 'react'
import { MoisTab } from '@/components/budget/MoisTab'
import { TransactionsTab } from '@/components/budget/TransactionsTab'
import { EnveloppesTab } from '@/components/budget/EnveloppesTab'

type Tab = 'mois' | 'transactions' | 'enveloppes'

const TABS: [Tab, string][] = [
  ['mois', '📅 Mois'],
  ['transactions', '📋 Transactions'],
  ['enveloppes', '🎯 Enveloppes'],
]

export default function BudgetPage() {
  const [tab, setTab] = useState<Tab>('mois')

  return (
    <div className="p-6 space-y-6">
      <header className="flex items-center gap-3">
        <h1 className="text-2xl font-semibold tracking-tight">Budget</h1>
      </header>

      <nav className="flex gap-1 border-b border-[var(--border)] flex-wrap">
        {TABS.map(([k, label]) => (
          <button
            key={k}
            onClick={() => setTab(k)}
            className={`px-3 py-2 text-sm -mb-px border-b-2 ${tab === k ? 'border-blue-500 text-[var(--foreground)]' : 'border-transparent text-[var(--muted-foreground)] hover:text-[var(--foreground)]'}`}
          >
            {label}
          </button>
        ))}
      </nav>

      {tab === 'mois' && <MoisTab />}
      {tab === 'transactions' && <TransactionsTab />}
      {tab === 'enveloppes' && <EnveloppesTab />}
    </div>
  )
}
