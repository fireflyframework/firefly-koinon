// Copyright 2026 Firefly Software Foundation
// SPDX-License-Identifier: Apache-2.0
import { test, expect } from '@playwright/test';
import { context, mockService } from './fixtures';
import { mkdir } from 'node:fs/promises';
const output = process.env['KOINON_BRAND_SCREENSHOTS'];
for (const custom of [false, true])
  for (const width of [1440, 390]) {
    test(`${custom ? 'custom' : 'native'} identity stays aligned and attributed at ${width}px`, async ({
      page,
    }) => {
      await page.setViewportSize({ width, height: 960 });
      await mockService(page);
      await page.route('**/bff/api/v1/context', (route) =>
        route.fulfill({ json: { ...context, tenants: [context.tenants[0]] } }),
      );
      await page.route('**/chat/{threads,folders}*', (route) =>
        route.fulfill({ json: { items: [], page: 1, page_size: 25, total: 0, pages: 0 } }),
      );
      const logo = await page.evaluate(() => {
        const canvas = document.createElement('canvas');
        canvas.width = 200;
        canvas.height = 40;
        const ctx = canvas.getContext('2d')!;
        ctx.fillStyle = '#272820';
        ctx.font = '600 28px sans-serif';
        ctx.fillText('Northstar', 0, 30);
        return canvas.toDataURL('image/png');
      });
      const branding = custom
        ? { product_name: 'Northstar', assistant_name: 'Northstar', logo_light: logo }
        : { product_name: 'koinon', assistant_name: 'koinon' };
      await page.route('**/bff/api/v1/branding/defaults', (route) =>
        route.fulfill({ json: branding }),
      );
      await page.route('**/bff/api/v1/tenants/*/branding', (route) =>
        route.fulfill({
          json: { tenant_id: 'tenant-one', schema_version: 1, revision: 0, branding },
        }),
      );
      await page.goto('/chat');
      await expect(page.getByRole('combobox', { name: 'Organization', exact: true })).toHaveCount(0);
      const header = page.locator('ffk-shell .topbar'),
        brand = header.locator('.brand');
      await expect(brand).toHaveAccessibleName(`${branding.product_name}, Chat`);
      await expect(page.locator('ffk-shell footer ffk-powered-by')).toHaveCount(custom ? 1 : 0);
      if (custom) {
        const image = page.locator('ffk-shell footer ffk-powered-by img');
        await expect(image).toHaveAttribute('alt', 'koinon');
        await expect
          .poll(() => image.evaluate((img: HTMLImageElement) => img.naturalWidth))
          .toBeGreaterThan(0);
      }
      if (width === 1440) {
        const section = page.locator('ffk-conversation-sidebar .group-title h3').first();
        await expect(section).toBeVisible();
        const logo = (await brand.boundingBox())!,
          group = (await section.boundingBox())!;
        const nav = (await header
          .getByRole('navigation', { name: 'Main navigation', exact: true })
          .boundingBox())!;
        expect(Math.abs(logo.x - group.x)).toBeLessThanOrEqual(1);
        const art = (await brand.locator('img').boundingBox())!;
        expect(nav.x - art.x - art.width).toBeGreaterThanOrEqual(24);
      }
      expect(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth)).toBe(
        true,
      );
      if (output) {
        await mkdir(output, { recursive: true });
        await page.screenshot({
          path: `${output}/${custom ? 'custom' : 'native'}-chat-${width}.png`,
        });
      }
      await mockService(page, { authenticated: false });
      await page.route('**/bff/api/v1/branding/defaults', (route) =>
        route.fulfill({ json: branding }),
      );
      await page.reload();
      const login = page.locator('.sign-in');
      await expect(login.getByRole('button', { name: 'Sign in', exact: true })).toBeVisible();
      await expect(login.locator('header ffk-powered-by')).toHaveCount(0);
      await expect(login.locator('footer ffk-powered-by')).toHaveCount(custom ? 1 : 0);
      expect(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth)).toBe(
        true,
      );
      if (output)
        await page.screenshot({
          path: `${output}/${custom ? 'custom' : 'native'}-login-${width}.png`,
        });
      await login.getByRole('button', { name: 'Use dark theme', exact: true }).click();
      await expect(
        login.getByRole('button', { name: 'Use light theme', exact: true }),
      ).toBeVisible();
      if (custom)
        await expect(login.locator('footer ffk-powered-by img')).toHaveAttribute(
          'src',
          /koinon-wordmark-reversed.svg$/,
        );
      else
        await expect(login.locator('.login-brand img')).toHaveAttribute(
          'src',
          /firefly-koinon-lockup-reversed.svg$/,
        );
      if (output)
        await page.screenshot({
          path: `${output}/${custom ? 'custom' : 'native'}-login-dark-${width}.png`,
        });
    });
  }
for (const width of [1440, 390])
  test(`Library header actions share regular proportions at ${width}px`, async ({ page }) => {
    await page.setViewportSize({ width, height: 960 });
    await mockService(page);
    await page.goto('/library');
    const actions = page.locator('ffk-library-template');
    const heights = [];
    for (const name of ['Archived', 'Browse folders', 'Create a space', 'Add knowledge']) {
      const button = actions.getByRole('button', { name, exact: true });
      await expect(button).toBeVisible();
      heights.push((await button.boundingBox())!.height);
    }
    expect(Math.max(...heights) - Math.min(...heights)).toBeLessThanOrEqual(1);
    expect(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth)).toBe(
      true,
    );
    if (output) await page.screenshot({ path: `${output}/library-actions-${width}.png` });
  });

test('a failed optional sign-in chunk retains a working authentication action', async ({ page }) => {
  await mockService(page, { authenticated: false });
  await page.route('**/chunk-*.js', async route => {
    const response=await route.fetch();
    if ((await response.text()).includes('ffk-sign-in')) await route.abort();
    else await route.fulfill({response});
  });
  await page.goto('/library');
  await expect(page.getByRole('alert')).toHaveText('This panel could not be opened. Refresh this page and try again.');
  await expect(page.getByRole('button',{name:'Sign in',exact:true})).toBeEnabled();
  await page.route('**/oauth2/authorization/koinon', route => route.fulfill({contentType:'text/html',body:'<h1>Organization sign-in</h1>'}));
  await page.getByRole('button',{name:'Sign in',exact:true}).click();
  await expect(page).toHaveURL(/\/oauth2\/authorization\/koinon$/);
  await expect(page.getByRole('heading',{name:'Organization sign-in',exact:true})).toBeVisible();
});
