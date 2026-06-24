import { describe, it, expect, beforeAll } from 'vitest'
import { render, screen } from '@testing-library/react'
import { MotionConfig } from 'motion/react'
import { DeckSection } from '@/components/deck/DeckSection'

// Polyfill IntersectionObserver pour useInView() de motion/react
beforeAll(() => {
  if (typeof IntersectionObserver === 'undefined') {
    ;(global as any).IntersectionObserver = class IntersectionObserver {
      constructor(callback: IntersectionObserverCallback) {
        this.callback = callback
      }
      private callback: IntersectionObserverCallback
      observe() {
        // Dans les tests, supposer que les éléments sont visibles par défaut
        this.callback([{ isIntersecting: true } as any], this as any)
      }
      unobserve() {}
      disconnect() {}
      takeRecords() {
        return []
      }
    } as any
  }
})

describe('DeckSection', () => {
  it('rend une section étiquetée contenant ses enfants', () => {
    render(
      <MotionConfig reducedMotion="always">
        <DeckSection label="Corps" index={2}>
          <p>contenu</p>
        </DeckSection>
      </MotionConfig>,
    )
    const section = screen.getByRole('region', { name: 'Corps' })
    expect(section).toBeInTheDocument()
    expect(section.className).toContain('deck-section')
    expect(screen.getByText('contenu')).toBeInTheDocument()
  })
})
