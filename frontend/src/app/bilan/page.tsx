'use client'

import { useState } from 'react'
import { ChevronLeft, ChevronRight, Printer } from 'lucide-react'
import { ModuleHeader } from '@/components/layout'
import { ErrorBoundary } from '@/components/ErrorBoundary'
import { useMonthlyReport } from '@/lib/queries/routines'

function Bilan() {
  const now = new Date()
  const [ym, setYm] = useState({ y: now.getFullYear(), m: now.getMonth() + 1 })
  const { data, isLoading } = useMonthlyReport(ym.y, ym.m)
  const shift = (d: number) => {
    let m = ym.m + d, y = ym.y
    if (m < 1) { m = 12; y -= 1 }
    if (m > 12) { m = 1; y += 1 }
    setYm({ y, m })
  }

  return (
    <div className="mx-auto max-w-2xl space-y-5">
      <div className="flex items-center justify-between print:hidden">
        <div className="flex items-center gap-2">
          <button onClick={() => shift(-1)} aria-label="Mois précédent" className="rounded-lg border border-[var(--border)] p-1.5 text-[var(--muted-foreground)] hover:text-[var(--foreground)]"><ChevronLeft size={15} /></button>
          <span className="min-w-32 text-center text-sm font-medium capitalize">{data?.periode ?? '…'}</span>
          <button onClick={() => shift(1)} aria-label="Mois suivant" className="rounded-lg border border-[var(--border)] p-1.5 text-[var(--muted-foreground)] hover:text-[var(--foreground)]"><ChevronRight size={15} /></button>
        </div>
        <button onClick={() => window.print()} className="flex items-center gap-1.5 rounded-lg bg-[var(--ring)] px-3 py-1.5 text-sm font-medium text-white">
          <Printer size={14} /> Imprimer / PDF
        </button>
      </div>

      {isLoading || !data ? (
        <p className="text-sm text-[var(--muted-foreground)]">Chargement…</p>
      ) : data.jours_couverts === 0 ? (
        <p className="text-sm text-[var(--muted-foreground)]">Aucune donnée pour {data.periode}.</p>
      ) : (
        <article className="rounded-[var(--radius-lg)] border border-[var(--glass-border)] bg-[var(--card)] p-6">
          <header className="mb-4 border-b border-[var(--glass-border)] pb-3">
            <h1 className="font-display text-2xl capitalize text-[var(--foreground)]">Bilan de vie — {data.periode}</h1>
            <p className="text-sm text-[var(--muted-foreground)]">{data.jours_couverts} jours couverts</p>
          </header>

          <section className="mb-4">
            <h2 className="mb-2 text-xs font-semibold uppercase text-[var(--muted-foreground)]">Métriques du mois</h2>
            <dl className="grid grid-cols-2 gap-3 sm:grid-cols-3">
              {Object.entries(data.metriques).map(([k, v]) => (
                <div key={k}>
                  <dt className="text-xs text-[var(--muted-foreground)]">{k}</dt>
                  <dd className="tabular-nums text-lg text-[var(--foreground)]">{v}</dd>
                </div>
              ))}
            </dl>
          </section>

          {data.poids && (
            <section>
              <h2 className="mb-2 text-xs font-semibold uppercase text-[var(--muted-foreground)]">Poids</h2>
              <p className="text-sm text-[var(--foreground)]">
                {data.poids.debut} kg → {data.poids.fin} kg{' '}
                <span className={data.poids.delta <= 0 ? 'text-[var(--success-foreground)]' : 'text-[var(--warning-foreground)]'}>
                  ({data.poids.delta > 0 ? '+' : ''}{data.poids.delta} kg)
                </span>
              </p>
            </section>
          )}
        </article>
      )}
    </div>
  )
}

export default function BilanPage() {
  return (
    <div className="animate-fade-in">
      <ModuleHeader title="Bilan mensuel" subtitle="Synthèse de vie imprimable (→ PDF)" />
      <div className="p-6 animate-fade-in-up">
        <ErrorBoundary label="Bilan">
          <Bilan />
        </ErrorBoundary>
      </div>
    </div>
  )
}
