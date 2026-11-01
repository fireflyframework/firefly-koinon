// Copyright 2026 Firefly Software Foundation
// SPDX-License-Identifier: Apache-2.0
import { test, expect } from '@playwright/test';
import { mockService, openAdministration } from './fixtures';
for (const width of [1440, 390]) {
  test(`provider setup exposes supported choices without framework inventory at ${width}px`, async ({
    page,
  }) => {
    await mockService(page);
    await page.route('**/bff/api/v1/**/configuration', (route) =>
      route.fulfill({
        json: {
          providers: [],
          connections: [],
          checks: [],
          provider_types: [{ id: 'openai', name: 'OpenAI compatible', fields: [] }],
          framework_providers: [
            {
              id: 'framework-only-provider',
              native_supported: true,
              exposed: false,
              reason: 'Internal framework inventory',
              model_class: 'private.module.Provider',
            },
          ],
        },
      }),
    );
    await page.setViewportSize({ width, height: 1000 });
    await page.goto('/library');
    await openAdministration(page, 'Settings');
    const settings = page.locator('ffk-settings-page');
    await expect(settings.getByRole('heading', { name: 'Providers', exact: true })).toBeVisible();
    await expect(settings.getByText('Framework provider support', { exact: true })).toHaveCount(0);
    await expect(settings.getByText('framework-only-provider', { exact: true })).toHaveCount(0);
    await expect(settings.getByText('private.module.Provider', { exact: true })).toHaveCount(0);
    await settings.getByRole('button', { name: 'Connect a model', exact: true }).click();
    await settings.getByRole('button', { name: 'OpenAI compatible', exact: true }).click();
    await expect(settings.locator('.selected-provider')).toContainText('OpenAI compatible');
    expect(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth)).toBe(
      true,
    );
  });
}
