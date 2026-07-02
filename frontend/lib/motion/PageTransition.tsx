'use client'

/**
 * Transition d'entrée de page, keyée sur le MODULE (1er segment d'URL) :
 * naviguer à l'intérieur d'un module ne rejoue rien (fini le « flash »
 * à chaque clic), changer de module rejoue un fondu court.
 * Opacité seule : un transform persistant créerait un bloc conteneur et
 * casserait les `position: fixed` des enfants (rail de points du Deck).
 * Remplace src/app/template.tsx (qui remontait à CHAQUE navigation).
 */

import { usePathname } from 'next/navigation'
import { motion, useReducedMotion } from 'motion/react'
import { durations, EASE_OUT } from './tokens'

export function PageTransition({ children }: { children: React.ReactNode }) {
  const pathname = usePathname()
  const reduced = useReducedMotion()
  const segment = '/' + (pathname.split('/')[1] ?? '')

  if (reduced) {
    return (
      <div data-testid="page-transition" data-segment={segment}>
        {children}
      </div>
    )
  }

  return (
    <motion.div
      key={segment}
      data-testid="page-transition"
      data-segment={segment}
      initial={{ opacity: 0 }}
      animate={{ opacity: 1 }}
      transition={{ duration: durations.fast, ease: EASE_OUT }}
    >
      {children}
    </motion.div>
  )
}
