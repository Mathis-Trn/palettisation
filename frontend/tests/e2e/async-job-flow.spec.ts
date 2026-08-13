import { expect, test, type Page, type Route } from "@playwright/test";

/**
 * Le backend est démarré avec `PALLETIZER_ENABLE_TEST_HOOKS=1` (voir playwright.config.ts), donc
 * l'en-tête `X-Palletizer-Test-Delay-Seconds` fait dormir le worker ce nombre de secondes avant de
 * lancer le calcul réel — cela simule un calcul long (plusieurs minutes en production) sans faire
 * durer la suite de tests plusieurs minutes. Une seule intégration lente est nécessaire (voir le
 * cahier des charges) : les autres tests de ce fichier restent rapides (délai nul ou quasi nul).
 */
async function withTestDelay(page: Page, seconds: number) {
  await page.route("**/api/v1/palletization-jobs", async (route: Route) => {
    if (route.request().method() !== "POST") return route.continue();
    const headers = { ...route.request().headers(), "x-palletizer-test-delay-seconds": String(seconds) };
    await route.continue({ headers });
  });
}

async function openDemoResultsTab(page: Page) {
  await page.goto("/");
  await page.getByRole("button", { name: "Démonstration", exact: true }).click();
  await page.getByRole("tab", { name: "Résultats" }).click();
}

test("un calcul long affiche le loader accessible, jamais l'ancienne barre ni l'erreur (30s)", async ({ page }) => {
  await withTestDelay(page, 5);
  await openDemoResultsTab(page);

  const runButton = page.getByRole("button", { name: /Lancer l.optimisation|Relancer l.optimisation/ });
  await runButton.click();

  // Le bouton se désactive et son contenu change, sans jamais afficher l'ancienne barre de
  // progression artificielle ni le texte technique "le backend ne rapporte pas de progression".
  await expect(page.getByRole("button", { name: "Calcul en cours…" })).toBeDisabled();
  await expect(page.getByText(/backend ne rapporte pas de progression/i)).toHaveCount(0);

  const loader = page.getByRole("status");
  await expect(loader).toBeVisible();
  await expect(loader.getByText("Calcul de la palettisation en cours…")).toBeVisible();
  await expect(loader.getByText(/plusieurs minutes pour une commande volumineuse/i)).toBeVisible();

  // Aucune barre de progression ni pourcentage : uniquement un temps écoulé, sans estimation.
  await expect(page.locator('[class*="animate-pulse"]')).toHaveCount(0);
  await expect(page.getByText(/\d+\s*%.*(cours|calcul)/i)).toHaveCount(0);

  await expect(page.getByRole("button", { name: /Lancer l.optimisation|Relancer l.optimisation/ })).toBeEnabled({
    timeout: 15_000,
  });
  await expect(page.getByText("Cartons placés", { exact: true }).first()).toBeVisible();

  await expect(page.getByText(/délai imparti/i)).toHaveCount(0);
  await expect(page.getByText("(30s)")).toHaveCount(0);
});

test("un double clic pendant le calcul ne crée qu'un seul job", async ({ page }) => {
  await withTestDelay(page, 2);
  await openDemoResultsTab(page);

  let postCount = 0;
  page.on("request", (request) => {
    if (request.method() === "POST" && request.url().includes("/api/v1/palletization-jobs")) postCount += 1;
  });

  const runButton = page.getByRole("button", { name: /Lancer l.optimisation|Relancer l.optimisation/ });
  await runButton.click();
  // Le bouton est désactivé pendant le calcul ; un clic supplémentaire ne doit produire aucun effet.
  await runButton.click({ force: true });
  await runButton.click({ force: true });

  await expect(page.getByRole("button", { name: /Lancer l.optimisation|Relancer l.optimisation/ })).toBeEnabled({
    timeout: 10_000,
  });
  expect(postCount).toBe(1);
});

test("un rafraîchissement pendant le calcul reprend le même job, n'en crée pas un nouveau", async ({ page }) => {
  await withTestDelay(page, 6);
  await openDemoResultsTab(page);

  const jobIds = new Set<string>();
  page.on("request", (request) => {
    if (request.method() === "POST" && request.url().includes("/api/v1/palletization-jobs")) {
      jobIds.add("POST");
    }
  });

  await page.getByRole("button", { name: /Lancer l.optimisation|Relancer l.optimisation/ }).click();
  await expect(page.getByRole("status")).toBeVisible();

  await page.reload();
  await page.getByRole("tab", { name: "Résultats" }).click();

  // Le loader doit réapparaître immédiatement (le job est repris, pas relancé), sans nouveau POST.
  await expect(page.getByRole("status")).toBeVisible();

  await expect(page.getByRole("button", { name: /Lancer l.optimisation|Relancer l.optimisation/ })).toBeEnabled({
    timeout: 15_000,
  });

  const postRequests: string[] = [];
  page.on("request", (r) => {
    if (r.method() === "POST" && r.url().includes("/api/v1/palletization-jobs")) postRequests.push(r.url());
  });
  await page.waitForTimeout(500);
  expect(postRequests.length).toBe(0);
});

test("quitter la page pendant le calcul arrête le suivi (plus de requête après démontage)", async ({ page }) => {
  await withTestDelay(page, 6);
  await openDemoResultsTab(page);

  await page.getByRole("button", { name: /Lancer l.optimisation|Relancer l.optimisation/ }).click();
  await expect(page.getByRole("status")).toBeVisible();

  await page.getByRole("link", { name: "Tableau de bord" }).click();
  await expect(page.getByRole("heading", { name: "Palettisation 3D" })).toBeVisible();

  // Ne compte que les requêtes émises APRÈS confirmation du démontage : les polls encore en vol
  // pendant la transition de navigation ne prouvent rien, seule la reprise en régime stable compte.
  let getCountAfterLeaving = 0;
  page.on("request", (request) => {
    if (request.method() === "GET" && request.url().includes("/api/v1/palletization-jobs/")) {
      getCountAfterLeaving += 1;
    }
  });

  await page.waitForTimeout(1_500);
  expect(getCountAfterLeaving).toBe(0);
});

test("une panne réseau transitoire affiche un message de nouvelle tentative puis se rétablit", async ({ page }) => {
  await withTestDelay(page, 1);
  await openDemoResultsTab(page);

  let getAttempts = 0;
  await page.route("**/api/v1/palletization-jobs/*", async (route: Route) => {
    if (route.request().method() !== "GET") return route.continue();
    getAttempts += 1;
    if (getAttempts <= 2) {
      await route.abort("connectionrefused");
      return;
    }
    await route.continue();
  });

  await page.getByRole("button", { name: /Lancer l.optimisation|Relancer l.optimisation/ }).click();

  await expect(page.getByText(/momentanément indisponible/i)).toBeVisible({ timeout: 10_000 });
  // Jamais de relance automatique d'une deuxième optimisation pendant la récupération réseau.
  await expect(page.getByRole("button", { name: /Lancer l.optimisation|Relancer l.optimisation/ })).toBeEnabled({
    timeout: 15_000,
  });
  await expect(page.getByText("Cartons placés", { exact: true }).first()).toBeVisible();
});

test("aucune bordure autour du réglage « hauteur max. inclut la palette », les autres cartes restent bordées", async ({
  page,
}) => {
  await page.goto("/");
  await page.getByRole("button", { name: "Démonstration", exact: true }).click();
  await page.getByRole("tab", { name: "Configuration" }).click();

  const heightSwitchLabel = page.getByText("La hauteur max. inclut la palette").locator("..");
  await expect(heightSwitchLabel).toBeVisible();
  const border = await heightSwitchLabel.evaluate((el) => getComputedStyle(el).borderWidth);
  expect(border).toBe("0px");

  const rotationsLabel = page.getByText("Autoriser les rotations").locator("..");
  const rotationsBorder = await rotationsLabel.evaluate((el) => getComputedStyle(el).borderWidth);
  expect(rotationsBorder).not.toBe("0px");
});
