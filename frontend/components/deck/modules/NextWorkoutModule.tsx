'use client'

/**
 * Module « Séance du jour » : libellé du jour programmé + premier bloc.
 * État repos si aucun bloc. Drill-in vers /entrainement.
 */

import Link from 'next/link'
import { Dumbbell } from 'lucide-react'
import { useEntrainementToday } from '@/lib/queries/entrainement'
import { TiltCard } from '@/lib/motion/TiltCard'
import { Skeleton } from '@/components/ui/skeleton'

export function NextWorkoutModule() {
  const { data, isLoading } = useEntrainementToday()
  if (isLoading) return <Skeleton data-testid="workout-skeleton" className="h-24 w-full" />

  const label = data?.jour_label ?? '—'
  const firstBlock = data?.slots?.[0]?.label ?? null

  return (
    <TiltCard className="block rounded-[var(--radius-lg)]">
      <Link
        href="/entrainement"
        aria-label="Séance d'entraînement du jour"
        className="block rounded-[var(--radius-lg)] border border-[var(--glass-border)] bg-[var(--card)] p-5 backdrop-blur-[var(--glass-blur)] shadow-[inset_0_1px_0_0_var(--glass-highlight),var(--shadow)] focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-[var(--ring)]"
      >
        <div className="flex items-center gap-2 text-[var(--muted-foreground)]">
          <Dumbbell className="h-4 w-4" aria-hidden="true" />
          <span className="text-sm">Séance du jour</span>
        </div>
        <p className="mt-1 font-display text-2xl text-[var(--foreground)]">{label}</p>
        <p className="mt-0.5 text-sm text-[var(--muted-foreground)]">
          {firstBlock ?? 'Jour de repos'}
        </p>
      </Link>
    </TiltCard>
  )
}
