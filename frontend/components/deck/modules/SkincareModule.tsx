'use client'

/**
 * Module « Skincare » : nombre de produits dus aujourd'hui. Drill-in /skincare.
 */

import Link from 'next/link'
import { Sparkles } from 'lucide-react'
import { useSkincareToday } from '@/lib/queries/skincare'
import { TiltCard } from '@/lib/motion/TiltCard'
import { Skeleton } from '@/components/ui/skeleton'

export function SkincareModule() {
  const { data, isLoading } = useSkincareToday()
  if (isLoading) return <Skeleton data-testid="skincare-skeleton" className="h-24 w-full" />

  const due = data?.due.length ?? 0

  return (
    <TiltCard className="block rounded-[var(--radius-lg)]">
      <Link
        href="/skincare"
        aria-label="Routine skincare du jour"
        className="block rounded-[var(--radius-lg)] border border-[var(--glass-border)] bg-[var(--card)] p-5 backdrop-blur-[var(--glass-blur)] shadow-[inset_0_1px_0_0_var(--glass-highlight),var(--shadow)] focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-[var(--ring)]"
      >
        <div className="flex items-center gap-2 text-[var(--muted-foreground)]">
          <Sparkles className="h-4 w-4" aria-hidden="true" />
          <span className="text-sm">Skincare</span>
        </div>
        <p className="mt-1 font-display text-2xl text-[var(--foreground)]">
          {due > 0 ? (
            <>
              <span className="tabular-nums">{due}</span> dû
            </>
          ) : (
            'à jour'
          )}
        </p>
      </Link>
    </TiltCard>
  )
}
