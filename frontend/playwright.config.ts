// Copyright 2026 Firefly Software Foundation SPDX-License-Identifier: Apache-2.0
import { defineConfig, devices } from '@playwright/test';
export default defineConfig({
  testDir: './e2e',
  fullyParallel: false,
  workers: 1,
  timeout: 30000,
  expect: { timeout: 7000 },
  use: {
    baseURL: process.env['KOINON_E2E_BASE_URL'] || 'http://127.0.0.1:18782',
    trace: 'retain-on-failure',
    screenshot: 'only-on-failure',
  },
  webServer: process.env['KOINON_E2E_BASE_URL'] ? undefined : {
    command: 'node scripts/preview.mjs',
    url: 'http://127.0.0.1:18782',
    reuseExistingServer: !process.env['CI'],
  },
  projects: [{ name: 'chromium', use: { ...devices['Desktop Chrome'] } }],
  reporter: [['list'], ['html', { open: 'never' }]],
});
