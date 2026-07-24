import path from "node:path";
import { expect, test } from "@playwright/test";

const REAL_CSV_PATH = path.resolve(__dirname, "../../../backend/tests/fixtures/csv/commande_reelle.csv");

test("parcours principal : démonstration -> optimisation (backend Python réel) -> vue 3D -> navigation entre palettes -> rejets", async ({
  page,
}) => {
  await page.goto("/");
  await expect(page.getByRole("heading", { name: "Palettisation 3D" })).toBeVisible();

  await page.getByRole("button", { name: "Démonstration", exact: true }).click();

  await expect(page.getByRole("tab", { name: "Résultats" })).toBeVisible({ timeout: 15000 });
  await page.getByRole("tab", { name: "Résultats" }).click();

  await page.getByRole("button", { name: "Lancer l'optimisation" }).click();

  // Le calcul est effectué par le backend Python réel (aucune logique de packing côté front).
  await expect(page.getByText("Cartons placés", { exact: true }).first()).toBeVisible({ timeout: 20000 });
  await expect(page.getByText("Palettes générées", { exact: true }).first()).toBeVisible();

  await expect(page.locator("canvas").first()).toBeVisible();

  const palletButtons = page.getByRole("button", { name: /^Palette \d/ });
  const count = await palletButtons.count();
  expect(count).toBeGreaterThan(1);
  await palletButtons.nth(1).click();
  await expect(page.locator("canvas").first()).toBeVisible();

  // Le jeu de démonstration contient un carton hors gabarit : la section des rejets doit
  // afficher son code et le message renvoyé par le backend, jamais recalculés côté client.
  await expect(page.getByRole("heading", { name: "Cartons non placés" })).toBeVisible();
  await expect(page.getByText("HORS-GABARIT")).toBeVisible();
  await expect(page.getByText("HEIGHT_EXCEEDED")).toBeVisible();
});

test("import du CSV réel : plusieurs commandes détectées, sélection, puis calcul", async ({ page }) => {
  await page.goto("/");
  await page.getByRole("button", { name: "Nouvelle simulation", exact: true }).first().click();
  await expect(page.getByRole("tab", { name: "Commande" })).toBeVisible();

  const fileChooserPromise = page.waitForEvent("filechooser");
  await page.getByRole("button", { name: "Importer un CSV" }).click();
  const fileChooser = await fileChooserPromise;
  await fileChooser.setFiles(REAL_CSV_PATH);

  // Le CSV réel contient 6 commandes : le sélecteur multi-commandes doit apparaître.
  await expect(page.getByText("Plusieurs commandes détectées")).toBeVisible({ timeout: 15000 });
  await expect(page.getByText("SO265669-X82921")).toBeVisible();

  await page.getByText("SO265841-X82965").click();
  await page.getByRole("button", { name: "Remplacer la commande" }).click();

  await expect(page.getByText(/référence\(s\), .* carton\(s\) au total/)).toBeVisible();
});

test("affiche un état clair lorsque le backend est indisponible", async ({ page }) => {
  // Simule un backend injoignable en interceptant uniquement l'appel d'optimisation, sans
  // dépendre d'une variable d'environnement (NEXT_PUBLIC_PALLETIZER_API_URL est figée au build).
  await page.route("**/api/v1/palletize", (route) => route.abort("connectionrefused"));

  await page.goto("/");
  await page.getByRole("button", { name: "Démonstration", exact: true }).click();
  await page.getByRole("tab", { name: "Résultats" }).click();
  await page.getByRole("button", { name: "Lancer l'optimisation" }).click();

  await expect(
    page.getByText(/Impossible de joindre le backend|n'a pas répondu|Erreur/i).first()
  ).toBeVisible({ timeout: 10000 });
});
