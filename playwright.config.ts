import { defineConfig, devices } from "@playwright/test";

const port = 8765;
const databasePath = `/tmp/coursepilot-playwright-${process.pid}.sqlite3`;

export default defineConfig({
  testDir: "frontend/e2e",
  fullyParallel: false,
  workers: 1,
  timeout: 30_000,
  expect: { timeout: 5_000 },
  reporter: [["list"]],
  use: {
    ...devices["Desktop Chrome"],
    baseURL: `http://127.0.0.1:${port}`,
    channel: "chrome",
    screenshot: "only-on-failure",
    trace: "retain-on-failure",
  },
  webServer: {
    command: `.venv/bin/python -m uvicorn app.main:app --host 127.0.0.1 --port ${port} --log-level warning`,
    url: `http://127.0.0.1:${port}/health`,
    reuseExistingServer: false,
    timeout: 30_000,
    env: {
      COURSEPILOT_API_KEY: "playwright-test-key-0123456789abcdef",
      COURSEPILOT_DB_PATH: databasePath,
      COURSEPILOT_TEST_MODE: "true",
    },
  },
});
