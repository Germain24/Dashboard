import { describe, it, expect, beforeAll } from 'vitest'
import { render, screen } from '@testing-library/react'
import { MotionConfig } from 'motion/react'
import { DeckSection } from '@/components/deck/DeckSection'

// Polyfill IntersectionObserver pour useInView() de motion/react
beforeAll(() => {
  if (typeof IntersectionObserver === 'undefined') {
    class MockIntersectionObserver implements IntersectionObserver {
      readonly root = null
      readonly rootMargin = '0px'
      readonly thresholds = [0]

      constructor(private readonly callback: IntersectionObserverCallback) {}

      observe(target: Element) {
        // Dans les tests, supposer que les éléments sont visibles par défaut
        const rect = target.getBoundingClientRect()
        this.callback([{
          time: 0,
          target,
          rootBounds: null,
          boundingClientRect: rect,
          intersectionRect: rect,
          isIntersecting: true,
          intersectionRatio: 1,
        }], this)
      }
      unobserve() {}
      disconnect() {}
      takeRecords() {
        return []
      }
    }
    globalThis.IntersectionObserver = MockIntersectionObserver
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
