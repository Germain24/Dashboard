'use client'
import { useEffect, useState } from 'react'
import { fetchTransactions } from '@/lib/budget'

export function TransactionsTab() {
  const [transactions, setTransactions] = useState<any[]>([])
  const [search, setSearch] = useState('')

  useEffect(() => { fetchTransactions().then(setTransactions) }, [])

  const filtered = transactions.filter(t =>
    ((t.marchand ?? '') + (t.description ?? '')).toLowerCase().includes(search.toLowerCase())
  )

  return (
    <div className="space-y-4">
      <input
        type="text"
        placeholder="Rechercher…"
        value={search}
        onChange={e => setSearch(e.target.value)}
        className="w-full rounded-lg border border-[var(--border)] bg-transparent px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-[var(--ring)]"
      />
      <div className="rounded-lg border border-[var(--border)] overflow-hidden">
        {filtered.slice(0, 50).map((t: any, i: number) => (
          <div
            key={t.id}
            className={`flex justify-between items-center px-4 py-3 text-sm hover:bg-[var(--accent)] transition-colors ${i !== 0 ? 'border-t border-[var(--border)]' : ''}`}
          >
            <div className="flex gap-4 min-w-0">
              <span className="text-[var(--muted-foreground)] shrink-0 w-24">{t.date}</span>
              <span className="truncate">{t.marchand || t.description}</span>
            </div>
            <span className={`font-mono shrink-0 ml-4 ${t.montant >= 0 ? 'text-emerald-600' : ''}`}>
              {t.montant >= 0 ? '+' : ''}{t.montant?.toFixed(2)}
            </span>
          </div>
        ))}
        {filtered.length === 0 && (
          <div className="px-4 py-6 text-center text-sm text-[var(--muted-foreground)]">
            Aucune transaction trouvée.
          </div>
        )}
      </div>
    </div>
  )
}
