import { defineConfig } from '@playwright/test';

if (!process.env.KOTOBA_E2E_DATABASE_URL)
  throw Error('Set KOTOBA_E2E_DATABASE_URL to a disposable PostgreSQL database.');

export default defineConfig({
  testDir: './tests/e2e',
  workers: 1,
  fullyParallel: false,
  timeout: 30000,
  use: { baseURL: 'http://127.0.0.1:8010', headless: true, trace: 'retain-on-failure' },
  webServer: {
    command: process.env.KOTOBA_E2E_COMMAND || 'uv run python -m scripts.e2e_server',
    url: 'http://127.0.0.1:8010/api/test-environment',
    reuseExistingServer: false,
    timeout: 60000,
  },
});
