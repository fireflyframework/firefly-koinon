// Copyright 2026 Firefly Software Foundation
// SPDX-License-Identifier: Apache-2.0
import { expect, test } from '@playwright/test';
import { mockService } from './fixtures';
import { mkdir } from 'node:fs/promises';
import { resolve } from 'node:path';

test('Chat defers the Library body until keyboard navigation and supports direct reload', async ({ page }) => {
  const scripts: Promise<string>[] = [];
  const errors: string[] = [];
  page.on('pageerror', error => errors.push(error.message));
  page.on('console', message => { if (message.type() === 'error') errors.push(message.text()); });
  page.on('response', response => {
    if (response.request().resourceType() === 'script') scripts.push(response.text());
  });
  await mockService(page);
  await page.route('**/bff/api/v1/branding/defaults', route => route.fulfill({ json: {} }));
  await page.route('**/bff/api/v1/tenants/*/branding', route => route.fulfill({
    json: { tenant_id: 'tenant-one', schema_version: 1, revision: 0, branding: {} },
  }));
  await page.route('**/bff/api/v1/notifications/unread-count', route => route.fulfill({ json: { unread: 0 } }));
  await page.route('**/organization/people/me/presentation', route => route.fulfill({
    json: { tenant_id: 'tenant-one', subject: 'synthetic.reviewer', status: 'not_configured', display_name: 'Alex Rivera' },
  }));
  await page.route(url => /^\/bff\/api\/v1\/tenants\/[^/]+\/(?:agents|chat\/threads)$/.test(url.pathname), route => {
    if (route.request().method() !== 'GET') return route.fallback();
    return route.fulfill({ json: {
      items: [], total: 0, pages: 0, page: 1,
      page_size: Number(new URL(route.request().url()).searchParams.get('page_size') || 25),
    } });
  });
  await page.goto('/chat');
  await expect(page.getByRole('heading', { name: 'Chat', exact: true })).toBeAttached();
  expect((await Promise.all(scripts)).some(script => script.includes('.library-grid'))).toBe(false);
  const library = page.getByRole('button', { name: 'Library', exact: true });
  await library.focus();
  await page.keyboard.press('Enter');
  await expect(page.getByRole('heading', { name: 'Library', exact: true })).toBeVisible();
  expect((await Promise.all(scripts)).some(script => script.includes('.library-grid'))).toBe(true);
  await page.reload();
  await expect(page.getByRole('heading', { name: 'Library', exact: true })).toBeVisible();
  await expect(page.getByRole('button', { name: 'Research operations', exact: true })).toBeVisible();
  expect(errors).toEqual([]);
});

for (const width of [1440, 390, 320]) for (const theme of ['light', 'dark'] as const)
  test(`Library chunk states preserve Spanish navigation at ${width}px in ${theme}`, async ({ page }) => {
    const errors: string[] = [];
    page.on('pageerror', error => errors.push(error.message));
    await page.setViewportSize({ width, height: 900 });
    await page.addInitScript(theme => localStorage.setItem('koinon-theme', theme), theme);
    await mockService(page);
    await page.route('**/bff/api/v1/profile', route => route.fulfill({ json: {
      subject: 'synthetic.reviewer', display_name: 'Alex Rivera', locale: 'es-ES',
      time_zone: 'UTC', response_language: 'es', avatar_url: null, avatar_version: null,
    } }));
    let release!: () => void;
    const gate = new Promise<void>(resolve => { release = resolve; });
    await page.route('**/*.js', async route => {
      const response = await route.fetch();
      if ((await response.text()).includes('.library-grid')) {
        await gate;
        await route.abort();
      } else await route.fulfill({ response });
    });
    const capture = async (state: string) => {
      const directory = process.env['KOINON_E2E_CAPTURE_DIR'];
      if (!directory) return;
      await mkdir(directory, { recursive: true });
      await page.screenshot({ path: resolve(directory, `library-${state}-${width}-${theme}.png`), fullPage: true });
    };
    try {
      await page.goto('/library');
      await expect(page.getByRole('status', { name: 'Cargando biblioteca', exact: true })).toBeVisible();
      await capture('loading');
    } finally {
      release();
    }
    await expect(page.locator('.library-main').getByRole('alert')).toContainText('Actualiza');
    await capture('error');
    await page.unroute('**/*.js');
    await page.reload();
    await expect(page.getByRole('heading', { name: 'Biblioteca', exact: true })).toBeVisible();
    await expect(page.getByRole('button', { name: 'Research operations', exact: true })).toBeVisible();
    await page.getByRole('button', { name: 'Research operations', exact: true }).focus();
    await expect(page.getByRole('button', { name: 'Research operations', exact: true })).toBeFocused();
    await capture('ready');
    if (width === 1440) await page.evaluate(() => { document.documentElement.style.zoom = '2'; });
    expect(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth)).toBe(true);
    expect(errors).toEqual([]);
  });

test('Library boot keeps source coordinates and OpenUI outside the initial JavaScript', async ({
  page,
}) => {
  const loaded: string[] = [];
  page.on('response', (response) => {
    if (response.request().resourceType() === 'script') loaded.push(response.url());
  });
  await mockService(page);
  await page.goto('/library');
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
  await page.goto('/library');
  await page.getByRole('button', { name: 'Chat', exact: true }).click();
  await expect(page.getByRole('heading', { name: 'Chat', exact: true })).toBeAttached();
  const scripts = await Promise.all(
    loaded.map(async (url) => (await page.request.get(url)).text()),
  );
  expect(scripts.join('\n')).not.toContain('ffk-openui-answer');
});

test('Escape cancels a dialog while its scoped overlay is still downloading', async ({ page }) => {
  await mockService(page);
  await page.goto('/library');
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
    await page.goto('/library');
    await expect(page.getByRole('heading', { name: 'Library', exact: true })).toBeVisible();
    let aborted = false;
    await page.route('**/*.js', async (route) => {
      const response = await route.fetch();
      if (/selectors:\[\[[`"']ffk-workbench-dialogs[`"']\]\]/.test(await response.text())) {
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
    await add.click();
    await expect(dialog).toBeVisible();
    await close.click();
    await expect(dialog).toHaveCount(0);
    await expect(add).toBeFocused();
  });

test('a failed nested upload body preserves close and recovers after the instructed page refresh', async ({
  page,
}) => {
  await mockService(page);
  await page.goto('/library');
  await expect(page.getByRole('heading', { name: 'Library', exact: true })).toBeVisible();
  let aborted = false;
  await page.route('**/*.js', async (route) => {
    const response = await route.fetch();
    if (/selectors:\[\[[`"']ffk-library-upload-panel[`"']\]\]/.test(await response.text())) {
      aborted = true;
      await route.abort();
    } else await route.fulfill({ response });
  });
  const add = page.getByRole('button', { name: 'Add knowledge', exact: true });
  await add.click();
  await page
    .getByRole('dialog')
    .getByRole('button', { name: /Upload files/ })
    .click();
  const upload = page.getByRole('dialog', { name: 'Add files', exact: true });
  await expect(upload.getByRole('alert')).toHaveText(
    'This panel could not be opened. Refresh this page and try again.',
  );
  expect(aborted).toBe(true);
  await upload.getByRole('button', { name: 'Close dialog', exact: true }).click();
  await expect(page.getByRole('dialog')).toHaveCount(0);
  await expect(add).toBeFocused();
  await page.unroute('**/*.js');
  await page.reload();
  await add.click();
  await page
    .getByRole('dialog')
    .getByRole('button', { name: /Upload files/ })
    .click();
  await expect(upload.getByLabel('Choose files')).toBeAttached();
  await upload.getByRole('button', { name: 'Close dialog', exact: true }).click();
  await expect(page.getByRole('dialog')).toHaveCount(0);
  await expect(add).toBeFocused();
});
