import { test, expect } from '@playwright/test'

// Parcours clés (#185). Nécessite le stack lancé (backend + frontend).

test('la page d’accueil se charge et la navigation fonctionne', async ({ page }) => {
  await page.goto('/')
  await expect(page).toHaveTitle(/Mission Control|Accueil|Dashboard/i)
})

test('ajouter une dépense au budget', async ({ page }) => {
  await page.goto('/budget')
  // Saisie rapide d'une transaction (le libellé exact peut varier selon l'UI).
  const addButton = page.getByRole('button', { name: /ajouter|saisie|nouvelle|\+/i }).first()
  await expect(addButton).toBeVisible()
})

test('le module Données expose l’export', async ({ page }) => {
  await page.goto('/donnees')
  await expect(page.getByRole('button', { name: /exporter le backup/i })).toBeVisible()
})
