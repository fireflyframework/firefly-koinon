// Copyright 2026 Firefly Software Foundation
// SPDX-License-Identifier: Apache-2.0
import { test, expect } from '@playwright/test';
import { mockService } from './fixtures';
test('session expiry destroys private account page before showing sign-in', async ({ page }) => {
  await mockService(page);
  await page.route('**/bff/api/v1/profile', (route) =>
    route.request().method() === 'PATCH'
      ? route.fulfill({
          status: 401,
          contentType: 'application/problem+json',
          body: JSON.stringify({ detail: 'Your session has expired' }),
        })
      : route.fulfill({
          contentType: 'application/json',
          body: JSON.stringify({
            subject: 'synthetic.reviewer',
            display_name: 'Alex Rivera',
            locale: 'en-US',
            time_zone: 'UTC',
            response_language: 'en',
            avatar_version: null,
          }),
        }),
  );
  await page.goto('/');
  await page.getByRole('button', { name: 'Account menu', exact: true }).click();
  await page.getByRole('menuitem', { name: 'Your account', exact: true }).click();
  await page.getByRole('textbox', { name: 'Display name', exact: true }).fill('Updated reviewer');
  await page.getByRole('button', { name: 'Save preferences', exact: true }).click();
  await expect(page.getByRole('heading', { name: 'Welcome to koinon', exact: true })).toBeVisible();
  await expect(page.getByRole('dialog')).toHaveCount(0);
  await expect(page.getByRole('textbox', { name: 'Display name', exact: true })).toHaveCount(0);
});
