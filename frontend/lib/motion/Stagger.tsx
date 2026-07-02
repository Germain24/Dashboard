'use client'

/**
 * Cascade d'entrée déclarative (remplace l'ancien utilitaire CSS `.stagger`
 * limité à 6 enfants). Opt-in : chaque item est posé explicitement, le
 * conteneur peut être une grid (l'item porte les classes de placement,
 * ex. col-span-2). Sous reduced-motion, seuls les fondus restent.
 */

import { motion } from 'motion/react'
import { fadeUp, staggerContainer } from './variants'

export function StaggerGroup({
  children,
  className,
}: {
  children: React.ReactNode
  className?: string
}) {
  return (
    <motion.div
      data-testid="stagger-group"
      className={className}
      variants={staggerContainer}
      initial="hidden"
      animate="visible"
    >
      {children}
    </motion.div>
  )
}

export function StaggerItem({
  children,
  className,
}: {
  children: React.ReactNode
  className?: string
}) {
  return (
    <motion.div className={className} variants={fadeUp}>
      {children}
    </motion.div>
  )
}
