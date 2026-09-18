import { describe, it, expect, vi, beforeEach } from 'vitest'
import { render, screen } from '@testing-library/react'
import { MotionConfig } from 'motion/react'

vi.mock('@/lib/queries/skincare', () => ({ useSkincareToday: vi.fn() }))
import { useSkincareToday } from '@/lib/queries/skincare'
import { SkincareModule } from '@/components/deck/modules/SkincareModule'

const mockToday = vi.mocked(useSkincareToday)
beforeEach(() => mockToday.mockReset())

function renderModule() {
  return render(
    <MotionConfig reducedMotion="always">
      <SkincareModule />
    </MotionConfig>,
  )
}

describe('SkincareModule', () => {
  it('affiche le nombre de produits dus + drill-in /skincare', () => {
    mockToday.mockReturnValue({
      data: { date: '2026-06-24', AM: [], PM: [{}, {}], due: [{}, {}, {}] }, isLoading: false, isError: false,
    } as unknown as ReturnType<typeof useSkincareToday>)
    renderModule()
    // Le chiffre est dans son propre span tabular-nums (« 3 » + « dû »).
    const count = screen.getByText('3')
    expect(count.className).toContain('tabular-nums')
    expect(count.closest('p')?.textContent).toMatch(/3\s*dû/)
    expect(screen.getByRole('link', { name: /skincare/i })).toHaveAttribute('href', '/skincare')
  })

  it('affiche « à jour » quand rien n\'est dû', () => {
    mockToday.mockReturnValue({
      data: { date: '2026-06-24', AM: [], PM: [], due: [] }, isLoading: false, isError: false,
    } as unknown as ReturnType<typeof useSkincareToday>)
    renderModule()
    expect(screen.getByText(/à jour/i)).toBeInTheDocument()
  })

  it('affiche un skeleton au chargement', () => {
    mockToday.mockReturnValue({ data: undefined, isLoading: true, isError: false } as unknown as ReturnType<typeof useSkincareToday>)
    renderModule()
    expect(screen.getByTestId('skincare-skeleton')).toBeInTheDocument()
  })
})
