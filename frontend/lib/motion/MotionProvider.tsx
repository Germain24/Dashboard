'use client'

/**
 * Configuration Motion globale : `reducedMotion="user"` neutralise les
 * transforms (translate/scale) quand l'OS demande moins de mouvement,
 * en ne laissant que les fondus d'opacité. Posé une fois dans le layout.
 */

import { MotionConfig } from 'motion/react'

export function MotionProvider({ children }: { children: React.ReactNode }) {
  return <MotionConfig reducedMotion="user">{children}</MotionConfig>
}
