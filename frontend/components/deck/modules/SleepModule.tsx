'use client'

/**
 * Module « Sommeil » : durée de la dernière nuit (via le score de forme).
 * Drill-in vers /score. Chiffre en tabular-nums.
 */

import Link from 'next/link'
import { Moon } from 'lucide-react'
import { useScore } from '@/lib/queries/sante'
import { TiltCard } from '@/lib/motion/TiltCard'
import { Skeleton } from '@/components/ui/skeleton'

export function formatSleepHours(h: number | null): string {
  if (h == null) return '—'
  const total = Math.round(h * 60)
  const hh = Math.floor(total / 60)
  const mm = total % 60
  return `${hh} h ${String(mm).padStart(2, '0')}`
}

export function SleepModule() {
  const { data, isLoading } = useScore()
  if (isLoading) return <Skeleton data-testid="sleep-skeleton" className="h-24 w-full" />

  return (
    <TiltCard className="block rounded-[var(--radius-lg)]">
      <Link
        href="/score"
        aria-label="Sommeil de la dernière nuit"
        className="block rounded-[var(--radius-lg)] border border-[var(--glass-border)] bg-[var(--card)] p-5 backdrop-blur-[var(--glass-blur)] shadow-[inset_0_1px_0_0_var(--glass-highlight),var(--shadow)] focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-[var(--ring)]"
      >
        <div className="flex items-center gap-2 text-[var(--muted-foreground)]">
          <Moon className="h-4 w-4" aria-hidden="true" />
          <span className="text-sm">Sommeil</span>
        </div>
        <p className="mt-1 font-display text-2xl tabular-nums text-[var(--foreground)]">
          {formatSleepHours(data?.details.sommeil_h ?? null)}
        </p>
      </Link>
    </TiltCard>
  )
}
