/**
 * Tokens de mouvement — source unique des springs, durées et easings.
 * Toute animation Motion (motion/react) du Deck y puise (cohérence + ajustement central).
 * Mappé sur l'esthétique « quiet luxury » : ressorts amortis, pas de rebond.
 */

export type Spring = {
  type: 'spring'
  stiffness: number
  damping: number
  mass?: number
}

export const springs = {
  /** Entrées / éléments généraux : doux, sans rebond. */
  soft: { type: 'spring', stiffness: 120, damping: 20, mass: 1 } as Spring,
  /** Count-up de chiffres : un peu plus rapide, fortement amorti (pas d'overshoot). */
  countUp: { type: 'spring', stiffness: 90, damping: 26, mass: 1 } as Spring,
  /** Tilt / parallax au survol : inertie marquée mais retour calme. */
  tilt: { type: 'spring', stiffness: 150, damping: 18, mass: 0.6 } as Spring,
} as const

export const durations = {
  fast: 0.25,
  base: 0.45,
  slow: 0.7,
} as const

/** Équivalent JS de --ease-out (globals.css). */
export const EASE_OUT: [number, number, number, number] = [0.22, 1, 0.36, 1]
