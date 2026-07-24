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
  webServer: [
    {
      command: "python -m uv run uvicorn palletizer.api.main:app --host 0.0.0.0 --port 8000",
      cwd: "../backend",
      url: "http://localhost:8000/health",
      reuseExistingServer: !process.env.CI,
      timeout: 60_000,
    },
    {
      command: "npm run dev",
      url: "http://localhost:3000",
      reuseExistingServer: !process.env.CI,
      timeout: 120_000,
    },
  ],
  projects: [{ name: "chromium", use: { ...devices["Desktop Chrome"] } }],
});
