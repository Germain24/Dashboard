import { describe, it, expect, vi, beforeEach } from 'vitest'
import { render, screen } from '@testing-library/react'
import { MotionConfig } from 'motion/react'

vi.mock('@/lib/queries/sante', () => ({ useScore: vi.fn() }))
import { useScore } from '@/lib/queries/sante'
import { SleepModule, formatSleepHours } from '@/components/deck/modules/SleepModule'

const mockScore = vi.mocked(useScore)
beforeEach(() => mockScore.mockReset())

describe('formatSleepHours', () => {
  it('formate les heures décimales en « h min »', () => {
    expect(formatSleepHours(7.5)).toBe('7 h 30')
    expect(formatSleepHours(8)).toBe('8 h 00')
  })
  it('renvoie — pour null', () => {
    expect(formatSleepHours(null)).toBe('—')
  })
})

describe('SleepModule', () => {
  it('affiche la durée et un drill-in /score', () => {
    mockScore.mockReturnValue({
      data: { date: '2026-06-24', score: 70, composantes: { sommeil: 1, sport: 1, nutrition: 1 }, details: { sommeil_h: 7.5, sessions_7j: 3, kcal_consommees: 1, kcal_cible: 1 } },
      isLoading: false, isError: false,
    } as ReturnType<typeof useScore>)
    render(
      <MotionConfig reducedMotion="always">
        <SleepModule />
      </MotionConfig>,
    )
    expect(screen.getByText('7 h 30').className).toContain('tabular-nums')
    expect(screen.getByRole('link', { name: /sommeil/i })).toHaveAttribute('href', '/score')
  })
})
