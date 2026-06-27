import { describe, it, expect, vi, beforeEach } from 'vitest'
import { render, screen } from '@testing-library/react'
import { MotionConfig } from 'motion/react'

vi.mock('@/lib/queries/entrainement', () => ({ useEntrainementToday: vi.fn() }))
import { useEntrainementToday } from '@/lib/queries/entrainement'
import { NextWorkoutModule } from '@/components/deck/modules/NextWorkoutModule'

const mockToday = vi.mocked(useEntrainementToday)
beforeEach(() => mockToday.mockReset())

function renderModule() {
  return render(
    <MotionConfig reducedMotion="always">
      <NextWorkoutModule />
    </MotionConfig>,
  )
}

describe('NextWorkoutModule', () => {
  it('affiche la séance du jour + drill-in /entrainement', () => {
    mockToday.mockReturnValue({
      data: { date: '2026-06-24', weekday: 2, jour_label: 'Push', programme_jour_id: 1, slots: [{ label: 'Développé couché' }], seance_en_cours: null, kcal_estimees: 0, poids_corps_kg: 70, mesocycle: null },
      isLoading: false, isError: false,
    } as unknown as ReturnType<typeof useEntrainementToday>)
    renderModule()
    expect(screen.getByText('Push')).toBeInTheDocument()
    expect(screen.getByText(/Développé couché/)).toBeInTheDocument()
    expect(screen.getByRole('link', { name: /séance|entraînement/i })).toHaveAttribute('href', '/entrainement')
  })

  it('affiche un état repos si aucun bloc', () => {
    mockToday.mockReturnValue({
      data: { date: '2026-06-24', weekday: 6, jour_label: 'Repos', programme_jour_id: null, slots: [], seance_en_cours: null, kcal_estimees: 0, poids_corps_kg: 70, mesocycle: null },
      isLoading: false, isError: false,
    } as unknown as ReturnType<typeof useEntrainementToday>)
    renderModule()
    expect(screen.getByText('Jour de repos')).toBeInTheDocument()
  })
})
