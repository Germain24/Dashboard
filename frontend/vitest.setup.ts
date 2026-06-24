import '@testing-library/jest-dom/vitest'

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
