'use client'

/**
 * Parallax vertical piloté par le scroll, pour un effet de profondeur
 * multi-couches (ex. titre + halo de Corps qui se déplacent à des vitesses
 * différentes). Mappe la progression de la cible dans le viewport sur un
 * décalage `±distance` px. Désactivé (constant 0) sous reduced-motion.
 */

import { useScroll, useTransform, useReducedMotion, type MotionValue } from 'motion/react'
import type { RefObject } from 'react'

export function useScrollParallax(
  ref: RefObject<HTMLElement | null>,
  distance: number,
): MotionValue<number> {
  const reduced = useReducedMotion()
  const { scrollYProgress } = useScroll({
    target: ref,
    offset: ['start end', 'end start'],
  })
  // Au centre du viewport (progress ≈ 0.5) le décalage est nul ; il glisse de
  // +distance (entrée par le bas) à -distance (sortie par le haut).
  return useTransform(scrollYProgress, [0, 1], reduced ? [0, 0] : [distance, -distance])
}
