'use client'

/**
 * Le Deck (v2) — coquille d'accueil pilotée par Framer Motion. Le snap reste
 * CSS (.deck / .deck-section). Le groupe « Santé & Performance » est rendu par
 * CorpsExperience (prototype) ; les autres par GenericGroupExperience le temps
 * de leur migration. Rail de points + clavier via useDeckNavigation.
 */

import { type ReactNode } from 'react'
import { MODULE_GROUPS } from '@/lib/modules'
import { CorpsExperience } from '@/components/deck/experiences/CorpsExperience'
import { GenericGroupExperience } from '@/components/deck/experiences/GenericGroupExperience'
import { DeckRail } from '@/components/deck/DeckRail'
import { useDeckNavigation } from '@/components/deck/useDeckNavigation'

const CORPS_GROUP = 'Santé & Performance'

export function Deck({ intro }: { intro?: ReactNode }) {
  const introOffset = intro ? 1 : 0
  const total = MODULE_GROUPS.length + introOffset
  const { active, sectionRefs, goTo } = useDeckNavigation(total)

  const labels = [
    ...(intro ? ["Aujourd'hui"] : []),
    ...MODULE_GROUPS.map((g) => (g.group === CORPS_GROUP ? 'Corps' : g.group)),
  ]

  return (
    <div className="relative">
      <div className="deck no-scrollbar" aria-label="Accueil">
        {intro && (
          <section
            ref={(el) => { sectionRefs.current[0] = el }}
            className="deck-section"
            aria-label="Aujourd'hui"
          >
            <div className="mx-auto w-full max-w-[1280px] px-[max(24px,calc((100vw-1280px)/2+24px))]">
              {intro}
            </div>
          </section>
        )}

        {MODULE_GROUPS.map((group, gi) => {
          const index = gi + introOffset
          const setRef = (el: HTMLElement | null) => { sectionRefs.current[index] = el }
          return group.group === CORPS_GROUP ? (
            <CorpsExperience key={group.group} index={index} sectionRef={setRef} />
          ) : (
            <GenericGroupExperience key={group.group} group={group} index={index} sectionRef={setRef} />
          )
        })}
      </div>

      <DeckRail total={total} active={active} labels={labels} onJump={goTo} />
    </div>
  )
}
