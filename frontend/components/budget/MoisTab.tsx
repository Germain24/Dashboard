'use client'
import { useEffect, useState } from 'react'
import {
  fetchSummary, fetchEnvelopes, fetchCategories, fetchByCategory, fetchTrend, fetchRecurring,
  fetchSavingsGoal, setSavingsGoal,
  type CategorySpend, type MonthTrend, type Recurring, type SavingsGoal,
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
  const [recurring, setRecurring] = useState<Recurring[]>([])
  const [savings, setSavings] = useState<SavingsGoal | null>(null)
  const [goalInput, setGoalInput] = useState('')
  const [loading, setLoading] = useState(true)
  const month = new Date().toISOString().slice(0, 7)

  useEffect(() => {
    void Promise.all([
      fetchSummary(month).then(d => d && !d.detail ? d : null),
      fetchEnvelopes(month).then(d => Array.isArray(d) ? d : []),
      fetchCategories().then(d => Array.isArray(d) ? d : []),
      fetchByCategory(month),
      fetchTrend(6),
      fetchRecurring(),
      fetchSavingsGoal(),
    ]).then(([s, e, c, bc, tr, rec, sav]) => {
      setSummary(s)
      setEnvelopes(e)
      setCategories(c)
      setByCat(bc)
      setTrend(tr)
      setRecurring(rec)
      setSavings(sav)
      setLoading(false)
    })
  }, [month])

  const saveGoal = () => {
    const m = parseFloat(goalInput)
    if (!Number.isFinite(m) || m < 0) return
    void setSavingsGoal(m).then(() => fetchSavingsGoal()).then((sav) => { setSavings(sav); setGoalInput('') })
  }

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

  // Reste à vivre (#117) : ce qu'il reste après dépenses, et le budget/jour restant.
  const now = new Date()
  const daysInMonth = new Date(now.getFullYear(), now.getMonth() + 1, 0).getDate()
  const daysLeft = Math.max(1, daysInMonth - now.getDate() + 1)
  const reste = s.solde
  const perDay = reste > 0 ? reste / daysLeft : 0

  // Lien Cuisine (#120) : dépenses « courses » du mois (catégories alimentaires).
  const GROCERY = ['épicerie', 'epicerie', 'courses', 'alimentation', 'cuisine', 'supermarch', 'grocery']
  const groceryCost = byCat
    .filter((c) => GROCERY.some((g) => c.nom.toLowerCase().includes(g)))
    .reduce((sum, c) => sum + c.montant, 0)

  // Comparaison mois sur mois des dépenses (#118)
  const lastTwo = trend.slice(-2)
  const momPct = lastTwo.length === 2 && lastTwo[0].depenses > 0
    ? Math.round(((lastTwo[1].depenses - lastTwo[0].depenses) / lastTwo[0].depenses) * 100)
    : null

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

      {/* Reste à vivre (#117) */}
      <div className="flex flex-wrap items-center justify-between gap-3 rounded-xl border border-[var(--border)] bg-[var(--card)] p-4 animate-fade-in-up">
        <div>
          <p className="mb-1 text-xs font-medium uppercase tracking-wider text-[var(--muted-foreground)]">Reste à vivre</p>
          <p className={`font-mono text-3xl font-bold ${reste >= 0 ? 'text-[var(--foreground)]' : 'text-[var(--destructive)]'}`}>
            {formatCAD(reste)}
          </p>
        </div>
        <div className="text-right text-sm text-[var(--muted-foreground)]">
          {reste > 0 ? (
            <>
              <p className="font-mono text-[var(--foreground)]">{formatCAD(perDay)}<span className="text-xs"> / jour</span></p>
              <p className="text-xs">sur {daysLeft} jour{daysLeft > 1 ? 's' : ''} restant{daysLeft > 1 ? 's' : ''}</p>
            </>
          ) : (
            <p className="text-xs">Budget du mois dépassé</p>
          )}
        </div>
      </div>

      {/* Objectif d'épargne mensuel (#121) */}
      {savings && (
        <div className="rounded-xl border border-[var(--border)] bg-[var(--card)] p-4 animate-fade-in-up">
          <div className="mb-2 flex flex-wrap items-center justify-between gap-2">
            <h2 className="text-sm font-semibold">Objectif d'épargne mensuel</h2>
            <div className="flex items-center gap-1">
              <input
                type="number" step="50" min="0"
                placeholder={savings.objectif > 0 ? String(savings.objectif) : 'montant'}
                value={goalInput} onChange={(e) => setGoalInput(e.target.value)}
                aria-label="Objectif d'épargne (CAD)"
                className="w-24 rounded border border-[var(--border)] bg-transparent px-2 py-1 text-sm"
              />
              <button onClick={saveGoal}
                className="rounded bg-[var(--primary)] px-2 py-1 text-xs font-medium text-[var(--primary-foreground)] hover:opacity-90">
                Définir
              </button>
            </div>
          </div>
          {savings.objectif > 0 ? (
            <>
              <div className="mb-1.5 flex items-center justify-between text-sm">
                <span className="font-mono">{formatCAD(savings.epargne)}</span>
                <span className="text-xs text-[var(--muted-foreground)]">/ {formatCAD(savings.objectif)} · {savings.progress_pct}%</span>
              </div>
              <div className="h-1.5 overflow-hidden rounded-full bg-[var(--muted)]">
                <div className="h-full rounded-full transition-all duration-500"
                  style={{ width: `${Math.min(100, savings.progress_pct)}%`, background: savings.progress_pct >= 100 ? 'var(--success)' : 'var(--ring)' }} />
              </div>
            </>
          ) : (
            <p className="text-xs text-[var(--muted-foreground)]">Aucun objectif défini. Saisis un montant à épargner ce mois.</p>
          )}
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
          <div className="flex items-center justify-between mb-3 gap-2 flex-wrap">
            <div className="flex items-baseline gap-2">
              <h2 className="text-sm font-semibold">Tendance (6 mois)</h2>
              {momPct !== null && (
                <span
                  className="text-xs font-medium"
                  style={{ color: momPct > 0 ? 'var(--destructive)' : momPct < 0 ? 'var(--success)' : 'var(--muted-foreground)' }}
                  title="Dépenses vs mois précédent"
                >
                  {momPct > 0 ? '+' : ''}{momPct}% vs mois dernier
                </span>
              )}
            </div>
            <div className="flex items-center gap-3 text-xs text-[var(--muted-foreground)]">
              <span className="flex items-center gap-1"><span className="w-2 h-2 rounded-sm bg-[var(--success)]" />Revenus</span>
              <span className="flex items-center gap-1"><span className="w-2 h-2 rounded-sm bg-[var(--destructive)]" />Dépenses</span>
              <span className="flex items-center gap-1"><span className="w-3 h-0.5 bg-[var(--ring)]" />Moy. 3 mois</span>
            </div>
          </div>
          <TrendChart data={trend} />
        </div>
      </div>

      {/* Liens inter-modules (#120) : Cuisine (coût des courses) + Finance (épargne) */}
      <div className="grid gap-4 sm:grid-cols-2">
        <a href="/cuisine"
          className="rounded-xl border border-[var(--border)] bg-[var(--card)] p-4 transition-colors hover:bg-[var(--muted)] animate-fade-in-up">
          <p className="mb-1 text-xs font-medium uppercase tracking-wider text-[var(--muted-foreground)]">Courses ce mois</p>
          <p className="font-mono text-xl font-bold">{formatCAD(groceryCost)}</p>
          <p className="mt-1 text-xs text-[var(--muted-foreground)]">Planifier dans Cuisine →</p>
        </a>
        <a href="/finance"
          className="rounded-xl border border-[var(--border)] bg-[var(--card)] p-4 transition-colors hover:bg-[var(--muted)] animate-fade-in-up">
          <p className="mb-1 text-xs font-medium uppercase tracking-wider text-[var(--muted-foreground)]">Épargne du mois (à investir)</p>
          <p className={`font-mono text-xl font-bold ${reste >= 0 ? 'text-[var(--success)]' : 'text-[var(--destructive)]'}`}>{formatCAD(reste)}</p>
          <p className="mt-1 text-xs text-[var(--muted-foreground)]">Investir dans Finance →</p>
        </a>
      </div>

      {/* Abonnements récurrents détectés (#116) */}
      {recurring.length > 0 && (
        <div className="rounded-xl border border-[var(--border)] bg-[var(--card)] overflow-hidden animate-fade-in-up">
          <div className="flex items-center justify-between border-b border-[var(--border)] px-4 py-3">
            <div>
              <h2 className="text-sm font-semibold">Abonnements détectés</h2>
              <p className="mt-0.5 text-xs text-[var(--muted-foreground)]">Dépenses mensuelles récurrentes</p>
            </div>
            <span className="text-sm font-mono font-semibold">
              {formatCAD(recurring.reduce((s, r) => s + r.montant_moyen, 0))}<span className="text-xs text-[var(--muted-foreground)]"> /mois</span>
            </span>
          </div>
          <div className="divide-y divide-[var(--border)]">
            {recurring.map((r) => (
              <div key={r.marchand} className="flex items-center gap-3 px-4 py-2.5">
                <span className="flex-1 truncate text-sm font-medium">{r.marchand}</span>
                <span className="text-xs text-[var(--muted-foreground)]">{r.occurrences}× · dès {r.derniere_date}</span>
                <span className="w-24 text-right font-mono text-sm tabular-nums">{formatCAD(r.montant_moyen)}</span>
              </div>
            ))}
          </div>
        </div>
      )}

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
  const n = data.length
  // Moyenne mobile 3 mois des dépenses (#118)
  const ma = data.map((_, i) => {
    const w = data.slice(Math.max(0, i - 2), i + 1)
    return w.reduce((sum, x) => sum + x.depenses, 0) / w.length
  })
  const maPts = ma.map((v, i) => `${((i + 0.5) / n) * 100},${100 - (v / max) * 100}`).join(' ')

  return (
    <div>
      <div className="relative h-32">
        <div className="flex h-full items-end gap-3">
          {data.map((d) => (
            <div key={d.mois} className="flex flex-1 items-end justify-center gap-0.5">
              <div className="w-3 rounded-t bg-[var(--success)]" style={{ height: `${(d.revenus / max) * 100}%` }}
                title={`Revenus ${formatCAD(d.revenus)}`} />
              <div className="w-3 rounded-t bg-[var(--destructive)]" style={{ height: `${(d.depenses / max) * 100}%` }}
                title={`Dépenses ${formatCAD(d.depenses)}`} />
            </div>
          ))}
        </div>
        <svg className="pointer-events-none absolute inset-0 h-full w-full" viewBox="0 0 100 100" preserveAspectRatio="none"
          role="img" aria-label="Moyenne mobile 3 mois des dépenses">
          <polyline points={maPts} fill="none" stroke="var(--ring)" strokeWidth={1} vectorEffect="non-scaling-stroke"
            strokeLinejoin="round" strokeLinecap="round" />
        </svg>
      </div>
      <div className="mt-1 flex gap-3">
        {data.map((d) => (
          <span key={d.mois} className="flex-1 text-center text-[10px] tabular-nums text-[var(--muted-foreground)]">
            {d.mois.slice(5)}
          </span>
        ))}
      </div>
    </div>
  )
}
