import { defineConfig, devices } from "@playwright/test";
import path from "node:path";
import { fileURLToPath } from "node:url";

// Starts the real backend with the mock model and Vite with its /api proxy.
// Needs `make setup` first (backend venv at backend/.venv).
const python = process.platform === "win32" ? path.join(".venv", "Scripts", "python") : path.join(".venv", "bin", "python");
const backendDir = fileURLToPath(new URL("../backend", import.meta.url));

export default defineConfig({
  testDir: "./e2e",
  timeout: 90_000,
  expect: { timeout: 15_000 },
  fullyParallel: false,
  workers: 1,
  retries: process.env.CI ? 1 : 0,
  reporter: process.env.CI ? "list" : [["list"], ["html", { open: "never" }]],
  use: {
    baseURL: "http://localhost:5173",
    trace: "retain-on-failure",
    screenshot: "only-on-failure",
  },
  projects: [
    {
      name: "phone-360",
      use: { ...devices["Desktop Chrome"], viewport: { width: 360, height: 760 }, isMobile: false, hasTouch: true },
    },
    {
      name: "desktop-1280",
      use: { ...devices["Desktop Chrome"], viewport: { width: 1280, height: 900 } },
    },
  ],
  webServer: [
    {
      command: `${python} -m alembic upgrade head && ${python} -m uvicorn app.main:app --port 8000`,
      cwd: backendDir,
      url: "http://localhost:8000/api/health",
      reuseExistingServer: !process.env.CI,
      timeout: 60_000,
      env: {
        LLM_PROVIDER: "mock",
        APP_ENV: "test",
        DATABASE_URL: process.env.E2E_DATABASE_URL ?? "sqlite:///./e2e.db",
        FREE_PLAN_MAX_CAMPAIGNS: "0",
      },
    },
    {
      command: "npm run dev -- --port 5173 --strictPort",
      url: "http://localhost:5173",
      reuseExistingServer: !process.env.CI,
      timeout: 60_000,
    },
  ],
});
