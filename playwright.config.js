import { defineConfig, devices } from "@playwright/test";

// Real-browser E2E: Chromium drives the production build served by `vite preview` against a live, throw-away local
// API (fresh SQLite, generated RS256 keys). Nothing external is contacted.
const python = process.env.E2E_PYTHON || (process.platform === "win32" ? "apps/ap-api/.venv/Scripts/python.exe" : "python");
const WEB = "http://127.0.0.1:4173";
const API = "http://127.0.0.1:8765";

export default defineConfig({
  testDir: "tests/e2e",
  timeout: 60_000,
  expect: { timeout: 10_000 },
  fullyParallel: false,
  workers: 1,
  retries: process.env.CI ? 1 : 0,
  reporter: process.env.CI ? [["list"], ["html", { open: "never" }]] : "list",
  use: { baseURL: WEB, trace: "retain-on-failure", screenshot: "only-on-failure", ...devices["Desktop Chrome"] },
  webServer: [
    {
      command: `"${python}" apps/ap-api/scripts/e2e_api.py --port 8765 --cors-origin ${WEB} --token-file .e2e/tokens.json`,
      url: `${API}/health`,
      reuseExistingServer: false,
      timeout: 120_000,
    },
    {
      command: "npm run build && npx vite preview --port 4173 --strictPort --host 127.0.0.1",
      url: WEB,
      reuseExistingServer: false,
      timeout: 180_000,
    },
  ],
});
