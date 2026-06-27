import { test, expect } from '@playwright/test'

// Deck v2 — expérience « Corps » (#prototype). Nécessite le stack lancé
// (frontend :3000 ; le backend peut être absent, les modules dégradent
// proprement). Les snapshots de référence se génèrent au 1er run via
// `npm run test:e2e:update` (non versionnés, cf. visual.spec.ts).

test.describe('Deck v2 — expérience Corps', () => {
  test('la section Corps est présente et atteignable au clavier', async ({ page }) => {
    await page.goto('/')

    // Section Corps présente (région ARIA).
    const corps = page.getByRole('region', { name: 'Corps' })
    await expect(corps).toBeAttached()

    // Le rail de points existe (desktop).
    const rail = page.getByRole('navigation', { name: 'Navigation des sections' })
    await expect(rail).toBeVisible()

    // Navigation clavier : ArrowDown fait défiler vers la section suivante.
    await page.locator('body').press('ArrowDown')
    await page.waitForTimeout(600) // laisse le smooth-scroll se terminer

    // Le titre « Corps » est rendu.
    await expect(page.getByRole('heading', { name: 'Corps' })).toBeAttached()
  })

  test('capture visuelle de la section Corps', async ({ page }) => {
    await page.goto('/')
    const corps = page.getByRole('region', { name: 'Corps' })
    await corps.scrollIntoViewIfNeeded()
    await page.waitForTimeout(800) // entrées + count-up terminés
    await expect(corps).toHaveScreenshot('corps-section.png', { maxDiffPixelRatio: 0.02 })
  })
})
