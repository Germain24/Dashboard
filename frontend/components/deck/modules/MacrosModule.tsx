'use client'

/**
 * Module « Macros du jour » : calories consommées / cible (count-up), barre de
 * progression, et hydratation intégrée en indicateur discret (pas de module
 * séparé). Drill-in vers /sante.
 */

import Link from 'next/link'
import { Droplet } from 'lucide-react'
import { useScore, useWaterToday } from '@/lib/queries/sante'
import { AnimatedNumber } from '@/lib/motion/AnimatedNumber'
import { TiltCard } from '@/lib/motion/TiltCard'
import { Skeleton } from '@/components/ui/skeleton'

export function MacrosModule() {
  const { data: score, isLoading: loadingScore } = useScore()
  const { data: water, isLoading: loadingWater } = useWaterToday()

  // On attend aussi l'hydratation pour éviter un flash (calories d'abord, puis
  // la ligne « Hydratation » qui apparaît après coup).
  if (loadingScore || loadingWater) {
    return <Skeleton data-testid="macros-skeleton" className="h-28 w-full" />
  }

  const kcal = score?.details.kcal_consommees ?? null
  const cible = score?.details.kcal_cible ?? null
  const pct = kcal != null && cible ? Math.min(100, (kcal / cible) * 100) : 0
  const waterPct = water?.pct ?? null

  return (
    <TiltCard className="block rounded-[var(--radius-lg)]">
      <Link
        href="/sante"
        aria-label="Macros et nutrition du jour"
        className="block rounded-[var(--radius-lg)] border border-[var(--glass-border)] bg-[var(--card)] p-5 backdrop-blur-[var(--glass-blur)] shadow-[inset_0_1px_0_0_var(--glass-highlight),var(--shadow)] focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-[var(--ring)]"
      >
        <div className="flex items-baseline justify-between">
          <h3 className="font-display text-xl text-[var(--foreground)]">Macros</h3>
          <p className="text-sm text-[var(--muted-foreground)]">
            {kcal == null ? (
              <span className="tabular-nums">—</span>
            ) : (
              <AnimatedNumber value={kcal} className="tabular-nums text-[var(--foreground)]" />
            )}
            <span className="tabular-nums"> / {cible ?? '—'} kcal</span>
          </p>
        </div>
        <div className="mt-3 h-2 overflow-hidden rounded bg-[var(--muted)]">
          <div className="h-full bg-[var(--ring)]" style={{ width: `${pct}%` }} />
        </div>
        {waterPct != null && (
          <p className="mt-3 flex items-center gap-1.5 text-xs text-[var(--muted-foreground)]">
            <Droplet className="h-3.5 w-3.5" aria-hidden="true" />
            Hydratation <span className="tabular-nums">{waterPct}&nbsp;%</span>
          </p>
        )}
      </Link>
    </TiltCard>
  )
}
