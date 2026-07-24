import { expect, test } from "@playwright/test";

test("parcours principal : démonstration -> optimisation -> vue 3D -> navigation entre palettes", async ({ page }) => {
  await page.goto("/");
  await expect(page.getByRole("heading", { name: "Palettisation 3D" })).toBeVisible();

  await page.getByRole("button", { name: "Démonstration", exact: true }).click();

  await expect(page.getByRole("tab", { name: "Résultats" })).toBeVisible({ timeout: 15000 });
  await page.getByRole("tab", { name: "Résultats" }).click();

  await page.getByRole("button", { name: "Lancer l'optimisation" }).click();

  await expect(page.getByText("Cartons placés", { exact: true }).first()).toBeVisible({ timeout: 20000 });
  await expect(page.getByText("Palettes générées", { exact: true }).first()).toBeVisible();

  // Vue 3D affichée (canvas WebGL).
  await expect(page.locator("canvas").first()).toBeVisible();

  // Navigation entre palettes (la démonstration génère plusieurs palettes).
  const palletButtons = page.getByRole("button", { name: /^Palette \d/ });
  const count = await palletButtons.count();
  expect(count).toBeGreaterThan(1);

  await palletButtons.nth(1).click();
  await expect(page.locator("canvas").first()).toBeVisible();
});
