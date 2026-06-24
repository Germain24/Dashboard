import { describe, it, expect } from 'vitest'
import { render, screen } from '@testing-library/react'
import { MotionConfig } from 'motion/react'
import { AnimatedNumber } from '@/lib/motion/AnimatedNumber'

function renderReduced(ui: React.ReactNode) {
  return render(<MotionConfig reducedMotion="always">{ui}</MotionConfig>)
}

describe('AnimatedNumber', () => {
  it('affiche la valeur finale immédiatement sous reduced-motion', () => {
    renderReduced(<AnimatedNumber value={78} />)
    expect(screen.getByText('78')).toBeInTheDocument()
  })
  it('applique la classe transmise (ex. tabular-nums)', () => {
    renderReduced(<AnimatedNumber value={42} className="tabular-nums" />)
    expect(screen.getByText('42').className).toContain('tabular-nums')
  })
  it('utilise le format fourni', () => {
    renderReduced(<AnimatedNumber value={1840} format={(v) => `${Math.round(v)} kcal`} />)
    expect(screen.getByText('1840 kcal')).toBeInTheDocument()
  })
})
