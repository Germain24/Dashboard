'use client'

/**
 * Parallax souris pour un élément héros (anneau de score).
 * `computeParallax` est pure et testée ; `useParallax` la branche aux
 * MotionValues + springs. Désactivé sous reduced-motion (reste à 0,0).
 */

import { useEffect, useRef } from 'react'
import { useMotionValue, useSpring, useReducedMotion, type MotionValue } from 'motion/react'
import { springs } from './tokens'

type Rect = { left: number; top: number; width: number; height: number }

export function computeParallax(
  clientX: number,
  clientY: number,
  rect: Rect,
  strength: number,
): { x: number; y: number } {
  const cx = rect.left + rect.width / 2
  const cy = rect.top + rect.height / 2
  const nx = (clientX - cx) / (rect.width / 2) // -1..1 (hors borne possible)
  const ny = (clientY - cy) / (rect.height / 2)
  const clamp = (v: number) => Math.max(-1, Math.min(1, v))
  // Inversé : l'élément « recule » dans le sens opposé à la souris.
  const x = -clamp(nx) * strength
  const y = -clamp(ny) * strength
  // Normalize -0 to 0
  return { x: x === 0 ? 0 : x, y: y === 0 ? 0 : y }
}

export function useParallax(strength: number): {
  ref: React.RefObject<HTMLDivElement | null>
  x: MotionValue<number>
  y: MotionValue<number>
} {
  const reduced = useReducedMotion()
  const ref = useRef<HTMLDivElement | null>(null)
  const rawX = useMotionValue(0)
  const rawY = useMotionValue(0)
  const x = useSpring(rawX, springs.tilt)
  const y = useSpring(rawY, springs.tilt)

  useEffect(() => {
    if (reduced) {
      rawX.set(0)
      rawY.set(0)
      return
    }
    const handle = (e: MouseEvent) => {
      const el = ref.current
      if (!el) return
      const rect = el.getBoundingClientRect()
      const { x: px, y: py } = computeParallax(e.clientX, e.clientY, rect, strength)
      rawX.set(px)
      rawY.set(py)
    }
    window.addEventListener('mousemove', handle)
    return () => window.removeEventListener('mousemove', handle)
  }, [reduced, strength, rawX, rawY])

  return { ref, x, y }
}
