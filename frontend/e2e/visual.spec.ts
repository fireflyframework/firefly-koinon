// Copyright 2026 Firefly Software Foundation SPDX-License-Identifier: Apache-2.0
import { expect, test, type Page } from '@playwright/test';
import { mkdir } from 'node:fs/promises';
import { resolve } from 'node:path';
import { mockService, entry } from './fixtures';
const directory = resolve('../../control/frontend-captures/atomic-stage2');
async function label(page: Page) {
  await page.evaluate(() => {
    document
      .querySelector<HTMLElement>('ffk-workbench')
      ?.style.setProperty('--koinon-workspace-height', 'calc(100dvh - 22px)');
    const mark = document.createElement('div');
    mark.textContent = 'Interface preview using controlled service data.';
    mark.style.cssText =
      'position:fixed;bottom:0;left:0;right:0;z-index:9999;padding:5px 12px;background:#855414;color:white;font:10px system-ui;pointer-events:none;text-align:center';
    document.body.append(mark);
  });
}
async function folder(page: Page) {
  for (const name of ['Research operations', 'Operations intelligence', 'Reference library'])
    await page.getByRole('button', { name, exact: true }).click();
}
async function capture(page: Page, name: string) {
  await label(page);
  expect(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth)).toBe(true);
  await page.screenshot({
    path: resolve(directory, name + '.png'),
    fullPage: true,
    animations: 'disabled',
  });
}
test.beforeAll(async () => {
  await mkdir(directory, { recursive: true });
});
for (const width of [1440, 1024, 390])
  for (const theme of ['light', 'dark'])
    test(`controlled Library ${width} ${theme}`, async ({ page }) => {
      await page.setViewportSize({ width, height: 960 });
      await page.addInitScript((theme) => localStorage.setItem('koinon-theme', theme), theme);
      await mockService(page);
      await page.goto('/library');
      await folder(page);
      await expect(
        page.getByRole('heading', { name: 'Reference library', exact: true }),
      ).toBeVisible();
      await capture(page, `library-${width}-${theme}`);
      await page.getByRole('button', { name: 'Quarterly service activity', exact: true }).click();
      await expect(page.getByLabel('Resource details', { exact: true })).toBeVisible();
      await capture(page, `inspector-${width}-${theme}`);
    });
test('dialog focus and Escape restore the invoking action inside the shadow root', async ({
  page,
}) => {
  await mockService(page);
  await page.goto('/library');
  const open = page.getByRole('button', { name: 'Add knowledge', exact: true });
  await open.click();
  await expect(page.getByRole('dialog')).toBeVisible();
  await expect(page.locator('body > .cdk-overlay-container')).toHaveCount(0);
  await page.keyboard.press('Escape');
  await expect(page.getByRole('dialog')).toHaveCount(0);
  await expect(open).toBeFocused();
});
test('720px reflow, long names, folder drawer and reduced motion', async ({ page }) => {
  await page.setViewportSize({ width: 720, height: 960 });
  await page.emulateMedia({ reducedMotion: 'reduce' });
  const service = await mockService(page);
  for (let i = 0; i < 42; i++)
    service.rows.push(
      entry(
        'long-' + i,
        'document',
        i === 0 ? 'unbroken'.repeat(30) + '.pdf' : 'Additional evidence ' + i + '.pdf',
        'source-one',
      ),
    );
  await page.goto('/library');
  await folder(page);
  await capture(page, 'library-720-long-rows');
  await page.getByRole('button', { name: 'Browse folders', exact: true }).click();
  await expect(page.getByRole('tree')).toBeVisible();
  await capture(page, 'tree-720');
  expect(
    await page.locator('.beating-heart').evaluate((el) => getComputedStyle(el).animationName),
  ).toBe('none');
});
test('controlled query evidence and upload preview', async ({ page }) => {
  await page.setViewportSize({ width: 1440, height: 1000 });
  await mockService(page);
  await page.goto('/library');
  await folder(page);
  await page.getByRole('button', { name: 'Add knowledge', exact: true }).click();
  await page
    .getByRole('dialog')
    .getByRole('button', { name: /Upload files/ })
    .click();
  await page
    .getByLabel('Choose files')
    .setInputFiles({
      name: 'quarterly-service-activity.csv',
      mimeType: 'text/csv',
      buffer: Buffer.from('region,count\nNorth,18\n'),
    });
  await capture(page, 'upload-preview-1440');
  await page.keyboard.press('Escape');
  await page.getByRole('button', { name: 'Quarterly service activity', exact: true }).click();
  await page.getByRole('button', { name: 'Explore dataset', exact: true }).click();
  await page
    .getByRole('textbox', { name: 'What would you like to understand?' })
    .fill('Count activity by region');
  await page.getByRole('button', { name: 'Run query', exact: true }).click();
  await expect(page.getByRole('cell', { name: 'North', exact: true })).toBeVisible();
  await capture(page, 'query-1440');
});
for (const width of [1440, 390])
  test(`branded native-login screen ${width}`, async ({ page }) => {
    await page.setViewportSize({ width, height: 960 });
    await mockService(page, { authenticated: false });
    await page.goto('/library');
    await expect(page.getByRole('button', { name: 'Sign in', exact: true })).toBeVisible();
    await capture(page, `login-${width}`);
  });
