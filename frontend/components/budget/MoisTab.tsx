'use client'
import { useState } from 'react'
import {
  useBudgetCategories, useBudgetComparison, useBudgetSummary, useByCategory, useEnvelopes,
  useRecurring, useRecurringProjection, useSavingsGoal, useSetSavingsGoal, useTrend,
} from '@/lib/queries/budget'
import type { Comparison } from '@/lib/budget'
import { Donut, TrendChart } from './charts'

const formatCAD = (v: number) =>
  new Intl.NumberFormat('fr-CA', { style: 'currency', currency: 'CAD' }).format(v ?? 0)

const CATEGORY_COLORS = [
  '#6366f1', '#22c55e', '#f59e0b', '#ef4444',
  '#8b5cf6', '#06b6d4', '#71717a', '#ec4899', '#84cc16',
]

export default function MoisTab() {
  const [goalInput, setGoalInput] = useState('')
  const month = new Date().toISOString().slice(0, 7)

  const summaryQ = useBudgetSummary(month)
  const comparisonQ = useBudgetComparison(month)
  const envelopesQ = useEnvelopes(month)
  const categoriesQ = useBudgetCategories()
  const byCatQ = useByCategory(month)
  const trendQ = useTrend(6)
  const recurringQ = useRecurring()
  const projectionQ = useRecurringProjection()
  const savingsQ = useSavingsGoal()
  const setGoalMutation = useSetSavingsGoal()

  const summary = summaryQ.data && !summaryQ.data.detail ? summaryQ.data : null
  const envelopes: any[] = Array.isArray(envelopesQ.data) ? envelopesQ.data : []
  const categories: any[] = Array.isArray(categoriesQ.data) ? categoriesQ.data : []
  const byCat = byCatQ.data ?? []
  const trend = trendQ.data ?? []
  const recurring = recurringQ.data ?? []
  const savings = savingsQ.data ?? null
  const loading =
    summaryQ.isLoading || envelopesQ.isLoading || categoriesQ.isLoading ||
    byCatQ.isLoading || trendQ.isLoading || recurringQ.isLoading || savingsQ.isLoading

  const saveGoal = () => {
    const m = parseFloat(goalInput)
    if (!Number.isFinite(m) || m < 0) return
    setGoalMutation.mutate(m, { onSuccess: () => setGoalInput('') })
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
          <p className="mb-1 text-xs font-medium text-[var(--muted-foreground)]">Reste à vivre</p>
          <p className={`font-display text-3xl tabular-nums ${reste >= 0 ? 'text-[var(--foreground)]' : 'text-[var(--destructive)]'}`}>
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
          <p className="text-xs font-medium text-[var(--muted-foreground)] mb-1">Revenus</p>
          <p className="font-display text-[1.75rem] leading-tight tabular-nums text-[var(--success)]">{formatCAD(s.revenus)}</p>
          <Delta cmp={comparisonQ.data?.revenus} favorableWhen="up" />
        </div>
        <div className="rounded-xl border border-[var(--border)] bg-[var(--card)] p-4 card-hover animate-fade-in-up">
          <p className="text-xs font-medium text-[var(--muted-foreground)] mb-1">Dépenses</p>
          <p className="font-display text-[1.75rem] leading-tight tabular-nums text-[var(--destructive)]">{formatCAD(Math.abs(s.depenses))}</p>
          <Delta cmp={comparisonQ.data?.depenses} favorableWhen="down" />
          {s.revenus > 0 && <p className="text-xs text-[var(--muted-foreground)] mt-1">{depensesPct}% des revenus</p>}
        </div>
        <div className="rounded-xl border border-[var(--border)] bg-[var(--card)] p-4 card-hover animate-fade-in-up">
          <p className="text-xs font-medium text-[var(--muted-foreground)] mb-1">Solde</p>
          <p className={`font-display text-[1.75rem] leading-tight tabular-nums ${s.solde >= 0 ? 'text-[var(--success)]' : 'text-[var(--destructive)]'}`}>
            {formatCAD(s.solde)}
          </p>
          <Delta cmp={comparisonQ.data?.solde} favorableWhen="up" />
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
          <p className="mb-1 text-xs font-medium text-[var(--muted-foreground)]">Courses ce mois</p>
          <p className="font-display text-xl tabular-nums">{formatCAD(groceryCost)}</p>
          <p className="mt-1 text-xs text-[var(--muted-foreground)]">Planifier dans Cuisine →</p>
        </a>
        <a href="/finance"
          className="rounded-xl border border-[var(--border)] bg-[var(--card)] p-4 transition-colors hover:bg-[var(--muted)] animate-fade-in-up">
          <p className="mb-1 text-xs font-medium text-[var(--muted-foreground)]">Épargne du mois (à investir)</p>
          <p className={`font-display text-xl tabular-nums ${reste >= 0 ? 'text-[var(--success)]' : 'text-[var(--destructive)]'}`}>{formatCAD(reste)}</p>
          <p className="mt-1 text-xs text-[var(--muted-foreground)]">Investir dans Finance →</p>
        </a>
      </div>

      {/* Abonnements récurrents détectés (#116) */}
      {recurring.length > 0 && (
        <div className="rounded-xl border border-[var(--border)] bg-[var(--card)] overflow-hidden animate-fade-in-up">
          <div className="flex items-center justify-between border-b border-[var(--border)] px-4 py-3">
            <div>
              <h2 className="text-sm font-semibold">Abonnements détectés</h2>
              <p className="mt-0.5 text-xs text-[var(--muted-foreground)]">
                Dépenses mensuelles récurrentes
                {projectionQ.data && projectionQ.data.projection_annuelle_recurrents > 0 && (
                  <> · ≈ <span className="font-medium text-[var(--foreground)]">{formatCAD(projectionQ.data.projection_annuelle_recurrents)}/an</span> projetés</>
                )}
              </p>
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

/** Variation vs mois précédent (#229). Couleur selon que la variation est
 *  favorable (revenus/solde : hausse = bien ; dépenses : baisse = bien). */
function Delta({ cmp, favorableWhen }: { cmp?: Comparison; favorableWhen: 'up' | 'down' }) {
  if (!cmp || cmp.direction === 'flat') return null
  const favorable = cmp.direction === favorableWhen
  const arrow = cmp.direction === 'up' ? '↑' : '↓'
  const pct = cmp.delta_pct == null ? null : Math.abs(cmp.delta_pct)
  return (
    <p
      className={`mt-1 text-xs tabular-nums ${favorable ? 'text-[var(--success)]' : 'text-[var(--destructive)]'}`}
      title={`${formatCAD(cmp.previous)} le mois précédent`}
    >
      {arrow} {pct == null ? '—' : `${pct.toFixed(0)}%`} vs mois préc.
    </p>
  )
}
