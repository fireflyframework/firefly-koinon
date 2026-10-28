// Copyright 2026 Firefly Software Foundation SPDX-License-Identifier: Apache-2.0
import { mkdir } from 'node:fs/promises';
import { resolve } from 'node:path';
import { test, expect } from '@playwright/test';
import { mockService } from './fixtures';
test('profile preferences switch the actual shell language after persistence and survive reload', async ({
  page,
}) => {
  await mockService(page);
  let profile = {
    subject: 'synthetic.reviewer',
    display_name: 'Alex Rivera',
    locale: 'en-US',
    time_zone: 'UTC',
    response_language: 'en',
    avatar_url: null,
    avatar_version: null,
  };
  const writes: unknown[] = [];
  await page.route('**/bff/api/v1/profile', async (route) => {
    if (route.request().method() === 'PATCH') {
      writes.push(route.request().postDataJSON());
      profile = { ...profile, ...route.request().postDataJSON() };
      expect(route.request().headers()['x-xsrf-token']).toBe('synthetic-csrf+token');
    }
    return route.fulfill({ contentType: 'application/json', body: JSON.stringify(profile) });
  });
  await page.goto('/');
  await page.getByRole('button', { name: 'Account menu', exact: true }).click();
  await page.getByRole('menuitem', { name: 'Profile & preferences', exact: true }).click();
  await page
    .getByRole('combobox', { name: 'Interface language', exact: true })
    .selectOption('es-ES');
  await expect(page.getByRole('button', { name: 'Library', exact: true }).first()).toBeVisible();
  await page
    .getByRole('combobox', { name: 'Time zone', exact: true })
    .selectOption('Europe/Madrid');
  await page.getByRole('button', { name: 'Save preferences', exact: true }).click();
  await expect(page.getByText('Perfil guardado.', { exact: true })).toBeVisible();
  await expect(page.getByRole('button', { name: 'Biblioteca', exact: true }).first()).toBeVisible();
  expect(writes).toEqual([
    {
      display_name: 'Alex Rivera',
      locale: 'es-ES',
      time_zone: 'Europe/Madrid',
      response_language: 'en',
    },
  ]);
  await page.reload();
  await expect(page.getByRole('button', { name: 'Biblioteca', exact: true }).first()).toBeVisible();
  await page.getByRole('button', { name: 'Menú de cuenta', exact: true }).click();
  await page.getByRole('menuitem', { name: 'Perfil y preferencias', exact: true }).click();
  await expect(
    page.getByRole('combobox', { name: 'Idioma de la interfaz', exact: true }),
  ).toHaveValue('es-ES');
});
test('personal token secret is shown once and revoke uses the SDK with CSRF', async ({ page }) => {
  await mockService(page);
  const tokens: Record<string, unknown>[] = [],
    writes: { method: string; path: string; body: unknown }[] = [];
  await page.route('**/bff/api/v1/tokens**', async (route) => {
    const request = route.request(),
      path = new URL(request.url()).pathname,
      json = (body: unknown, status = 200) =>
        route.fulfill({ status, contentType: 'application/json', body: JSON.stringify(body) });
    if (path.endsWith('/scopes'))
      return json({
        items: [
          { id: 'catalog:read', name: 'Read library', dependencies: [] },
          { id: 'knowledge:search', name: 'Search knowledge', dependencies: ['catalog:read'] },
        ],
        max_lifetime_days: 90,
        max_active_per_user: 10,
      });
    if (request.method() !== 'GET') {
      expect(request.headers()['x-xsrf-token']).toBe('synthetic-csrf+token');
      writes.push({
        method: request.method(),
        path,
        body: request.postData() ? request.postDataJSON() : null,
      });
    }
    if (request.method() === 'POST') {
      const token = {
        ...request.postDataJSON(),
        id: 'token-one',
        prefix: 'ffk_test',
        revoked_at: null,
        last_used_at: null,
        created_at: '2026-10-26T00:00:00Z',
      };
      tokens.push(token);
      return json({ ...token, token: 'synthetic-one-time-secret' }, 201);
    }
    if (request.method() === 'DELETE') {
      tokens.splice(0);
      return route.fulfill({ status: 204 });
    }
    return json({
      items: tokens,
      total: tokens.length,
      page: 1,
      page_size: 25,
      pages: tokens.length ? 1 : 0,
    });
  });
  await page.goto('/');
  await page.getByRole('button', { name: 'Account menu', exact: true }).click();
  await page.getByRole('menuitem', { name: 'API tokens', exact: true }).click();
  await page.getByRole('button', { name: 'Create a token', exact: true }).click();
  await page.getByRole('textbox', { name: 'Token name', exact: true }).fill('Local integration');
  await page.getByRole('checkbox', { name: 'Search knowledge', exact: true }).check();
  await expect(page.getByRole('checkbox', { name: 'Read library', exact: true })).toBeChecked();
  await page.getByRole('button', { name: 'Create a token', exact: true }).click();
  await expect(page.getByRole('textbox', { name: 'New API token', exact: true })).toHaveValue(
    'synthetic-one-time-secret',
  );
  await page.getByRole('button', { name: 'Done', exact: true }).click();
  await expect(page.getByRole('textbox', { name: 'New API token', exact: true })).toHaveCount(0);
  await page.getByRole('button', { name: 'Revoke', exact: true }).click();
  await page.getByRole('button', { name: 'Revoke', exact: true }).click();
  await expect(page.getByText('Token revoked.', { exact: true })).toBeVisible();
  expect(writes.map((write) => write.method)).toEqual(['POST', 'DELETE']);
  expect(
    await page.evaluate(() => JSON.stringify(localStorage) + JSON.stringify(sessionStorage)),
  ).not.toContain('synthetic-one-time-secret');
});

for (const width of [1440, 390])
  test(`profile review and focus restoration ${width}`, async ({ page }) => {
    await page.setViewportSize({ width, height: 1000 });
    await mockService(page);
    await page.goto('/');
    await page.getByRole('button', { name: 'Account menu', exact: true }).click();
    await page.getByRole('menuitem', { name: 'Profile & preferences', exact: true }).click();
    await expect(page.getByRole('textbox', { name: 'Display name', exact: true })).toHaveValue(
      'Alex Rivera',
    );
    await page.evaluate(() => {
      document
        .querySelector<HTMLElement>('ffk-workbench')
        ?.style.setProperty('--koinon-workspace-height', 'calc(100dvh - 22px)');
      const mark = document.createElement('div');
      mark.textContent = 'Controlled service fixtures · Frontend review only';
      mark.style.cssText =
        'position:fixed;bottom:0;left:0;right:0;z-index:9999;padding:5px 12px;background:#855414;color:white;font:10px system-ui;pointer-events:none;text-align:center';
      document.body.append(mark);
    });
    const dir = resolve('../../control/frontend-captures/atomic-stage3');
    await mkdir(dir, { recursive: true });
    await page.screenshot({
      path: resolve(dir, `profile-${width}.png`),
      fullPage: true,
      animations: 'disabled',
    });
    await page.keyboard.press('Escape');
    await expect(page.getByRole('dialog')).toHaveCount(0);
    await expect(page.getByRole('button', { name: 'Account menu', exact: true })).toBeFocused();
  });
