// Copyright 2026 Firefly Software Foundation
// SPDX-License-Identifier: Apache-2.0
import { expect, test } from '@playwright/test';
import { mockService } from './fixtures';
import { mkdir } from 'node:fs/promises';
import { resolve } from 'node:path';

test('Library boot keeps source coordinates and OpenUI outside the initial JavaScript', async ({
  page,
}) => {
  const loaded: string[] = [];
  page.on('response', (response) => {
    if (response.request().resourceType() === 'script') loaded.push(response.url());
  });
  await mockService(page);
  await page.goto('/');
  await expect(page.getByRole('heading', { name: 'Library', exact: true })).toBeVisible();
  const scripts = await Promise.all(
    loaded.map(async (url) => (await page.request.get(url)).text()),
  );
  expect(scripts.join('\n')).not.toContain('ffk-table-coordinates');
  expect(scripts.join('\n')).not.toContain('ffk-openui-answer');
  expect(scripts.join('\n')).not.toContain('.drop-zone');
  expect(scripts.join('\n')).not.toContain('.cdk-overlay-container');
});

test('opening a new chat waits for an answer before downloading OpenUI', async ({ page }) => {
  const loaded: string[] = [];
  page.on('response', (response) => {
    if (response.request().resourceType() === 'script') loaded.push(response.url());
  });
  await mockService(page);
  await page.goto('/');
  await page.getByRole('button', { name: 'Chat', exact: true }).click();
  await expect(page.getByRole('heading', { name: 'Chat', exact: true })).toBeAttached();
  const scripts = await Promise.all(
    loaded.map(async (url) => (await page.request.get(url)).text()),
  );
  expect(scripts.join('\n')).not.toContain('ffk-openui-answer');
});

test('Escape cancels a dialog while its scoped overlay is still downloading', async ({ page }) => {
  await mockService(page);
  await page.goto('/');
  await expect(page.getByRole('heading', { name: 'Library', exact: true })).toBeVisible();
  let release!: () => void, observed!: () => void;
  const gate = new Promise<void>((resolve) => {
    release = resolve;
  });
  const held = new Promise<void>((resolve) => {
    observed = resolve;
  });
  await page.route('**/*.js', async (route) => {
    const response = await route.fetch();
    if ((await response.text()).includes('.cdk-overlay-container')) {
      observed();
      await gate;
    }
    await route.fulfill({ response });
  });
  const add = page.getByRole('button', { name: 'Add knowledge', exact: true });
  await add.click();
  await held;
  await page.keyboard.press('Escape');
  release();
  await page.waitForLoadState('networkidle');
  await expect(add).toBeFocused();
  await expect(page.getByRole('dialog')).toHaveCount(0);
  await add.click();
  await expect(page.getByRole('dialog')).toBeVisible();
  await page.keyboard.press('Escape');
  await expect(add).toBeFocused();
});

for (const width of [1440, 390])
  test(`failed dialog body keeps a styled keyboard modal at ${width}px`, async ({ page }) => {
    await page.setViewportSize({ width, height: 900 });
    await mockService(page);
    await page.goto('/');
    await expect(page.getByRole('heading', { name: 'Library', exact: true })).toBeVisible();
    let aborted = false;
    await page.route('**/*.js', async (route) => {
      const response = await route.fetch();
      if ((await response.text()).includes('.drop-zone')) {
        aborted = true;
        await route.abort();
      } else await route.fulfill({ response });
    });
    const add = page.getByRole('button', { name: 'Add knowledge', exact: true });
    await add.click();
    const dialog = page.getByRole('dialog', { name: 'Panel unavailable', exact: true });
    await expect(dialog).toBeVisible();
    expect(aborted).toBe(true);
    await expect(dialog).toHaveAttribute('aria-modal', 'true');
    const close = dialog.getByRole('button', { name: 'Close', exact: true });
    await expect(close).toBeFocused();
    await page.keyboard.press('Tab');
    await expect(close).toBeFocused();
    await page.keyboard.press('Shift+Tab');
    await expect(close).toBeFocused();
    const frame = await dialog.boundingBox();
    expect(frame!.width).toBeGreaterThanOrEqual(300);
    expect(frame!.x).toBeGreaterThanOrEqual(0);
    expect(frame!.x + frame!.width).toBeLessThanOrEqual(width);
    expect(await dialog.evaluate((node) => getComputedStyle(node).backgroundColor)).not.toBe(
      'rgba(0, 0, 0, 0)',
    );
    const directory = resolve('../../control/frontend-captures/bundle-v19');
    await mkdir(directory, { recursive: true });
    await page.screenshot({
      path: resolve(directory, `dialog-body-load-error-${width}.png`),
      fullPage: true,
    });
    await page.keyboard.press('Escape');
    await expect(dialog).toHaveCount(0);
    await expect(add).toBeFocused();
  });
