import '@testing-library/jest-dom/vitest'

// motion/react émet un avertissement dev quand reduced-motion est actif (notre
// défaut de test déterministe, cf. le polyfill matchMedia ci-dessous). On filtre
// uniquement ce message pour garder la sortie de test propre, sans masquer le reste.
const __origWarn = console.warn
console.warn = (...args: unknown[]) => {
  if (typeof args[0] === 'string' && args[0].includes('Reduced Motion')) return
  __origWarn(...(args as []))
}

// jsdom n'implémente pas window.matchMedia, dont motion/react a besoin pour
// useReducedMotion() (qui lit la media query — pas MotionConfig). On force donc
// prefers-reduced-motion: reduce → les tests du Deck rendent l'état final/statique
// de façon déterministe (count-up et parallax désactivés). Le rendu animé réel
// est couvert par les tests visuels Playwright (e2e), pas par jsdom.
if (typeof window !== 'undefined' && typeof window.matchMedia !== 'function') {
  window.matchMedia = (query: string): MediaQueryList =>
    ({
      matches:
        query.includes('prefers-reduced-motion') &&
        !query.includes('no-preference'),
      media: query,
      onchange: null,
      addEventListener: () => {},
      removeEventListener: () => {},
      addListener: () => {},
      removeListener: () => {},
      dispatchEvent: () => false,
    }) as unknown as MediaQueryList
}

// jsdom n'implémente pas IntersectionObserver, dont motion/react a besoin pour
// useInView() (orchestration d'entrée des DeckSection). Le mock déclenche
// immédiatement isIntersecting: true à l'observe → les sections sont « visibles »
// de façon déterministe dans les tests. Le comportement réel au scroll est
// couvert par Playwright (e2e), pas par jsdom.
if (typeof globalThis !== 'undefined' && typeof globalThis.IntersectionObserver === 'undefined') {
  class MockIntersectionObserver {
    root = null
    rootMargin = ''
    thresholds: number[] = []
    constructor(private cb: IntersectionObserverCallback) {}
    observe(el: Element) {
      this.cb(
        [{ isIntersecting: true, target: el } as IntersectionObserverEntry],
        this as unknown as IntersectionObserver,
      )
    }
    unobserve() {}
    disconnect() {}
    takeRecords(): IntersectionObserverEntry[] {
      return []
    }
  }
  globalThis.IntersectionObserver =
    MockIntersectionObserver as unknown as typeof IntersectionObserver
}
