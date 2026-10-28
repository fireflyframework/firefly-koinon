// Copyright 2026 Firefly Software Foundation SPDX-License-Identifier: Apache-2.0
// Controlled design fixtures only; these captures do not qualify live-provider behavior.
import { test, expect } from '@playwright/test';
import { setDarkAppearance } from './fixtures';
import { mkdir } from 'node:fs/promises';
import { resolve } from 'node:path';
const capture = resolve('../../control/frontend-captures/atomic-stage1');
test.beforeAll(async () => {
  await mkdir(capture, { recursive: true });
});
async function noOverflow(page: import('@playwright/test').Page) {
  expect(await page.evaluate(() => document.documentElement.scrollWidth <= window.innerWidth)).toBe(
    true,
  );
}
for (const width of [1440, 720, 390]) {
  test(`Library template ${width} with actual atomic components`, async ({ page }) => {
    await page.setViewportSize({ width, height: 960 });
    await page.goto('/design/');
    await expect(page.getByRole('heading', { name: 'Policies & playbooks' })).toBeVisible();
    await expect(page.getByText('Controlled design fixtures')).toBeVisible();
    if (width === 390) await setDarkAppearance(page);
    await noOverflow(page);
    await page.screenshot({
      path: resolve(capture, `library-${width}-${width === 390 ? 'dark' : 'light'}.png`),
      fullPage: true,
    });
    if (width === 1440) {
      await page.getByRole('button', { name: 'Grid', exact: true }).click();
      await page.screenshot({ path: resolve(capture, 'library-1440-grid.png'), fullPage: true });
    }
  });
}
for (const width of [1440, 720, 390]) {
  test(`Component catalog all states ${width}`, async ({ page }) => {
    await page.setViewportSize({ width, height: 960 });
    await page.goto('/design/');
    if (width === 390) await setDarkAppearance(page);
    await page.getByRole('button', { name: 'Component catalog', exact: true }).click();
    await expect(page.getByRole('heading', { name: 'Every part has a purpose.' })).toBeVisible();
    await expect(page.getByRole('button', { name: 'Unavailable', exact: true })).toBeDisabled();
    await expect(page.getByRole('textbox', { name: 'Name', exact: true })).toHaveAttribute(
      'aria-invalid',
      'true',
    );
    await noOverflow(page);
    await page.screenshot({
      path: resolve(capture, `components-${width}-${width === 390 ? 'dark' : 'light'}.png`),
      fullPage: true,
    });
  });
}
test('Mobile navigation traps focus and closes with Escape', async ({ page }) => {
  await page.setViewportSize({ width: 390, height: 844 });
  await page.goto('/design/');
  const menu = page.getByRole('button', { name: 'Open navigation' });
  await menu.click();
  await expect(page.getByRole('dialog', { name: 'Navigation' })).toBeVisible();
  await page.keyboard.press('Tab');
  await page.keyboard.press('Escape');
  await expect(menu).toHaveAttribute('aria-expanded', 'false');
  await expect(menu).toBeFocused();
});
