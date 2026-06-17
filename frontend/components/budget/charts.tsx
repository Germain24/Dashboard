'use client'
/** Graphes du module Budget (extraits de MoisTab.tsx, #519) : camembert + tendance. */

import type { CategorySpend, MonthTrend } from '@/lib/budget'

const formatCAD = (v: number) =>
  new Intl.NumberFormat('fr-CA', { style: 'currency', currency: 'CAD' }).format(v ?? 0)

/** "2026-01" → "janv. 26" (mois court + année sur 2 chiffres). */
const monthLabel = (mois: string) => {
  const [y, m] = mois.split('-').map(Number)
  if (!y || !m) return mois
  return new Date(y, m - 1, 1).toLocaleDateString('fr-CA', { month: 'short', year: '2-digit' })
}

export function Donut({ data }: { data: CategorySpend[] }) {
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

export function TrendChart({ data }: { data: MonthTrend[] }) {
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
            <div key={d.mois} className="flex h-full flex-1 items-end justify-center gap-0.5">
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
          <span key={d.mois} className="flex-1 text-center text-[10px] text-[var(--muted-foreground)]">
            {monthLabel(d.mois)}
          </span>
        ))}
      </div>
    </div>
  )
}
