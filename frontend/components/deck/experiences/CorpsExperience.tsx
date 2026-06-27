'use client'

/**
 * Expérience « Corps » (groupe Santé & Performance) — prototype de la nouvelle
 * norme : héros Score de forme + modules satellites (sommeil, macros, séance,
 * skincare), mise en page éditoriale asymétrique. Vitrine + drill-in.
 */

import { DeckSection, FadeUpItem } from '@/components/deck/DeckSection'
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
  return (
    <DeckSection label="Corps" index={index} sectionRef={sectionRef}>
      <FadeUpItem>
        <p className="text-sm text-[var(--muted-foreground)]">
          {String(index + 1).padStart(2, '0')} / 07
        </p>
        <h2 className="mt-1 font-display text-[clamp(1.75rem,4vw,3rem)] leading-tight text-[var(--foreground)]">
          Corps
        </h2>
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
