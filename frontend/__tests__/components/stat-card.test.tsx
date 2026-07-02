import { describe, it, expect } from 'vitest'
import { render, screen } from '@testing-library/react'
import { MotionConfig } from 'motion/react'
import { StatCard } from '@/components/ui/stat-card'

const reduced = (ui: React.ReactNode) =>
  render(<MotionConfig reducedMotion="always">{ui}</MotionConfig>)

describe('StatCard', () => {
  it('affiche une valeur string telle quelle', () => {
    reduced(<StatCard label="Poids" value="57,2 kg" />)
    expect(screen.getByText('57,2 kg')).toBeInTheDocument()
  })

  it('affiche une valeur numérique entière (count-up, valeur finale sous reduced-motion)', () => {
    reduced(<StatCard label="Séances" value={42} />)
    expect(screen.getByText('42')).toBeInTheDocument()
  })

  it('préserve les décimales de la valeur numérique (format fr-CA)', () => {
    reduced(<StatCard label="Ratio" value={1.25} />)
    expect(screen.getByText('1,25')).toBeInTheDocument()
  })
})
