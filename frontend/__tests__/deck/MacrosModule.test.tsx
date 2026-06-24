import { describe, it, expect, vi, beforeEach } from 'vitest'
import { render, screen } from '@testing-library/react'
import { MotionConfig } from 'motion/react'

vi.mock('@/lib/queries/sante', () => ({ useScore: vi.fn(), useWaterToday: vi.fn() }))
import { useScore, useWaterToday } from '@/lib/queries/sante'
import { MacrosModule } from '@/components/deck/modules/MacrosModule'

const mockScore = vi.mocked(useScore)
const mockWater = vi.mocked(useWaterToday)

function renderModule() {
  return render(
    <MotionConfig reducedMotion="always">
      <MacrosModule />
    </MotionConfig>,
  )
}

beforeEach(() => {
  mockScore.mockReset()
  mockWater.mockReset()
})

describe('MacrosModule', () => {
  it('affiche calories du jour + hydratation, drill-in /sante', () => {
    mockScore.mockReturnValue({
      data: { date: '2026-06-24', score: 70, composantes: { sommeil: 1, sport: 1, nutrition: 1 }, details: { sommeil_h: 7, sessions_7j: 3, kcal_consommees: 1840, kcal_cible: 2100 } },
      isLoading: false, isError: false,
    } as ReturnType<typeof useScore>)
    mockWater.mockReturnValue({
      data: { date: '2026-06-24', eau_ml: 1500, cible_ml: 2500, pct: 60 }, isLoading: false, isError: false,
    } as ReturnType<typeof useWaterToday>)
    renderModule()
    expect(screen.getByText('1840').className).toContain('tabular-nums')
    expect(screen.getByText(/2100/)).toBeInTheDocument()
    expect(screen.getByText(/60\s*%/)).toBeInTheDocument()
    expect(screen.getByRole('link', { name: /nutrition|macros|santé/i })).toHaveAttribute('href', '/sante')
  })

  it('skeleton au chargement', () => {
    mockScore.mockReturnValue({ data: undefined, isLoading: true, isError: false } as ReturnType<typeof useScore>)
    mockWater.mockReturnValue({ data: undefined, isLoading: true, isError: false } as ReturnType<typeof useWaterToday>)
    renderModule()
    expect(screen.getByTestId('macros-skeleton')).toBeInTheDocument()
  })
})
