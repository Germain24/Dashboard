'use client'

/**
 * Module héros « Score de forme » : anneau SVG dont l'arc se remplit selon le
 * score (0–100), valeur centrale en count-up `tabular-nums`, parallax souris
 * léger, sous-scores sommeil/sport/nutrition. Drill-in vers /score.
 */

import Link from 'next/link'
import { motion } from 'motion/react'
import { useScore } from '@/lib/queries/sante'
import { AnimatedNumber } from '@/lib/motion/AnimatedNumber'
import { useParallax } from '@/lib/motion/useParallax'
import { EASE_OUT } from '@/lib/motion/tokens'
import { Skeleton } from '@/components/ui/skeleton'

const R = 86
const CIRC = 2 * Math.PI * R

function tone(score: number): string {
  if (score >= 80) return 'var(--success)'
  if (score >= 60) return '#22c55e'
  if (score >= 40) return '#f59e0b'
  return 'var(--destructive)'
}

export function ScoreRingModule() {
  const { data, isLoading, isError } = useScore()
  const { ref, x, y } = useParallax(8)

  if (isLoading) {
    return <Skeleton data-testid="score-skeleton" className="h-[220px] w-[220px] rounded-full" />
  }

  const score = isError || data == null ? null : (data.score ?? null)
  const pct = score == null ? 0 : Math.max(0, Math.min(100, score)) / 100
  const color = score != null ? tone(score) : 'var(--muted)'
  const comps = data?.composantes

  return (
    <Link
      href="/score"
      aria-label={`Score de forme${score != null ? ` : ${score} sur 100` : ''}`}
      className="group inline-flex flex-col items-center gap-4 rounded-[var(--radius-lg)] focus-visible:outline-2 focus-visible:outline-offset-4 focus-visible:outline-[var(--ring)]"
    >
      <motion.div ref={ref} style={{ x, y }} className="relative h-[220px] w-[220px]">
        <svg viewBox="0 0 200 200" className="h-full w-full -rotate-90">
          <circle cx="100" cy="100" r={R} fill="none" stroke="var(--muted)" strokeWidth="10" />
          <motion.circle
            cx="100" cy="100" r={R} fill="none" stroke={color} strokeWidth="10" strokeLinecap="round"
            strokeDasharray={CIRC}
            initial={{ strokeDashoffset: CIRC }}
            animate={{ strokeDashoffset: CIRC * (1 - pct) }}
            transition={{ duration: 1.1, ease: EASE_OUT }}
          />
        </svg>
        <div className="absolute inset-0 flex flex-col items-center justify-center">
          {score == null ? (
            <span className="font-display text-5xl tabular-nums text-[var(--muted-foreground)]">—</span>
          ) : (
            <AnimatedNumber value={score} className="font-display text-6xl tabular-nums text-[var(--foreground)]" />
          )}
          <span className="text-xs uppercase tracking-wide text-[var(--muted-foreground)]">score</span>
        </div>
      </motion.div>

      {comps && (
        <div className="flex gap-5 text-sm">
          <SubScore label="Sommeil" value={comps.sommeil} />
          <SubScore label="Sport" value={comps.sport} />
          <SubScore label="Nutrition" value={comps.nutrition} />
        </div>
      )}
    </Link>
  )
}

function SubScore({ label, value }: { label: string; value: number | null }) {
  return (
    <span className="flex flex-col items-center">
      <span className="font-medium tabular-nums text-[var(--foreground)]">{value ?? '—'}</span>
      <span className="text-xs text-[var(--muted-foreground)]">{label}</span>
    </span>
  )
}
