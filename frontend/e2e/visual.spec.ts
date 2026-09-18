import { test, expect } from '@playwright/test'

// Régression visuelle (#189). 1er run crée les snapshots de référence
// (`--update-snapshots`), les runs suivants comparent.

test('accueil — snapshot visuel', async ({ page }) => {
  await page.goto('/')
  await expect(page).toHaveScreenshot('accueil.png', { fullPage: true, maxDiffPixelRatio: 0.02 })
})

test('jobs — snapshot visuel', async ({ page }) => {
  await page.goto('/jobs')
  await expect(page).toHaveScreenshot('jobs.png', { fullPage: true, maxDiffPixelRatio: 0.02 })
})
