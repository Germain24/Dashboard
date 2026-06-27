import { describe, it, expect, vi, beforeEach } from 'vitest'
import { render, screen } from '@testing-library/react'
import { MotionConfig } from 'motion/react'

vi.mock('@/lib/queries/sante', () => ({ useScore: vi.fn(), useWaterToday: vi.fn() }))
vi.mock('@/lib/queries/entrainement', () => ({ useEntrainementToday: vi.fn() }))
vi.mock('@/lib/queries/skincare', () => ({ useSkincareToday: vi.fn() }))

import { useScore, useWaterToday } from '@/lib/queries/sante'
import { useEntrainementToday } from '@/lib/queries/entrainement'
import { useSkincareToday } from '@/lib/queries/skincare'
import { CorpsExperience } from '@/components/deck/experiences/CorpsExperience'

beforeEach(() => {
  vi.mocked(useScore).mockReturnValue({
    data: { date: '2026-06-24', score: 78, composantes: { sommeil: 80, sport: 70, nutrition: 84 }, details: { sommeil_h: 7.5, sessions_7j: 4, kcal_consommees: 1840, kcal_cible: 2100 } },
    isLoading: false, isError: false,
  } as ReturnType<typeof useScore>)
  vi.mocked(useWaterToday).mockReturnValue({ data: { date: '2026-06-24', eau_ml: 1500, cible_ml: 2500, pct: 60 }, isLoading: false, isError: false } as ReturnType<typeof useWaterToday>)
  vi.mocked(useEntrainementToday).mockReturnValue({ data: { date: '2026-06-24', weekday: 2, jour_label: 'Push', programme_jour_id: 1, slots: [{ label: 'Développé couché' }], seance_en_cours: null, kcal_estimees: 0, poids_corps_kg: 70, mesocycle: null }, isLoading: false, isError: false } as ReturnType<typeof useEntrainementToday>)
  vi.mocked(useSkincareToday).mockReturnValue({ data: { date: '2026-06-24', AM: [], PM: [{}], due: [{}] }, isLoading: false, isError: false } as ReturnType<typeof useSkincareToday>)
})

describe('CorpsExperience', () => {
  it('compose le titre Corps et les 5 modules', () => {
    render(
      <MotionConfig reducedMotion="always">
        <CorpsExperience index={2} />
      </MotionConfig>,
    )
    expect(screen.getByRole('region', { name: 'Corps' })).toBeInTheDocument()
    expect(screen.getByRole('heading', { name: 'Corps' })).toBeInTheDocument()
    expect(screen.getByText('78')).toBeInTheDocument()            // score héros
    expect(screen.getByText('Macros')).toBeInTheDocument()        // macros
    expect(screen.getByText('7 h 30')).toBeInTheDocument()        // sommeil
    expect(screen.getByText('Push')).toBeInTheDocument()          // séance
    expect(screen.getByText(/dû/)).toBeInTheDocument()            // skincare
  })
})
