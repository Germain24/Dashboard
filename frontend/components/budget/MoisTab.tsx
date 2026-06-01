'use client'
import { useEffect, useState } from 'react'
import { fetchSummary, fetchEnvelopes, fetchCategories } from '@/lib/budget'

const formatCAD = (v: number) =>
  new Intl.NumberFormat('fr-CA', { style: 'currency', currency: 'CAD' }).format(v ?? 0)

const CATEGORY_COLORS = [
  '#6366f1', '#22c55e', '#f59e0b', '#ef4444',
  '#8b5cf6', '#06b6d4', '#71717a', '#ec4899', '#84cc16',
]

export default function MoisTab() {
  const [summary, setSummary] = useState<any>(null)
  const [envelopes, setEnvelopes] = useState<any[]>([])
  const [categories, setCategories] = useState<any[]>([])
  const [loading, setLoading] = useState(true)
  const month = new Date().toISOString().slice(0, 7)

  useEffect(() => {
    Promise.all([
      fetchSummary(month).then(d => d && !d.detail ? d : null),
      fetchEnvelopes(month).then(d => Array.isArray(d) ? d : []),
      fetchCategories().then(d => Array.isArray(d) ? d : []),
    ]).then(([s, e, c]) => {
      setSummary(s)
      setEnvelopes(e)
      setCategories(c)
      setLoading(false)
    })
  }, [month])

  const catName = (id: number) => categories.find((c: any) => c.id === id)?.nom ?? `#${id}`

  if (loading) {
    return (
      <div className="space-y-6">
        <div className="grid grid-cols-3 gap-4">
          {[0, 1, 2].map(i => (
            <div key={i} className="rounded-xl border border-[var(--border)] bg-[var(--card)] p-4 h-20 skeleton-shimmer" />
          ))}
        </div>
        <div className="rounded-xl border border-[var(--border)] bg-[var(--card)] h-48 skeleton-shimmer" />
      </div>
    )
  }

  const s = summary ?? { revenus: 0, depenses: 0, solde: 0 }
  const depensesPct = s.revenus > 0 ? Math.round((Math.abs(s.depenses) / s.revenus) * 100) : 0

  return (
    <div className="space-y-6">
      {/* Stats cards */}
      <div className="grid grid-cols-3 gap-4 stagger">
        <div className="rounded-xl border border-[var(--border)] bg-[var(--card)] p-4 card-hover animate-fade-in-up">
          <p className="text-xs font-medium text-[var(--muted-foreground)] uppercase tracking-wider mb-1">Revenus</p>
          <p className="text-2xl font-bold font-mono text-[var(--success)]">{formatCAD(s.revenus)}</p>
        </div>
        <div className="rounded-xl border border-[var(--border)] bg-[var(--card)] p-4 card-hover animate-fade-in-up">
          <p className="text-xs font-medium text-[var(--muted-foreground)] uppercase tracking-wider mb-1">Dépenses</p>
          <p className="text-2xl font-bold font-mono text-[var(--destructive)]">{formatCAD(Math.abs(s.depenses))}</p>
          {s.revenus > 0 && <p className="text-xs text-[var(--muted-foreground)] mt-1">{depensesPct}% des revenus</p>}
        </div>
        <div className="rounded-xl border border-[var(--border)] bg-[var(--card)] p-4 card-hover animate-fade-in-up">
          <p className="text-xs font-medium text-[var(--muted-foreground)] uppercase tracking-wider mb-1">Solde</p>
          <p className={`text-2xl font-bold font-mono ${s.solde >= 0 ? 'text-[var(--success)]' : 'text-[var(--destructive)]'}`}>
            {formatCAD(s.solde)}
          </p>
        </div>
      </div>

      {/* Enveloppes budgétaires */}
      {envelopes.length > 0 && (
        <div className="rounded-xl border border-[var(--border)] bg-[var(--card)] overflow-hidden animate-fade-in-up">
          <div className="px-4 py-3 border-b border-[var(--border)]">
            <h2 className="text-sm font-semibold">Enveloppes budgétaires</h2>
            <p className="text-xs text-[var(--muted-foreground)] mt-0.5">{month}</p>
          </div>
          <div className="divide-y divide-[var(--border)]">
            {envelopes.map((env: any, i: number) => {
              const color = CATEGORY_COLORS[i % CATEGORY_COLORS.length]
              const pct = Math.min(env.pct ?? 0, 100)
              const over = (env.pct ?? 0) > 100
              return (
                <div key={env.category_id} className="px-4 py-3 hover:bg-[var(--muted)] transition-colors duration-150">
                  <div className="flex items-center justify-between mb-1.5">
                    <div className="flex items-center gap-2">
                      <span className="w-2.5 h-2.5 rounded-full flex-shrink-0" style={{ background: color }} />
                      <span className="text-sm font-medium">{catName(env.category_id)}</span>
                    </div>
                    <div className="flex items-center gap-3 text-sm">
                      <span className={over ? 'text-[var(--destructive)] font-medium' : 'text-[var(--foreground)]'}>
                        {formatCAD(env.depense ?? 0)}
                      </span>
                      <span className="text-[var(--muted-foreground)] text-xs">/ {formatCAD(env.budget ?? 0)}</span>
                    </div>
                  </div>
                  <div className="h-1.5 rounded-full bg-[var(--muted)] overflow-hidden">
                    <div
                      className="h-full rounded-full transition-all duration-500"
                      style={{ width: `${pct}%`, background: over ? 'var(--destructive)' : color }}
                    />
                  </div>
                </div>
              )
            })}
          </div>
        </div>
      )}

      {envelopes.length === 0 && (
        <div className="rounded-xl border border-dashed border-[var(--border)] p-6 text-center animate-fade-in-up">
          <p className="text-sm text-[var(--muted-foreground)]">
            Aucune enveloppe définie pour {month}. Créez-en dans l'onglet Enveloppes.
          </p>
        </div>
      )}
    </div>
  )
}
