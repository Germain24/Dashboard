import '@testing-library/jest-dom/vitest'
import { vi } from 'vitest'

// Mock matchMedia for motion/react to detect reduced motion
window.matchMedia = vi.fn().mockImplementation(query => ({
  matches: query.includes('prefers-reduced-motion'),
  media: query,
  onchange: null,
  addListener: vi.fn(),
  removeListener: vi.fn(),
  addEventListener: vi.fn(),
  removeEventListener: vi.fn(),
  dispatchEvent: vi.fn(),
}))
