import path from 'path'
import { defineConfig } from 'vitest/config'

export default defineConfig({
  test: {
    environment: 'jsdom',
    globals: true,
    setupFiles: ['./vitest.setup.ts'],
    include: ['**/*.test.{ts,tsx}'],
    exclude: ['node_modules', '.next', 'e2e'],
  },
  esbuild: { jsx: 'automatic' },
  // Neutralise le PostCSS du projet (Tailwind v4) inutile pour les tests.
  css: { postcss: { plugins: [] } },
  resolve: {
    alias: { '@': path.resolve(__dirname, '.') },
  },
})
