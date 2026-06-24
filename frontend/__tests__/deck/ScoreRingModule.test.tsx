import { describe, it, expect, vi, beforeEach } from 'vitest'
import { render, screen } from '@testing-library/react'
import { MotionConfig } from 'motion/react'

vi.mock('@/lib/queries/sante', () => ({ useScore: vi.fn() }))
import { useScore } from '@/lib/queries/sante'
import { ScoreRingModule } from '@/components/deck/modules/ScoreRingModule'

const mockUseScore = vi.mocked(useScore)

function renderModule() {
  return render(
    <MotionConfig reducedMotion="always">
      <ScoreRingModule />
    </MotionConfig>,
  )
}

beforeEach(() => mockUseScore.mockReset())

describe('ScoreRingModule', () => {
  it('affiche le score en tabular-nums et un drill-in vers /score', () => {
    mockUseScore.mockReturnValue({
      data: { date: '2026-06-24', score: 78, composantes: { sommeil: 80, sport: 70, nutrition: 84 }, details: { sommeil_h: 7.6, sessions_7j: 4, kcal_consommees: 1840, kcal_cible: 2100 } },
      isLoading: false, isError: false,
    } as ReturnType<typeof useScore>)
    renderModule()
    expect(screen.getByText('78').className).toContain('tabular-nums')
    expect(screen.getByRole('link', { name: /score/i })).toHaveAttribute('href', '/score')
  })

  it('affiche un skeleton au chargement', () => {
    mockUseScore.mockReturnValue({ data: undefined, isLoading: true, isError: false } as ReturnType<typeof useScore>)
    renderModule()
    expect(screen.getByTestId('score-skeleton')).toBeInTheDocument()
  })

  it('affiche — quand le score est indisponible', () => {
    mockUseScore.mockReturnValue({ data: undefined, isLoading: false, isError: true } as ReturnType<typeof useScore>)
    renderModule()
    expect(screen.getByText('—')).toBeInTheDocument()
  })
})
