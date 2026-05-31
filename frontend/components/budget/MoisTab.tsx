'use client'
import { useEffect, useState } from 'react'
import { fetchSummary, fetchTransactions } from '@/lib/budget'

export function MoisTab() {
  const [summary, setSummary] = useState<any>(null)
  const [transactions, setTransactions] = useState<any[]>([])
  const month = new Date().toISOString().slice(0, 7)

  useEffect(() => {
    fetchSummary(month).then(setSummary)
    fetchTransactions({ from: month + '-01' }).then(setTransactions)
  }, [month])

  if (!summary) {
    return (
      <div className="space-y-4 animate-pulse">
        <div className="grid grid-cols-3 gap-4">
          {[0, 1, 2].map(i => (
            <div key={i} className="h-20 rounded-lg bg-[var(--muted)]" />
          ))}
        </div>
        <div className="h-48 rounded-lg bg-[var(--muted)]" />
      </div>
    )
  }

  return (
    <div className="space-y-6">
      <div className="grid grid-cols-3 gap-4">
        <div className="rounded-lg border border-[var(--border)] p-4">
          <div className="text-sm text-[var(--muted-foreground)]">Revenus</div>
          <div className="text-2xl font-mono text-emerald-600">{summary.revenus?.toFixed(2)} CAD</div>
        </div>
        <div className="rounded-lg border border-[var(--border)] p-4">
          <div className="text-sm text-[var(--muted-foreground)]">Dépenses</div>
          <div className="text-2xl font-mono text-red-500">{Math.abs(summary.depenses ?? 0).toFixed(2)} CAD</div>
        </div>
        <div className="rounded-lg border border-[var(--border)] p-4">
          <div className="text-sm text-[var(--muted-foreground)]">Solde</div>
          <div className={`text-2xl font-mono ${(summary.solde ?? 0) >= 0 ? 'text-emerald-600' : 'text-red-500'}`}>
            {summary.solde?.toFixed(2)} CAD
          </div>
        </div>
      </div>

      <div className="space-y-2">
        <h3 className="text-sm font-medium text-[var(--muted-foreground)]">Transactions récentes</h3>
        <div className="rounded-lg border border-[var(--border)] overflow-hidden">
          {transactions.slice(0, 10).map((t: any, i: number) => (
            <div
              key={t.id}
              className={`flex justify-between items-center px-4 py-3 text-sm ${i !== 0 ? 'border-t border-[var(--border)]' : ''}`}
            >
              <div>
                <div className="font-medium">{t.marchand || t.description}</div>
                <div className="text-xs text-[var(--muted-foreground)]">{t.date}</div>
              </div>
              <div className={`font-mono ${t.montant >= 0 ? 'text-emerald-600' : 'text-[var(--foreground)]'}`}>
                {t.montant >= 0 ? '+' : ''}{t.montant?.toFixed(2)}
              </div>
            </div>
          ))}
          {transactions.length === 0 && (
            <div className="px-4 py-6 text-center text-sm text-[var(--muted-foreground)]">
              Aucune transaction ce mois-ci.
            </div>
          )}
        </div>
      </div>
    </div>
  )
}
