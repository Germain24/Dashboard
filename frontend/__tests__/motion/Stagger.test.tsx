import { describe, it, expect } from 'vitest'
import { render, screen } from '@testing-library/react'
import { MotionConfig } from 'motion/react'
import { StaggerGroup, StaggerItem } from '@/lib/motion/Stagger'

describe('StaggerGroup / StaggerItem', () => {
  it('rend les enfants et applique la className du conteneur', () => {
    render(
      <MotionConfig reducedMotion="always">
        <StaggerGroup className="grid grid-cols-2">
          <StaggerItem>Un</StaggerItem>
          <StaggerItem className="col-span-2">Deux</StaggerItem>
        </StaggerGroup>
      </MotionConfig>,
    )
    expect(screen.getByText('Un')).toBeInTheDocument()
    expect(screen.getByText('Deux').className).toContain('col-span-2')
    expect(screen.getByTestId('stagger-group').className).toContain('grid-cols-2')
  })
})
