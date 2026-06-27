'use client'

/**
 * Wrapper générique d'une section du Deck. Conserve le snap CSS (.deck-section)
 * et délègue l'orchestration à Framer Motion : le conteneur passe en `visible`
 * (stagger) quand il entre dans le viewport et revient en `hidden` (fondu +
 * léger slide) quand il en sort — entrée ET sortie. Réutilisable par toutes les
 * expériences de domaine. Sous reduced-motion, seul le fondu d'opacité subsiste.
 */

import { useRef, type ReactNode } from 'react'
import { motion, useInView } from 'motion/react'
import { fadeUp, staggerContainer } from '@/lib/motion/variants'

/** Enfant standard d'une DeckSection : entre en fondu + slide-up. */
export const MotionFadeUp = motion.create('div')

export function DeckSection({
  children,
  label,
  index,
  sectionRef,
}: {
  children: ReactNode
  label: string
  index: number
  sectionRef?: (el: HTMLElement | null) => void
}) {
  const inViewRef = useRef<HTMLDivElement>(null)
  // once: false → la section s'anime aussi en SORTIE quand elle quitte le viewport.
  const inView = useInView(inViewRef, { once: false, amount: 0.35 })

  return (
    <section ref={sectionRef} className="deck-section" aria-label={label} data-index={index}>
      <motion.div
        ref={inViewRef}
        variants={staggerContainer}
        initial="hidden"
        animate={inView ? 'visible' : 'hidden'}
        className="mx-auto w-full max-w-[1280px] px-[max(24px,calc((100vw-1280px)/2+24px))]"
      >
        {children}
      </motion.div>
    </section>
  )
}

/** Helper : enfant fadeUp prêt à l'emploi. */
export function FadeUpItem({ children, className }: { children: ReactNode; className?: string }) {
  return (
    <MotionFadeUp variants={fadeUp} className={className}>
      {children}
    </MotionFadeUp>
  )
}
