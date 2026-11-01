// Copyright 2026 Firefly Software Foundation
// SPDX-License-Identifier: Apache-2.0
import { test, expect } from '@playwright/test';
import { mkdir } from 'node:fs/promises';
import { context, mockService } from './fixtures';

for (const width of [1440, 390]) {
  test(`authoritative session warning renews without replaying an interrupted Library draft at ${width}px`, async ({
    page,
  }) => {
    await page.setViewportSize({ width, height: width === 390 ? 844 : 1000 });
    const fixture = await mockService(page);
    let phase: 'original' | 'expired' | 'started' | 'confirmed' = 'original';
    let posts = 0;
    const oldLogin = '2026-11-01T09:00:00Z',
      newLogin = '2026-11-01T10:00:00Z';
    await page.route('**/auth/me', (route) =>
      route.fulfill({
        status: phase === 'expired' ? 401 : 200,
        contentType: 'application/json',
        body: JSON.stringify({
          subject: context.subject,
          authenticated: true,
          authentication_method: 'oidc-session',
          server_time: new Date().toISOString(),
          expires_at: new Date(Date.now() + (phase === 'original' ? 65000 : 1800000)).toISOString(),
          authenticated_at: phase === 'confirmed' ? newLogin : oldLogin,
        }),
      }),
    );
    await page.route('**/bff/api/v1/tenants/tenant-one/catalog', (route) => {
      if (route.request().method() !== 'POST') return route.fallback();
      posts++;
      phase = 'expired';
      return route.fulfill({
        status: 401,
        contentType: 'application/problem+json',
        body: JSON.stringify({ detail: 'Session expired before creation' }),
      });
    });
    await page.context().route('**/oauth2/authorization/koinon', (route) => {
      phase = 'started';
      return route.fulfill({
        contentType: 'text/html',
        body: '<!doctype html><title>Controlled sign-in fixture</title><button>Complete controlled sign-in</button>',
      });
    });
    await page.goto('/library');
    const renew = page.getByRole('button', { name: 'Renew session', exact: true });
    await expect(renew).toBeVisible();
    await expect(page.getByRole('timer')).toBeVisible();
    await page.getByRole('button', { name: 'Create a space', exact: true }).click();
    await page.getByRole('textbox', { name: 'Name', exact: true }).fill('Retained private draft');
    await page
      .getByRole('textbox', { name: 'Description', exact: true })
      .fill('Controlled draft text. No real organization data.');
    await expect(
      page.getByRole('dialog').getByRole('button', { name: 'Renew session', exact: true }),
    ).toBeVisible();
    const output = process.env['KOINON_SESSION_SCREENSHOTS'];
    if (output) {
      await mkdir(output, { recursive: true });
      await expect(page.getByRole('dialog')).toHaveCSS('opacity', '1');
      await page.screenshot({
        path: `${output}/session-warning-${width}.png`,
        fullPage: true,
        animations: 'disabled',
      });
    }
    await page.getByRole('button', { name: 'Create space', exact: true }).click();
    await expect(page.locator('.auth-scene')).toBeVisible();
    await expect(page.getByRole('textbox', { name: 'Name', exact: true })).toHaveCount(0);
    const popupPromise = page.waitForEvent('popup');
    await renew.click();
    const popup = await popupPromise;
    await expect(popup.getByRole('button', { name: 'Complete controlled sign-in' })).toBeVisible();
    expect(await popup.evaluate(() => window.opener === null)).toBe(true);
    await expect(
      page.getByRole('button', { name: 'Waiting for sign-in', exact: true }),
    ).toBeVisible();
    await expect.poll(() => phase).toBe('started');
    await expect(page.locator('.auth-scene')).toBeVisible();
    expect(posts).toBe(1);
    await popup.getByRole('button', { name: 'Complete controlled sign-in' }).click();
    phase = 'confirmed';
    await expect(page.getByRole('textbox', { name: 'Name', exact: true })).toHaveValue(
      'Retained private draft',
    );
    await expect(page.getByRole('textbox', { name: 'Description', exact: true })).toHaveValue(
      'Controlled draft text. No real organization data.',
    );
    await expect(
      page.getByText(
        'Session renewed. Review your Library draft and any earlier request before saving.',
        { exact: true },
      ),
    ).toBeVisible();
    expect(posts).toBe(1);
    expect(fixture.writes).toHaveLength(0);
    if (output)
      await page.screenshot({ path: `${output}/session-restored-${width}.png`, fullPage: true });
    await popup.close();
  });
}

test('an old backend without an authoritative deadline shows no invented countdown', async ({
  page,
}) => {
  await mockService(page);
  await page.goto('/library');
  await expect(page.getByRole('heading', { name: 'Library', exact: true })).toBeVisible();
  await expect(page.getByRole('timer')).toHaveCount(0);
  await expect(page.getByRole('button', { name: 'Renew session', exact: true })).toHaveCount(0);
});
