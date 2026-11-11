import { defineConfig, devices } from "@playwright/test";

// End-to-end tests drive the real frontend against the real backend. The only
// stand-in is the model: LLM_PROVIDER=fake answers deterministically, so the
// suite needs no API key and cannot flake on a provider.
//
// Both servers are started by Playwright on ports that do not collide with the
// dev stack (13000/18000). Postgres (with pgvector) and Redis must already be
// running — CI provides them as service containers; locally, `docker compose up
// -d postgres redis` and point E2E_DATABASE_URL / E2E_REDIS_URL at them.

const API_PORT = 18090;
const WEB_PORT = 13090;
const API_URL = `http://localhost:${API_PORT}`;
const WEB_URL = `http://localhost:${WEB_PORT}`;
const isCI = Boolean(process.env.CI);

export default defineConfig({
  testDir: "./e2e",
  timeout: 60_000,
  expect: { timeout: 15_000 },
  fullyParallel: false,
  workers: 1,
  forbidOnly: isCI,
  retries: isCI ? 1 : 0,
  reporter: isCI ? [["github"], ["html", { open: "never" }]] : "list",
  use: {
    baseURL: WEB_URL,
    trace: "retain-on-failure",
    screenshot: "only-on-failure",
  },
  projects: [
    {
      name: "chromium",
      use: {
        ...devices["Desktop Chrome"],
        // Locally, use the installed Chrome instead of downloading a browser.
        ...(isCI ? {} : { channel: "chrome" }),
      },
    },
  ],
  webServer: [
    {
      command: `${process.env.E2E_PYTHON || "python"} -m uvicorn app.main:app --port ${API_PORT}`,
      cwd: "../backend",
      url: `${API_URL}/health/ready`,
      timeout: 120_000,
      reuseExistingServer: !isCI,
      stdout: "pipe",
      env: {
        ENVIRONMENT: "development",
        LLM_PROVIDER: "fake",
        DATABASE_URL:
          process.env.E2E_DATABASE_URL ||
          "postgresql+psycopg2://orchestra:orchestra@localhost:5432/orchestra_e2e",
        REDIS_URL: process.env.E2E_REDIS_URL || "redis://localhost:6379/1",
        JWT_SECRET: "e2e-only-secret-not-used-anywhere-else-0123456789",
        CORS_ORIGINS: WEB_URL,
        ALLOWED_HOSTS: "*",
        EMBEDDING_WARMUP_ENABLED: "false",
        // Every run signs up fresh users from one IP.
        SIGNUP_RATE_LIMIT_PER_HOUR: "1000",
      },
    },
    {
      // Built here, not reused, so the bundle always points at the e2e API.
      command: `npx next build && npx next start -p ${WEB_PORT}`,
      url: WEB_URL,
      timeout: 300_000,
      reuseExistingServer: !isCI,
      stdout: "pipe",
      env: {
        NEXT_PUBLIC_API_URL: API_URL,
        NEXT_PUBLIC_SITE_URL: WEB_URL,
      },
    },
  ],
});
