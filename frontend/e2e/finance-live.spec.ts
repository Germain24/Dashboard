import { expect, test } from "@playwright/test";

test("le suivi Finance quitte son état de chargement", async ({ page }) => {
  const pageErrors: string[] = [];
  const failedRequests: string[] = [];
  page.on("pageerror", (error) => pageErrors.push(error.message));
  page.on("requestfailed", (request) => {
    if (["fetch", "xhr"].includes(request.resourceType())) {
      failedRequests.push(`${request.url()} (${request.failure()?.errorText ?? "échec"})`);
    }
  });

  await page.goto("/finance");
  try {
    await expect(page.getByText("Valeur totale", { exact: true })).toBeVisible({ timeout: 35_000 });
  } catch (error) {
    throw new Error(
      [
        error instanceof Error ? error.message : String(error),
        `Erreurs page: ${pageErrors.join(" | ") || "aucune"}`,
        `Requêtes échouées: ${failedRequests.join(" | ") || "aucune"}`,
      ].join("\n"),
    );
  }

  expect(pageErrors).toEqual([]);
  expect(failedRequests).toEqual([]);
});

test("tous les onglets Finance chargent sans erreur", async ({ page }, testInfo) => {
  test.setTimeout(120_000);
  const pageErrors: string[] = [];
  const serverErrors: string[] = [];
  const failedRequests: string[] = [];
  page.on("pageerror", (error) => pageErrors.push(error.message));
  page.on("requestfailed", (request) => {
    if (["fetch", "xhr"].includes(request.resourceType())) {
      failedRequests.push(`${request.method()} ${request.url()} (${request.failure()?.errorText ?? "échec"})`);
    }
  });
  page.on("response", (response) => {
    if (["fetch", "xhr"].includes(response.request().resourceType()) && response.status() >= 500) {
      serverErrors.push(`${response.status()} ${response.url()}`);
    }
  });

  await page.goto("/finance");
  const checks: Array<[string, RegExp]> = [
    ["Suivi", /^Valeur totale$/],
    ["Portefeuille", /Ajouter une position/],
    ["Composition", /Détail des positions|Aucune position/],
    ["Rebalancing", /Affichage uniquement|Aucune analyse Buffett disponible/],
    ["Buffett", /Historique des analyses|Aucune analyse/],
    ["Transactions", /^Transactions enregistrées$/],
    ["Patrimoine", /^Patrimoine net$/],
    ["Impôts", /^Estimation fiscale CTO$/],
  ];

  for (const [tabName, visibleText] of checks) {
    const tab = page.getByRole("tab", { name: tabName, exact: true });
    await tab.click();
    await expect(tab).toHaveAttribute("aria-selected", "true");
    await expect(page.getByText(visibleText).first()).toBeVisible({ timeout: 35_000 });
    await expect
      .poll(() => page.evaluate(() => document.documentElement.scrollWidth <= document.documentElement.clientWidth + 1))
      .toBe(true);
  }

  await expect(page.getByText("Comparaison des régimes", { exact: true })).toBeVisible();
  await page.screenshot({ path: testInfo.outputPath("finance-impots-desktop.png"), fullPage: true });
  expect(pageErrors).toEqual([]);
  expect(serverErrors).toEqual([]);
  expect(failedRequests).toEqual([]);
});
