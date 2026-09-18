import { describe, it, expect } from 'vitest'
import { render, screen } from '@testing-library/react'
import { MotionConfig } from 'motion/react'
import { computeTilt, MAX_TILT_DEG, TiltCard } from '@/lib/motion/TiltCard'

const rect = { left: 0, top: 0, width: 100, height: 100 }

describe('computeTilt', () => {
  it('ne dépasse jamais ±MAX_TILT_DEG', () => {
    const { rotateX, rotateY } = computeTilt(99999, -99999, rect, MAX_TILT_DEG)
    expect(Math.abs(rotateX)).toBeLessThanOrEqual(MAX_TILT_DEG)
    expect(Math.abs(rotateY)).toBeLessThanOrEqual(MAX_TILT_DEG)
  })
  it('reste à 0 au centre', () => {
    expect(computeTilt(50, 50, rect, MAX_TILT_DEG)).toEqual({ rotateX: 0, rotateY: 0 })
  })
  it('MAX_TILT_DEG vaut 4 (quiet luxury)', () => {
    expect(MAX_TILT_DEG).toBe(4)
  })
})

describe('TiltCard', () => {
  it('rend ses enfants', () => {
    render(
      <MotionConfig reducedMotion="always">
        <TiltCard>contenu</TiltCard>
      </MotionConfig>,
    )
    expect(screen.getByText('contenu')).toBeInTheDocument()
  })
})
