import { defineConfig, devices } from "@playwright/test";

export default defineConfig({
  testDir: "./tests/e2e",
  timeout: 30_000,
  fullyParallel: true,
  reporter: "list",
  use: {
    baseURL: "http://localhost:3000",
    trace: "on-first-retry",
  },
  // Deux serveurs : le backend Python réel (pas de simulation/mock) et le frontend Next.js.
  // NEXT_PUBLIC_PALLETIZER_API_URL (voir .env.local) pointe déjà vers http://localhost:8000.
  // `PALLETIZER_ENABLE_TEST_HOOKS` autorise l'en-tête `X-Palletizer-Test-Delay-Seconds` (voir
  // tests/e2e/async-job-flow.spec.ts) pour simuler un calcul long sans attendre plusieurs minutes ;
  // jamais activé en dehors des tests. `PALLETIZATION_MAX_CONCURRENT_JOBS` est augmenté pour que
  // les jobs de tests concurrents ne se mettent pas en file les uns derrière les autres.
  webServer: [
    {
      command: "python -m uv run uvicorn palletizer.api.main:app --host 0.0.0.0 --port 8000",
      cwd: "../backend",
      url: "http://localhost:8000/health",
      reuseExistingServer: !process.env.CI,
      timeout: 60_000,
      env: { PALLETIZER_ENABLE_TEST_HOOKS: "1", PALLETIZATION_MAX_CONCURRENT_JOBS: "4" },
    },
    {
      command: "npm run dev",
      url: "http://localhost:3000",
      reuseExistingServer: !process.env.CI,
      timeout: 120_000,
      env: { NEXT_PUBLIC_JOB_POLL_INTERVAL_MS: "300" },
    },
  ],
  projects: [{ name: "chromium", use: { ...devices["Desktop Chrome"] } }],
});
