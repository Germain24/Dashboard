/**
 * Variants Framer Motion partagés par les sections du Deck.
 * `staggerContainer` orchestre l'entrée en cascade des enfants `fadeUp`.
 * Sous reduced-motion, Framer Motion neutralise automatiquement les transforms
 * (les `y` sont ignorés), il ne reste que le fondu d'opacité.
 */

import type { Variants } from 'motion/react'
import { springs } from './tokens'

/** Décalage temporel (s) entre chaque enfant d'un conteneur en stagger. */
export const STAGGER_STEP = 0.07

export const fadeUp: Variants = {
  hidden: { opacity: 0, y: 16 },
  visible: { opacity: 1, y: 0, transition: springs.soft },
}

export const staggerContainer: Variants = {
  hidden: {},
  visible: {
    transition: { staggerChildren: STAGGER_STEP, delayChildren: 0.05 },
  },
}
