import { describe, it, expect } from 'vitest'
import { fadeUp, staggerContainer, STAGGER_STEP } from '@/lib/motion/variants'
import { springs } from '@/lib/motion/tokens'

describe('motion variants', () => {
  it('fadeUp part masqué et décalé vers le bas, arrive en place', () => {
    expect(fadeUp.hidden).toMatchObject({ opacity: 0 })
    expect((fadeUp.hidden as { y: number }).y).toBeGreaterThan(0)
    expect(fadeUp.visible).toMatchObject({ opacity: 1, y: 0 })
    expect((fadeUp.visible as { transition: unknown }).transition).toBe(springs.soft)
  })
  it('staggerContainer cascade ses enfants', () => {
    const v = staggerContainer.visible as { transition: { staggerChildren: number } }
    expect(v.transition.staggerChildren).toBeCloseTo(STAGGER_STEP)
  })
})
