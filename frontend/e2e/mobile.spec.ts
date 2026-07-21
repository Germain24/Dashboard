import { expect, test } from "@playwright/test";

test.use({
  viewport: { width: 390, height: 844 },
  hasTouch: true,
  isMobile: true,
});

test("navigation Finance utilisable sur mobile sans débordement", async ({ page }) => {
  await page.goto("/finance");

  await expect
    .poll(() =>
      page.evaluate(
        () => document.documentElement.scrollWidth <= document.documentElement.clientWidth + 1,
      ),
    )
    .toBe(true);

  const trigger = page.getByRole("button", { name: "Ouvrir le menu" });
  await expect(trigger).toBeVisible();
  const triggerBox = await trigger.boundingBox();
  expect(triggerBox?.width).toBeGreaterThanOrEqual(44);
  expect(triggerBox?.height).toBeGreaterThanOrEqual(44);

  await trigger.click();
  const drawer = page.getByRole("dialog", { name: "Navigation" });
  await expect(drawer).toBeVisible();
  await expect(page.getByRole("button", { name: "Fermer le menu" })).toBeFocused();
  await expect(drawer.getByRole("link", { name: "Investissement" })).toHaveAttribute(
    "aria-current",
    "page",
  );

  await page.keyboard.press("Escape");
  await expect(drawer).toBeHidden();
  await expect(trigger).toBeFocused();
});

test("l'estimation fiscale reste lisible sur mobile", async ({ page }, testInfo) => {
  await page.goto("/finance");
  await page.getByRole("tab", { name: "Impôts", exact: true }).click();
  await expect(page.getByText("Estimation fiscale CTO", { exact: true })).toBeVisible({ timeout: 35_000 });
  await expect(page.getByText("Comparaison des régimes", { exact: true })).toBeVisible();
  await expect
    .poll(() => page.evaluate(() => document.documentElement.scrollWidth <= document.documentElement.clientWidth + 1))
    .toBe(true);

  await page.getByRole("button", { name: /Voir les ventes/ }).click();
  const dialog = page.getByRole("dialog", { name: /Ventes réalisées/ });
  await expect(dialog).toBeVisible();
  await expect(dialog.locator("tbody tr").first()).toBeVisible({ timeout: 35_000 });
  await expect
    .poll(() => page.evaluate(() => document.documentElement.scrollWidth <= document.documentElement.clientWidth + 1))
    .toBe(true);
  await page.screenshot({ path: testInfo.outputPath("finance-impots-mobile.png") });
});

test("les transactions sont paginées et contenues sur mobile", async ({ page }) => {
  await page.goto("/finance");
  await page.getByRole("tab", { name: "Transactions", exact: true }).click();
  await expect(page.getByText("Transactions enregistrées", { exact: true })).toBeVisible({ timeout: 35_000 });
  await expect(page.getByText(/1-100 sur \d+/)).toBeVisible();
  await expect
    .poll(() => page.evaluate(() => document.documentElement.scrollWidth <= document.documentElement.clientWidth + 1))
    .toBe(true);

  await page.getByRole("button", { name: "Page suivante" }).click();
  await expect(page.getByText(/101-200 sur \d+/)).toBeVisible();
});
