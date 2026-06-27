import { describe, it, expect, vi } from 'vitest'
import { render, screen } from '@testing-library/react'
import { MotionConfig } from 'motion/react'

// Mocks data : on vérifie seulement que la page monte le nouveau Deck.
vi.mock('@/lib/queries/sante', () => ({ useScore: vi.fn(() => ({ isError: true })), useWaterToday: vi.fn(() => ({ isError: true })) }))
vi.mock('@/lib/queries/entrainement', () => ({ useEntrainementToday: vi.fn(() => ({ isError: true })) }))
vi.mock('@/lib/queries/skincare', () => ({ useSkincareToday: vi.fn(() => ({ isError: true })) }))
vi.mock('@/components/home/TodayPanel', () => ({ TodayPanel: () => <div>panel-aujourdhui</div> }))
vi.mock('@/components/Greeting', () => ({ Greeting: () => <div>greeting</div> }))
vi.mock('@/components/HealthBadge', () => ({ HealthBadge: () => <div>health</div> }))

import HomePage from '@/src/app/page'

describe('HomePage', () => {
  it('monte le nouveau Deck avec la section Corps et l\'intro', () => {
    render(
      <MotionConfig reducedMotion="always">
        <HomePage />
      </MotionConfig>,
    )
    expect(screen.getByText('panel-aujourdhui')).toBeInTheDocument()
    expect(screen.getByRole('region', { name: 'Corps' })).toBeInTheDocument()
  })
})
