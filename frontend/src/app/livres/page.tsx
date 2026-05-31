'use client'
import { useState } from 'react'
import { BibliothequeTab } from '@/components/livres/BibliothequeTab'

type Tab = 'bibliotheque'

const TABS: [Tab, string][] = [
  ['bibliotheque', '📚 Bibliothèque'],
]

export default function LivresPage() {
  const [tab, setTab] = useState<Tab>('bibliotheque')

  return (
    <div className="p-6 space-y-6">
      <header className="flex items-center gap-3">
        <h1 className="text-2xl font-semibold tracking-tight">Livres</h1>
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

      {tab === 'bibliotheque' && <BibliothequeTab />}
    </div>
  )
}
