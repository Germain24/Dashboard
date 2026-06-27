import { describe, it, expect } from 'vitest'
import { render, screen } from '@testing-library/react'
import { MotionConfig } from 'motion/react'
import { Wallet } from 'lucide-react'
import { GenericGroupExperience } from '@/components/deck/experiences/GenericGroupExperience'

const group = {
  group: 'Finances & Ingénierie' as const,
  items: [
    { slug: 'budget', label: 'Budget', description: 'Trésorerie', icon: Wallet, group: 'Finances & Ingénierie' as const, ready: true },
  ],
}

describe('GenericGroupExperience', () => {
  it('rend le groupe et ses cartes-liens', () => {
    render(
      <MotionConfig reducedMotion="always">
        <GenericGroupExperience group={group} index={1} />
      </MotionConfig>,
    )
    expect(screen.getByRole('region', { name: 'Finances & Ingénierie' })).toBeInTheDocument()
    expect(screen.getByRole('link', { name: /Budget/ })).toHaveAttribute('href', '/budget')
  })
})
