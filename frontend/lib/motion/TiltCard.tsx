'use client'

/**
 * Carte avec tilt 3D très subtil (≤ ±4°) suivant la souris, retour en inertie
 * spring. Esthétique quiet luxury : perceptible seulement si l'on est attentif.
 * Désactivé sous reduced-motion (rend un simple <div>).
 */

import { useRef } from 'react'
import { motion, useMotionValue, useSpring, useReducedMotion } from 'motion/react'
import { springs } from './tokens'
import { cn } from '@/lib/utils'

export const MAX_TILT_DEG = 4

type Rect = { left: number; top: number; width: number; height: number }

export function computeTilt(
  clientX: number,
  clientY: number,
  rect: Rect,
  maxDeg: number,
): { rotateX: number; rotateY: number } {
  const cx = rect.left + rect.width / 2
  const cy = rect.top + rect.height / 2
  const nx = (clientX - cx) / (rect.width / 2)
  const ny = (clientY - cy) / (rect.height / 2)
  const clamp = (v: number) => Math.max(-1, Math.min(1, v))
  // Souris en haut (ny<0) → bord haut vers l'utilisateur → rotateX positif.
  const rotateX = -clamp(ny) * maxDeg
  const rotateY = clamp(nx) * maxDeg
  // Normalize -0 to +0 for test equality
  return { rotateX: rotateX === 0 ? 0 : rotateX, rotateY: rotateY === 0 ? 0 : rotateY }
}

export function TiltCard({
  children,
  className,
}: {
  children: React.ReactNode
  className?: string
}) {
  const reduced = useReducedMotion()
  const ref = useRef<HTMLDivElement | null>(null)
  const rx = useMotionValue(0)
  const ry = useMotionValue(0)
  const rotateX = useSpring(rx, springs.tilt)
  const rotateY = useSpring(ry, springs.tilt)

  if (reduced) {
    return <div className={className}>{children}</div>
  }

  const onMove = (e: React.MouseEvent<HTMLDivElement>) => {
    const el = ref.current
    if (!el) return
    const t = computeTilt(e.clientX, e.clientY, el.getBoundingClientRect(), MAX_TILT_DEG)
    rx.set(t.rotateX)
    ry.set(t.rotateY)
  }
  const onLeave = () => {
    rx.set(0)
    ry.set(0)
  }

  return (
    <div ref={ref} style={{ perspective: 1000 }} onMouseMove={onMove} onMouseLeave={onLeave}>
      <motion.div
        className={cn(className)}
        style={{ rotateX, rotateY, transformStyle: 'preserve-3d' }}
      >
        {children}
      </motion.div>
    </div>
  )
}
