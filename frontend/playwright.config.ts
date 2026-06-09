import { defineConfig, devices } from '@playwright/test'

/**
 * Config Playwright (#185/#189). Les e2e nécessitent le stack complet lancé
 * (backend FastAPI :8000 + frontend Next :3000) et l'installation des
 * navigateurs : `npx playwright install`.
 *
 * Lancement : démarre le stack (ex. `npm run dev` + backend), puis `npm run test:e2e`.
 */
export default defineConfig({
  testDir: './e2e',
  fullyParallel: true,
  forbidOnly: !!process.env.CI,
  retries: process.env.CI ? 2 : 0,
  reporter: 'list',
  use: {
    baseURL: process.env.E2E_BASE_URL ?? 'http://localhost:3000',
    trace: 'on-first-retry',
  },
  projects: [
    { name: 'chromium', use: { ...devices['Desktop Chrome'] } },
  ],
  // Démarre le frontend automatiquement (le backend doit déjà tourner sur :8000).
  webServer: {
    command: 'npm run dev',
    url: 'http://localhost:3000',
    reuseExistingServer: !process.env.CI,
    timeout: 120_000,
  },
})
