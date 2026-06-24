import { describe, it, expect } from 'vitest'
import { computeParallax } from '@/lib/motion/useParallax'

const rect = { left: 0, top: 0, width: 200, height: 200 } // centre = (100,100)

describe('computeParallax', () => {
  it('renvoie (0,0) quand la souris est au centre', () => {
    expect(computeParallax(100, 100, rect, 10)).toEqual({ x: 0, y: 0 })
  })
  it('inverse le sens (souris à droite → décalage négatif en x)', () => {
    const { x } = computeParallax(200, 100, rect, 10)
    expect(x).toBeLessThan(0)
  })
  it('borne le décalage à ±strength', () => {
    const { x, y } = computeParallax(10000, 10000, rect, 10)
    expect(x).toBeGreaterThanOrEqual(-10)
    expect(y).toBeGreaterThanOrEqual(-10)
    expect(Math.abs(x)).toBeLessThanOrEqual(10)
    expect(Math.abs(y)).toBeLessThanOrEqual(10)
  })
})
