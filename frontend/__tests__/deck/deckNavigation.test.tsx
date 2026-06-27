import { describe, it, expect, vi } from 'vitest'
import { render, screen } from '@testing-library/react'
import { nextSectionIndex } from '@/components/deck/useDeckNavigation'
import { DeckRail } from '@/components/deck/DeckRail'

describe('nextSectionIndex', () => {
  it('avance avec ArrowDown / ArrowRight (borné en haut)', () => {
    expect(nextSectionIndex(0, 'ArrowDown', 3)).toBe(1)
    expect(nextSectionIndex(2, 'ArrowRight', 3)).toBe(2) // borné
  })
  it('recule avec ArrowUp / ArrowLeft (borné à 0)', () => {
    expect(nextSectionIndex(1, 'ArrowUp', 3)).toBe(0)
    expect(nextSectionIndex(0, 'ArrowLeft', 3)).toBe(0) // borné
  })
  it('ignore les autres touches', () => {
    expect(nextSectionIndex(1, 'Enter', 3)).toBe(1)
  })
})

describe('DeckRail', () => {
  it('rend un point par section et marque l\'actif', () => {
    const onJump = vi.fn()
    render(<DeckRail total={3} active={1} labels={['A', 'B', 'C']} onJump={onJump} />)
    const buttons = screen.getAllByRole('button')
    expect(buttons).toHaveLength(3)
    expect(buttons[1]).toHaveAttribute('aria-current', 'true')
  })
})
