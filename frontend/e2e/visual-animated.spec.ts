import { test, expect } from '@playwright/test'

// Régression visuelle sur les états ANIMÉS stabilisés (§6.2 de la feuille de
// route P2). `visual.spec.ts` couvre les pages au repos ; ici on capture des
// écrans dont le rendu final dépend d'une transition (barres `.bar-fill`,
// 0.45s, dont la largeur inline arrive avec les données TanStack).
//
// Déterminisme : `animations: 'disabled'` fait avancer Playwright toutes les
// animations/transitions CSS à leur état final avant la capture, puis les fige.
// C'est ce qui rend la capture reproductible — un `waitForTimeout` seul ne
// garantit rien (la transition ne démarre qu'à l'arrivée des données).
//
// 1er run : `npm run test:e2e:update` pour créer les références.

/** Attend que les barres de progression aient reçu leur largeur définitive. */
async function attendreBarresStabilisees(page: import('@playwright/test').Page) {
  const barres = page.locator('.bar-fill')
  const n = await barres.count()
  if (n === 0) return

  // La largeur inline est posée par le composant au moment où la donnée arrive :
  // tant qu'elle est absente/nulle, la transition n'a pas commencé et capturer
  // maintenant figerait une barre vide.
  await expect
    .poll(
      async () =>
        barres.evaluateAll((els) =>
          els.filter((el) => {
            const w = (el as HTMLElement).style.width
            return w !== '' && w !== '0%' && w !== '0px'
          }).length,
        ),
      { timeout: 10_000 },
    )
    .toBeGreaterThan(0)
}

test('score — barres de composantes stabilisées', async ({ page }) => {
  await page.goto('/score')

  // La page monte des Skeleton tant que la requête n'a pas répondu.
  await expect(page.getByRole('heading', { name: 'Score' })).toBeVisible()
  await attendreBarresStabilisees(page)

  await expect(page).toHaveScreenshot('score-anime.png', {
    fullPage: true,
    animations: 'disabled',
    maxDiffPixelRatio: 0.02,
  })
})

test('accueil — état stabilisé après transitions', async ({ page }) => {
  await page.goto('/')
  await attendreBarresStabilisees(page)

  await expect(page).toHaveScreenshot('accueil-anime.png', {
    fullPage: true,
    animations: 'disabled',
    maxDiffPixelRatio: 0.02,
  })
})
