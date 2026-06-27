import { describe, it, expect, vi, beforeEach } from 'vitest'
import { render, screen } from '@testing-library/react'
import { MotionConfig } from 'motion/react'

vi.mock('@/lib/queries/sante', () => ({ useScore: vi.fn(), useWaterToday: vi.fn() }))
vi.mock('@/lib/queries/entrainement', () => ({ useEntrainementToday: vi.fn() }))
vi.mock('@/lib/queries/skincare', () => ({ useSkincareToday: vi.fn() }))

import { useScore, useWaterToday } from '@/lib/queries/sante'
import { useEntrainementToday } from '@/lib/queries/entrainement'
import { useSkincareToday } from '@/lib/queries/skincare'
import { Deck } from '@/components/deck/Deck'
import { GROUP_ORDER } from '@/lib/modules'

beforeEach(() => {
  vi.mocked(useScore).mockReturnValue({ data: undefined, isLoading: false, isError: true } as ReturnType<typeof useScore>)
  vi.mocked(useWaterToday).mockReturnValue({ data: undefined, isLoading: false, isError: true } as ReturnType<typeof useWaterToday>)
  vi.mocked(useEntrainementToday).mockReturnValue({ data: undefined, isLoading: false, isError: true } as ReturnType<typeof useEntrainementToday>)
  vi.mocked(useSkincareToday).mockReturnValue({ data: undefined, isLoading: false, isError: true } as ReturnType<typeof useSkincareToday>)
})

describe('Deck', () => {
  it('rend une section par groupe + la section Corps', () => {
    render(
      <MotionConfig reducedMotion="always">
        <Deck />
      </MotionConfig>,
    )
    // Corps remplace l'intitulé du groupe Santé & Performance.
    expect(screen.getByRole('region', { name: 'Corps' })).toBeInTheDocument()
    // Les autres groupes apparaissent par leur intitulé.
    const others = GROUP_ORDER.filter((g) => g !== 'Santé & Performance')
    for (const g of others) {
      expect(screen.getByRole('region', { name: g })).toBeInTheDocument()
    }
  })

  it('affiche la section intro quand fournie', () => {
    render(
      <MotionConfig reducedMotion="always">
        <Deck intro={<p>Bonjour</p>} />
      </MotionConfig>,
    )
    expect(screen.getByText('Bonjour')).toBeInTheDocument()
  })
})
