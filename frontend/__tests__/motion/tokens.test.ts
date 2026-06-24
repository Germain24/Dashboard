import { describe, it, expect } from 'vitest'
import { springs, durations, EASE_OUT } from '@/lib/motion/tokens'

describe('motion tokens', () => {
  it('expose trois springs typés', () => {
    for (const key of ['soft', 'countUp', 'tilt'] as const) {
      expect(springs[key].type).toBe('spring')
      expect(springs[key].stiffness).toBeGreaterThan(0)
      expect(springs[key].damping).toBeGreaterThan(0)
    }
  })
  it('expose des durées croissantes', () => {
    expect(durations.fast).toBeLessThan(durations.base)
    expect(durations.base).toBeLessThan(durations.slow)
  })
  it('EASE_OUT est une courbe de Bézier à 4 points', () => {
    expect(EASE_OUT).toHaveLength(4)
  })
})
