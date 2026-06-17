'use client'

import { useState } from 'react'
import { Activity, HeartPulse, TrendingUp, Lightbulb, Target } from 'lucide-react'
import { ModuleHeader, type ModuleTab } from '@/components/layout'
import { ErrorBoundary } from '@/components/ErrorBoundary'
import { useWellbeing, useSnapshots } from '@/lib/queries/snapshot'
import { useWeeklyInsights, useCorrelations, useRecommendations, useForecasts, useSurcharge } from '@/lib/queries/routines'
import { ObjectifsVie } from '@/components/ObjectifsVie'

type TabId = 'synthese' | 'recos' | 'objectifs' | 'analyse'

const TABS: ModuleTab[] = [
  { id: 'synthese', label: 'Synthèse', icon: HeartPulse },
  { id: 'recos', label: 'Recommandations', icon: Lightbulb },
  { id: 'objectifs', label: 'Objectifs de vie', icon: Target },
  { id: 'analyse', label: 'Analyse', icon: TrendingUp },
]

/** Tableau de bord « Vue 360 » (#225) : synthèse de toute ta vie sur un écran. */
function Vue360Content({ active }: { active: TabId }) {
  const { data: wb } = useWellbeing()
  const { data: insights } = useWeeklyInsights()
  const { data: corr } = useCorrelations()
  const { data: snaps } = useSnapshots(1)
  const today = snaps?.[0]?.data

  return (
    <div className="space-y-6">
      {active === 'synthese' && (
        <>
          {/* Bien-être global (#222) */}
          <section className="rounded-[var(--radius-lg)] border border-[var(--glass-border)] bg-[var(--card)] p-5">
            <h2 className="mb-3 flex items-center gap-1.5 text-xs font-semibold text-[var(--muted-foreground)]">
              <HeartPulse size={13} /> Bien-être global
            </h2>
            {wb ? (
              <div className="flex flex-wrap items-center gap-6">
                <div>
                  <div className="font-display text-4xl text-[var(--foreground)]">{Math.round(wb.score)}<span className="text-lg text-[var(--muted-foreground)]">/100</span></div>
                  <div className="text-sm text-[var(--muted-foreground)]">{wb.label}</div>
                </div>
                <div className="grid grid-cols-2 gap-x-6 gap-y-1 text-sm sm:grid-cols-4">
                  {Object.entries(wb.components).map(([k, v]) => (
                    <div key={k}>
                      <div className="text-xs capitalize text-[var(--muted-foreground)]">{k}</div>
                      <div className="tabular-nums text-[var(--foreground)]">{Math.round(v)}</div>
                    </div>
                  ))}
                </div>
              </div>
            ) : (
              <p className="text-sm text-[var(--muted-foreground)]">Pas encore de données.</p>
            )}
          </section>

          {/* Aujourd'hui en bref */}
          {today && (
            <section className="rounded-[var(--radius-lg)] border border-[var(--glass-border)] bg-[var(--card)] p-5">
              <h2 className="mb-3 text-xs font-semibold text-[var(--muted-foreground)]">Aujourd&apos;hui en bref</h2>
              <div className="grid grid-cols-2 gap-3 text-sm sm:grid-cols-4">
                {today.habitudes && <Metric label="Habitudes" value={`${today.habitudes.pct}%`} />}
                {today.humeur && <Metric label="Humeur" value={`${today.humeur.valeur}/10`} />}
                {today.sante?.poids != null && <Metric label="Poids" value={`${today.sante.poids} kg`} />}
                {today.budget && <Metric label="Dépenses" value={`${today.budget.depenses_total} $`} />}
              </div>
            </section>
          )}
        </>
      )}

      {active === 'recos' && (
        <>
          {/* Recommandations priorisées (#227) */}
          <RecommendationsSection />
          {/* Surcharge (#231) */}
          <SurchargeSection />
        </>
      )}

      {active === 'objectifs' && (
        /* Objectifs de vie inter-modules (#226) */
        <ObjectifsVie />
      )}

      {active === 'analyse' && (
        <>
          {/* Projections de tendances (#228) */}
          <ForecastsSection />

          {/* Insights de la semaine (#223) */}
          <section className="rounded-[var(--radius-lg)] border border-[var(--glass-border)] bg-[var(--card)] p-5">
            <h2 className="mb-3 flex items-center gap-1.5 text-xs font-semibold text-[var(--muted-foreground)]">
              <TrendingUp size={13} /> Insights de la semaine
            </h2>
            <div className="grid gap-3 sm:grid-cols-3">
              {([['Réussites', insights?.reussites], ['Vigilance', insights?.vigilance], ['Tendances', insights?.tendances]] as const).map(([title, items]) => (
                <div key={title}>
                  <p className="mb-1 text-xs font-semibold text-[var(--muted-foreground)]">{title}</p>
                  {items && items.length > 0 ? (
                    <ul className="space-y-1">{items.map((m, i) => <li key={i} className="text-xs text-[var(--foreground)]">{m}</li>)}</ul>
                  ) : <p className="text-xs text-[var(--muted-foreground)]">—</p>}
                </div>
              ))}
            </div>
          </section>

          {/* Corrélations clés (#221) */}
          {corr && corr.correlations.length > 0 && (
            <section className="rounded-[var(--radius-lg)] border border-[var(--glass-border)] bg-[var(--card)] p-5">
              <h2 className="mb-3 flex items-center gap-1.5 text-xs font-semibold text-[var(--muted-foreground)]">
                <Activity size={13} /> Liens repérés (pas des causalités)
              </h2>
              <ul className="space-y-1.5">
                {corr.correlations.slice(0, 5).map((c) => (
                  <li key={`${c.a}-${c.b}`} className="flex items-center justify-between gap-3 text-sm">
                    <span className="min-w-0 truncate text-[var(--foreground)]">{c.a} ↔ {c.b} <span className="text-xs text-[var(--muted-foreground)]">{c.interpretation}</span></span>
                    <span className={`shrink-0 tabular-nums text-xs font-medium ${c.r >= 0 ? 'text-[var(--success-foreground)]' : 'text-[var(--warning-foreground)]'}`}>{c.r > 0 ? '+' : ''}{c.r.toFixed(2)}</span>
                  </li>
                ))}
              </ul>
            </section>
          )}
        </>
      )}
    </div>
  )
}

/** Détection de surcharge (#231). */
function SurchargeSection() {
  const { data } = useSurcharge()
  const jours = data?.jours ?? []
  if (!jours.length) return null
  const fmtDate = (iso: string) => new Date(iso + 'T12:00:00').toLocaleDateString('fr-CA', { weekday: 'long', day: '2-digit', month: '2-digit' })
  return (
    <section className="rounded-[var(--radius-lg)] border border-[var(--warning-muted)] bg-[var(--warning-muted)]/30 p-5">
      <h2 className="mb-3 flex items-center gap-1.5 text-xs font-semibold text-[var(--warning-foreground)]">
        <Activity size={13} /> Journées surchargées cette semaine
      </h2>
      <ul className="space-y-1.5">
        {jours.map((j) => (
          <li key={j.date} className="text-sm">
            <span className="font-medium capitalize text-[var(--foreground)]">{fmtDate(j.date)}</span>
            <span className="ml-2 text-xs text-[var(--muted-foreground)]">{j.load_h} h · {j.n_events} évén. — {j.suggestion}</span>
          </li>
        ))}
      </ul>
    </section>
  )
}

/** Projections de tendances par régression (#228). */
function ForecastsSection() {
  const { data } = useForecasts()
  const forecasts = data?.forecasts ?? []
  if (!forecasts.length) return null
  return (
    <section className="rounded-[var(--radius-lg)] border border-[var(--glass-border)] bg-[var(--card)] p-5">
      <h2 className="mb-3 flex items-center gap-1.5 text-xs font-semibold text-[var(--muted-foreground)]">
        <TrendingUp size={13} /> Projections à {data?.horizon_days ?? 30} jours (tendance linéaire)
      </h2>
      <ul className="space-y-1.5">
        {forecasts.map((f) => {
          const up = f.variation > 0
          return (
            <li key={f.metric} className="flex items-center justify-between gap-3 text-sm">
              <span className="min-w-0 truncate text-[var(--foreground)]">
                {f.metric} <span className="text-xs text-[var(--muted-foreground)]">{f.courant} → {f.prevision}</span>
              </span>
              <span className={`shrink-0 tabular-nums text-xs font-medium ${f.direction === 'stable' ? 'text-[var(--muted-foreground)]' : up ? 'text-[var(--success-foreground)]' : 'text-[var(--warning-foreground)]'}`}>
                {f.variation > 0 ? '+' : ''}{f.variation}
              </span>
            </li>
          )
        })}
      </ul>
    </section>
  )
}

/** Recommandations priorisées par impact (#227). */
function RecommendationsSection() {
  const { data } = useRecommendations()
  const recs = data?.recommendations ?? []
  if (!recs.length) return null
  return (
    <section className="rounded-[var(--radius-lg)] border border-[var(--glass-border)] bg-[var(--card)] p-5">
      <h2 className="mb-3 flex items-center gap-1.5 text-xs font-semibold text-[var(--muted-foreground)]">
        <Lightbulb size={13} /> Recommandations (les plus utiles d&apos;abord)
      </h2>
      <ul className="space-y-2">
        {recs.map((r, i) => (
          <li key={i} className="flex items-center gap-3 text-sm">
            <span className="flex h-7 w-9 shrink-0 items-center justify-center rounded-[var(--radius)] bg-[var(--accent)] text-xs font-semibold tabular-nums text-[var(--foreground)]" title="impact estimé">{r.impact}</span>
            <span className="min-w-0 flex-1">
              <span className="text-[var(--foreground)]">{r.titre}</span>
              <span className="ml-2 text-xs text-[var(--muted-foreground)]">{r.raison}</span>
            </span>
          </li>
        ))}
      </ul>
    </section>
  )
}

function Metric({ label, value }: { label: string; value: string }) {
  return (
    <div>
      <div className="text-xs text-[var(--muted-foreground)]">{label}</div>
      <div className="tabular-nums text-[var(--foreground)]">{value}</div>
    </div>
  )
}

export default function Vue360Page() {
  const [active, setActive] = useState<TabId>('synthese')
  return (
    <div className="animate-fade-in">
      <ModuleHeader
        title="Vue 360"
        subtitle="Synthèse de toute ta vie sur un écran"
        tabs={TABS}
        active={active}
        onChange={(id) => setActive(id as TabId)}
      />
      <div className="p-6 animate-fade-in-up">
        <ErrorBoundary label="Vue 360">
          <Vue360Content active={active} />
        </ErrorBoundary>
      </div>
    </div>
  )
}
