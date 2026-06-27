'use client'

/**
 * Expérience « Corps » (groupe Santé & Performance) — prototype de la nouvelle
 * norme : héros Score de forme + modules satellites (sommeil, macros, séance,
 * skincare), mise en page éditoriale asymétrique. Vitrine + drill-in.
 *
 * Parallax au scroll multi-couches : un halo et le titre se déplacent à des
 * vitesses différentes (profondeur), désactivé en reduced-motion.
 */

import { useRef } from 'react'
import { motion } from 'motion/react'
import { DeckSection, FadeUpItem } from '@/components/deck/DeckSection'
import { useScrollParallax } from '@/lib/motion/useScrollParallax'
import { ScoreRingModule } from '@/components/deck/modules/ScoreRingModule'
import { MacrosModule } from '@/components/deck/modules/MacrosModule'
import { SleepModule } from '@/components/deck/modules/SleepModule'
import { NextWorkoutModule } from '@/components/deck/modules/NextWorkoutModule'
import { SkincareModule } from '@/components/deck/modules/SkincareModule'

export function CorpsExperience({
  index,
  sectionRef,
}: {
  index: number
  sectionRef?: (el: HTMLElement | null) => void
}) {
  const titleRef = useRef<HTMLDivElement>(null)
  const titleY = useScrollParallax(titleRef, 40)
  const haloY = useScrollParallax(titleRef, 90)

  return (
    <DeckSection label="Corps" index={index} sectionRef={sectionRef}>
      {/* Halo décoratif — couche de fond, parallax plus rapide que le titre. */}
      <motion.div
        aria-hidden="true"
        style={{ y: haloY }}
        className="pointer-events-none absolute -left-16 top-[18%] -z-10 h-[440px] w-[440px] rounded-full bg-[radial-gradient(circle,color-mix(in_srgb,var(--ring)_16%,transparent),transparent_70%)] blur-3xl"
      />

      <FadeUpItem>
        <motion.div ref={titleRef} style={{ y: titleY }}>
          <p className="text-sm text-[var(--muted-foreground)]">
            {String(index + 1).padStart(2, '0')} / 07
          </p>
          <h2 className="mt-1 font-display text-[clamp(1.75rem,4vw,3rem)] leading-tight text-[var(--foreground)]">
            Corps
          </h2>
        </motion.div>
      </FadeUpItem>

      <div className="mt-10 grid items-center gap-10 md:grid-cols-[auto_1fr]">
        <FadeUpItem className="flex justify-center md:justify-start">
          <ScoreRingModule />
        </FadeUpItem>

        <div className="grid gap-4 sm:grid-cols-2">
          <FadeUpItem><SleepModule /></FadeUpItem>
          <FadeUpItem><MacrosModule /></FadeUpItem>
          <FadeUpItem><NextWorkoutModule /></FadeUpItem>
          <FadeUpItem><SkincareModule /></FadeUpItem>
        </div>
      </div>
    </DeckSection>
  )
}
