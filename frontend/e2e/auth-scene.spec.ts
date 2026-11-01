// Copyright 2026 Firefly Software Foundation
// SPDX-License-Identifier: Apache-2.0
import { test, expect, type Page } from '@playwright/test';
import { mkdir } from 'node:fs/promises';
import { mockService } from './fixtures';
const output = process.env['KOINON_AUTH_SCREENSHOTS'];
async function capture(page: Page, name: string) {
  if (output) {
    await mkdir(output, { recursive: true });
    await page.screenshot({ path: `${output}/${name}.png`, fullPage: true, animations: 'disabled' });
  }
}
for (const width of [1440, 3840, 390])
  for (const custom of [false, true])
    for (const dark of [false, true])
      test(`auth library ${custom ? 'custom' : 'native'} ${dark ? 'dark' : 'light'} ${width}px`, async ({
        page,
      }) => {
        await page.setViewportSize({ width, height: width === 3840 ? 1440 : 960 });
        await page.addInitScript(
          (value) => localStorage.setItem('koinon-theme', value),
          dark ? 'dark' : 'light',
        );
        await mockService(page, { authenticated: false });
        if (custom) {
          const logos = await page.evaluate(() => {
            const canvas = document.createElement('canvas');
            canvas.width = 220;
            canvas.height = 44;
            const ctx = canvas.getContext('2d')!;
            const result: string[] = [];
            for (const color of ['#272820', '#f3f1eb']) {
              ctx.clearRect(0, 0, 220, 44);
              ctx.fillStyle = color;
              ctx.font = '600 30px sans-serif';
              ctx.fillText('Northstar', 0, 32);
              result.push(canvas.toDataURL('image/png'));
            }
            return result;
          });
          await page.route('**/bff/api/v1/branding/defaults', (route) =>
            route.fulfill({
              json: {
                product_name: 'Northstar',
                assistant_name: 'Northstar',
                logo_light: logos[0],
                logo_dark: logos[1],
              },
            }),
          );
        }
        await page.goto('/library');
        const scene = page.locator('.auth-scene'),
          panel = page.locator('.login-panel');
        await expect(scene).toBeVisible();
        await expect
          .poll(() => scene.evaluate((img: HTMLImageElement) => img.naturalWidth))
          .toBeGreaterThan(0);
        await expect(scene).toHaveAttribute('alt', '');
        await expect(scene).toHaveAttribute('aria-hidden', 'true');
        const art = (await scene.boundingBox())!,
          text = (await page.locator('.welcome-copy p').boundingBox())!,
          card = (await panel.boundingBox())!;
        expect(art.y).toBeGreaterThanOrEqual(text.y + text.height - 1);
        if (width > 700) expect(art.x + art.width).toBeLessThanOrEqual(card.x);
        const button = (await panel
          .getByRole('button', { name: 'Sign in', exact: true })
          .boundingBox())!;
        expect(button.y + button.height).toBeLessThanOrEqual(page.viewportSize()!.height);
        await expect(page.locator('ffk-sign-in header ffk-powered-by')).toHaveCount(0);
        await expect(page.locator('ffk-sign-in footer ffk-powered-by')).toHaveCount(custom ? 1 : 0);
        await expect(panel.locator('img')).toHaveCount(0);
        expect(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth)).toBe(
          true,
        );
        await capture(
          page,
          `auth-library-${custom ? 'custom' : 'native'}-${dark ? 'dark' : 'light'}-${width}`,
        );
      });
test('logout confirmation stays compact and failed sign-out preserves the authenticated view', async ({
  page,
}) => {
  await page.setViewportSize({ width: 390, height: 960 });
  await mockService(page);
  await page.route('**/logout', (route) => route.fulfill({ status: 503, json: {} }));
  await page.route('**/auth/me', (route) => route.fulfill({ json: { authenticated: true } }));
  await page.goto('/library');
  await page.getByRole('button', { name: 'Account menu', exact: true }).click();
  await page.getByRole('menuitem', { name: 'Sign out', exact: true }).click();
  const modal = page.getByRole('dialog', { name: 'Sign out?', exact: true });
  await expect(modal).toBeVisible();
  const box = (await modal.boundingBox())!;
  expect(box.width).toBeLessThanOrEqual(358);
  expect(box.height).toBeLessThan(360);
  await expect(modal.locator('.auth-scene')).toHaveCount(0);
  await capture(page, 'auth-library-signout-confirmation');
  await modal.getByRole('button', { name: 'Sign out', exact: true }).click();
  await expect(
    page.getByRole('alert').filter({ hasText: 'You are still signed in.' }),
  ).toBeVisible();
  await expect(page.locator('.auth-scene')).toHaveCount(0);
  await expect(page.getByRole('button', { name: 'Account menu', exact: true })).toBeVisible();
  await capture(page, 'auth-library-signout-error');
});
test('unavailable decorative artwork never blocks SSO', async ({ page }) => {
  await mockService(page, { authenticated: false });
  await page.route('**/illustrations/knowledge-library*.webp', (route) => route.abort());
  await page.goto('/library');
  await expect(page.locator('.welcome-copy')).toHaveClass(/scene-unavailable/);
  await expect(page.locator('.auth-scene')).toHaveCount(0);
  await page.route('**/oauth2/authorization/koinon', (route) =>
    route.fulfill({ contentType: 'text/html', body: '<h1>Organization sign-in</h1>' }),
  );
  await page.getByRole('button', { name: 'Sign in', exact: true }).click();
  await expect(
    page.getByRole('heading', { name: 'Organization sign-in', exact: true }),
  ).toBeVisible();
});
