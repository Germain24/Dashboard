'use client'

import { ArrowDownLeft, ArrowUpRight } from 'lucide-react'

const formatCAD = (v: number) =>
  new Intl.NumberFormat('fr-CA', { style: 'currency', currency: 'CAD' }).format(v ?? 0)

const MOCK_TRANSACTIONS = [
  { id: 1, date: '2026-05-30', description: 'Épicerie Metro', categorie: 'Épicerie', montant: -87.45, type: 'depense' },
  { id: 2, date: '2026-05-29', description: 'Salaire', categorie: 'Revenus', montant: 3200.0, type: 'revenu' },
  { id: 3, date: '2026-05-28', description: 'Netflix', categorie: 'Abonnements', montant: -17.99, type: 'depense' },
  { id: 4, date: '2026-05-27', description: 'Restaurant La Bella', categorie: 'Restaurants', montant: -42.50, type: 'depense' },
  { id: 5, date: '2026-05-26', description: 'STM mensuel', categorie: 'Transport', montant: -97.0, type: 'depense' },
  { id: 6, date: '2026-05-25', description: 'Loyer mai', categorie: 'Loyer', montant: -900.0, type: 'depense' },
  { id: 7, date: '2026-05-24', description: 'IGA', categorie: 'Épicerie', montant: -63.22, type: 'depense' },
]

export default function TransactionsTab() {
  return (
    <div className="space-y-4 animate-fade-in-up">
      <div className="rounded-xl border border-[var(--border)] bg-[var(--card)] overflow-hidden">
        <div className="px-4 py-3 border-b border-[var(--border)]">
          <h2 className="text-sm font-semibold">Transactions récentes</h2>
          <p className="text-xs text-[var(--muted-foreground)] mt-0.5">Mai 2026</p>
        </div>
        <div className="divide-y divide-[var(--border)]">
          {MOCK_TRANSACTIONS.map((tx) => (
            <div key={tx.id} className="flex items-center gap-3 px-4 py-3 hover:bg-[var(--muted)] transition-colors duration-150">
              <div className={`w-8 h-8 rounded-full flex items-center justify-center flex-shrink-0 ${
                tx.type === 'revenu'
                  ? 'bg-[color-mix(in_srgb,var(--success)_15%,transparent)]'
                  : 'bg-[color-mix(in_srgb,var(--destructive)_10%,transparent)]'
              }`}>
                {tx.type === 'revenu'
                  ? <ArrowDownLeft size={14} className="text-[var(--success)]" />
                  : <ArrowUpRight size={14} className="text-[var(--destructive)]" />
                }
              </div>
              <div className="flex-1 min-w-0">
                <p className="text-sm font-medium truncate">{tx.description}</p>
                <p className="text-xs text-[var(--muted-foreground)]">{tx.categorie} · {tx.date}</p>
              </div>
              <span className={`text-sm font-mono font-semibold ${
                tx.type === 'revenu' ? 'text-[var(--success)]' : 'text-[var(--foreground)]'
              }`}>
                {tx.montant > 0 ? '+' : ''}{formatCAD(tx.montant)}
              </span>
            </div>
          ))}
        </div>
      </div>

      <div className="rounded-xl border border-dashed border-[var(--border)] p-6 text-center">
        <p className="text-sm text-[var(--muted-foreground)]">
          Les transactions réelles seront importées depuis le backend Budget.
        </p>
      </div>
    </div>
  )
}
