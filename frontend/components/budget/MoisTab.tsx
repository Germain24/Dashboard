'use client'
import { useEffect, useState } from 'react'
import {
  fetchSummary, fetchEnvelopes, fetchCategories, fetchByCategory, fetchTrend,
  type CategorySpend, type MonthTrend,
} from '@/lib/budget'

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
  const [byCat, setByCat] = useState<CategorySpend[]>([])
  const [trend, setTrend] = useState<MonthTrend[]>([])
  const [loading, setLoading] = useState(true)
  const month = new Date().toISOString().slice(0, 7)

  useEffect(() => {
    void Promise.all([
      fetchSummary(month).then(d => d && !d.detail ? d : null),
      fetchEnvelopes(month).then(d => Array.isArray(d) ? d : []),
      fetchCategories().then(d => Array.isArray(d) ? d : []),
      fetchByCategory(month),
      fetchTrend(6),
    ]).then(([s, e, c, bc, tr]) => {
      setSummary(s)
      setEnvelopes(e)
      setCategories(c)
      setByCat(bc)
      setTrend(tr)
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

  const over = envelopes.filter((e: any) => e.status === 'over')
  const warn = envelopes.filter((e: any) => e.status === 'warning')

  return (
    <div className="space-y-6">
      {/* Alerte de dépassement (#114) */}
      {(over.length > 0 || warn.length > 0) && (
        <div
          className="rounded-xl border p-3 text-sm animate-fade-in-up"
          style={{
            borderColor: over.length ? 'var(--destructive)' : 'var(--warning)',
            background: `color-mix(in srgb, ${over.length ? 'var(--destructive)' : 'var(--warning)'} 10%, transparent)`,
          }}
        >
          <p className="font-medium" style={{ color: over.length ? 'var(--destructive)' : 'var(--warning)' }}>
            {over.length > 0
              ? `⚠ ${over.length} catégorie${over.length > 1 ? 's' : ''} dépassée${over.length > 1 ? 's' : ''}`
              : `${warn.length} catégorie${warn.length > 1 ? 's' : ''} proche${warn.length > 1 ? 's' : ''} de la limite`}
          </p>
          <p className="mt-0.5 text-[var(--muted-foreground)]">
            {[...over, ...warn].map((e: any) => catName(e.category_id)).join(' · ')}
          </p>
        </div>
      )}

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

      {/* Dépenses par catégorie (camembert) + tendance mensuelle (#113) */}
      <div className="grid gap-4 md:grid-cols-2">
        <div className="rounded-xl border border-[var(--border)] bg-[var(--card)] p-4 animate-fade-in-up">
          <h2 className="text-sm font-semibold mb-3">Dépenses par catégorie</h2>
          <Donut data={byCat} />
        </div>
        <div className="rounded-xl border border-[var(--border)] bg-[var(--card)] p-4 animate-fade-in-up">
          <div className="flex items-center justify-between mb-3">
            <h2 className="text-sm font-semibold">Tendance (6 mois)</h2>
            <div className="flex items-center gap-3 text-xs text-[var(--muted-foreground)]">
              <span className="flex items-center gap-1"><span className="w-2 h-2 rounded-sm bg-[var(--success)]" />Revenus</span>
              <span className="flex items-center gap-1"><span className="w-2 h-2 rounded-sm bg-[var(--destructive)]" />Dépenses</span>
            </div>
          </div>
          <TrendChart data={trend} />
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
              const status = env.status ?? ((env.pct ?? 0) > 100 ? 'over' : 'ok')
              const over = status === 'over'
              const barColor = over ? 'var(--destructive)' : status === 'warning' ? 'var(--warning)' : color
              return (
                <div key={env.category_id} className="px-4 py-3 hover:bg-[var(--muted)] transition-colors duration-150">
                  <div className="flex items-center justify-between mb-1.5">
                    <div className="flex items-center gap-2">
                      <span className="w-2.5 h-2.5 rounded-full flex-shrink-0" style={{ background: color }} />
                      <span className="text-sm font-medium">{catName(env.category_id)}</span>
                    </div>
                    <div className="flex items-center gap-3 text-sm">
                      <span
                        className={over || status === 'warning' ? 'font-medium' : 'text-[var(--foreground)]'}
                        style={over ? { color: 'var(--destructive)' } : status === 'warning' ? { color: 'var(--warning)' } : undefined}
                      >
                        {formatCAD(env.depense ?? 0)}
                      </span>
                      <span className="text-[var(--muted-foreground)] text-xs">/ {formatCAD(env.budget ?? 0)}</span>
                    </div>
                  </div>
                  <div className="h-1.5 rounded-full bg-[var(--muted)] overflow-hidden">
                    <div
                      className="h-full rounded-full transition-all duration-500"
                      style={{ width: `${pct}%`, background: barColor }}
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

function Donut({ data }: { data: CategorySpend[] }) {
  const total = data.reduce((s, d) => s + d.montant, 0)
  if (total <= 0) {
    return <p className="text-sm text-[var(--muted-foreground)]">Aucune dépense ce mois-ci.</p>
  }
  const r = 52
  const C = 2 * Math.PI * r
  const segs = data.map((d, i) => ({
    couleur: d.couleur,
    dash: (d.montant / total) * C,
    offset: data.slice(0, i).reduce((s, p) => s + (p.montant / total) * C, 0),
  }))
  const centre = new Intl.NumberFormat('fr-CA', {
    style: 'currency', currency: 'CAD', maximumFractionDigits: 0,
  }).format(total)

  return (
    <div className="flex flex-wrap items-center gap-5">
      <svg width="140" height="140" viewBox="0 0 140 140" className="shrink-0"
        role="img" aria-label="Répartition des dépenses par catégorie">
        <g transform="rotate(-90 70 70)">
          {segs.map((s, i) => (
            <circle key={i} cx="70" cy="70" r={r} fill="none" stroke={s.couleur} strokeWidth="16"
              strokeDasharray={`${s.dash} ${C - s.dash}`} strokeDashoffset={-s.offset} />
          ))}
        </g>
        <text x="70" y="67" textAnchor="middle" fontSize="14" fontWeight="600" fill="var(--foreground)">{centre}</text>
        <text x="70" y="83" textAnchor="middle" fontSize="10" fill="var(--muted-foreground)">dépensé</text>
      </svg>
      <ul className="min-w-[160px] flex-1 space-y-1 text-sm">
        {data.map((d) => (
          <li key={String(d.category_id)} className="flex items-center gap-2">
            <span className="h-2.5 w-2.5 shrink-0 rounded-full" style={{ background: d.couleur }} />
            <span className="flex-1 truncate">{d.nom}</span>
            <span className="tabular-nums text-[var(--muted-foreground)]">{d.pct}%</span>
            <span className="w-20 text-right tabular-nums">{formatCAD(d.montant)}</span>
          </li>
        ))}
      </ul>
    </div>
  )
}

function TrendChart({ data }: { data: MonthTrend[] }) {
  if (data.length === 0) {
    return <p className="text-sm text-[var(--muted-foreground)]">Pas de données.</p>
  }
  const max = Math.max(1, ...data.flatMap((d) => [d.depenses, d.revenus]))
  return (
    <div className="flex h-40 items-end gap-3">
      {data.map((d) => (
        <div key={d.mois} className="flex flex-1 flex-col items-center gap-1">
          <div className="flex h-32 w-full items-end justify-center gap-0.5">
            <div className="w-3 rounded-t bg-[var(--success)]" style={{ height: `${(d.revenus / max) * 100}%` }}
              title={`Revenus ${formatCAD(d.revenus)}`} />
            <div className="w-3 rounded-t bg-[var(--destructive)]" style={{ height: `${(d.depenses / max) * 100}%` }}
              title={`Dépenses ${formatCAD(d.depenses)}`} />
          </div>
          <span className="text-[10px] tabular-nums text-[var(--muted-foreground)]">{d.mois.slice(5)}</span>
        </div>
      ))}
    </div>
  )
}
