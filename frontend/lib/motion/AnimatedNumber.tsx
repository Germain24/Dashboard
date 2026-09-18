'use client'

/**
 * Chiffre animé en count-up (0 → value) via un ressort amorti.
 * Respecte reduced-motion : la valeur finale s'affiche immédiatement.
 * Toujours utilisé avec `tabular-nums` côté appelant pour éviter les sauts.
 */

import { useEffect, useState } from 'react'
import { useSpring, useReducedMotion, useMotionValueEvent } from 'motion/react'
import { springs } from './tokens'

type Props = {
  value: number
  format?: (v: number) => string
  className?: string
}

export function AnimatedNumber({ value, format = (v) => String(Math.round(v)), className }: Props) {
  const reduced = useReducedMotion()
  const spring = useSpring(0, springs.countUp)

  // Initialize display based on reduced motion
  const initialDisplay = reduced ? value : 0
  const [display, setDisplay] = useState(initialDisplay)

  useEffect(() => {
    if (reduced) {
      spring.jump(value)
      setDisplay(value)
    } else {
      spring.set(value)
    }
  }, [value, reduced, spring])

  useMotionValueEvent(spring, 'change', (v) => {
    if (!reduced) setDisplay(v)
  })

  return <span className={className}>{format(display)}</span>
}
