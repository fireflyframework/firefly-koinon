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
    const session = page.getByRole('button', { name: /View session details/ });
    await expect(session).toBeVisible();
    await expect(renew).toHaveCount(0);
    const library = page.locator('.library-layout');
    const before = await library.boundingBox();
    await session.click();
    await expect(renew).toBeVisible();
    await expect(page.getByRole('timer')).toBeVisible();
    expect(await library.boundingBox()).toEqual(before);
    await page.keyboard.press('Escape');
    await expect(session).toBeFocused();
    await session.press('Enter');
    await page.getByRole('button', { name: 'Account menu', exact: true }).click();
    await expect(page.getByRole('menu')).toBeVisible();
    await expect(renew).toHaveCount(0);
    await session.focus();
    await session.press('Enter');
    await expect(page.getByRole('menu')).toHaveCount(0);
    await expect(renew).toBeVisible();
    await page.getByRole('button', { name: 'Create a space', exact: true }).click();
    await page.getByRole('textbox', { name: 'Name', exact: true }).fill('Retained private draft');
    await page
      .getByRole('textbox', { name: 'Description', exact: true })
      .fill('Controlled draft text. No real organization data.');
    await expect(
      page.getByRole('dialog').getByRole('button', { name: 'Renew session', exact: true }),
    ).toBeVisible();
    await expect(session).toHaveCount(0);
    await expect(page.getByRole('timer')).toHaveCount(0);
    const description = await page.getByRole('textbox', { name: 'Description', exact: true }).boundingBox();
    const notice = await page.getByRole('dialog').locator('.notice').boundingBox();
    expect(notice!.y).toBeGreaterThan(description!.y + description!.height);
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
    await page.getByRole('button', { name: 'Sign in', exact: true }).click();
    const popup = await popupPromise;
    await expect(popup.getByRole('button', { name: 'Complete controlled sign-in' })).toBeVisible();
    expect(await popup.evaluate(() => window.opener === null)).toBe(true);
    await expect(
      page.getByText('Waiting for sign-in', { exact: true }),
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

for (const width of [1440, 390]) for (const theme of ['light', 'dark']) for (const locale of ['en', 'es']) {
  test(`session surfaces ${width} ${theme} ${locale} preserve layout, keyboard and translated first-open auth`, async ({ page }) => {
    await page.setViewportSize({ width, height: width === 390 ? 844 : 1000 });
    await page.addInitScript(value => localStorage.setItem('koinon-theme', value), theme);
    await mockService(page);
    await page.route('**/bff/api/v1/profile', route => route.fulfill({ json: {
      subject: context.subject, display_name: 'Alex Rivera', locale: locale === 'es' ? 'es-ES' : 'en-US',
      time_zone: 'UTC', response_language: locale, avatar_url: null, avatar_version: null,
    }}));
    await page.route('**/bff/api/v1/branding/defaults', route => route.fulfill({ json: {} }));
    await page.route('**/bff/api/v1/tenants/*/branding', route => route.fulfill({ json: { tenant_id: 'tenant-one', schema_version: 1, revision: 0, branding: {} } }));
    await page.route('**/bff/api/v1/notifications/unread-count', route => route.fulfill({ json: { unread: 0 } }));
    await page.route('**/organization/people/me/presentation', route => route.fulfill({ json: { tenant_id: 'tenant-one', subject: context.subject, status: 'not_configured', display_name: 'Alex Rivera' } }));
    let deadline = 28800, expired = false;
    await page.route('**/auth/me', route => route.fulfill({ status: expired ? 401 : 200, json: {
      subject: context.subject, authenticated: true, server_time: new Date().toISOString(),
      expires_at: new Date(Date.now() + deadline * 1000).toISOString(),
      authenticated_at: '2026-11-01T09:00:00Z',
    }}));
    const errors: string[] = [];
    page.on('pageerror', error => errors.push(error.message));
    page.on('console', message => { if (message.type() === 'error') errors.push(message.text()); });
    const output = process.env['KOINON_SESSION_SCREENSHOTS'];
    const capture = async (state: string) => { if (output) {
      await mkdir(output, { recursive: true });
      await page.screenshot({ path: `${output}/session-${width}-${theme}-${locale}-${state}.png`, animations: 'disabled' });
    }};
    await page.goto('/library');
    await expect(page.getByRole('heading', { name: locale === 'es' ? 'Biblioteca' : 'Library', exact: true })).toBeVisible();
    const session = page.getByRole('button', { name: /View session details|Ver detalles de sesión/ });
    await expect(session).toHaveCount(0);
    await capture('healthy');
    deadline = 65;
    await page.evaluate(() => document.dispatchEvent(new Event('visibilitychange')));
    await expect(session).toBeVisible();
    await session.focus();
    await page.keyboard.press('Enter');
    await expect(page.getByRole('button', { name: locale === 'es' ? 'Renovar sesión' : 'Renew session', exact: true })).toBeVisible();
    const details = page.locator('#session-details');
    const box = await details.boundingBox();
    expect(box!.x).toBeGreaterThanOrEqual(0);
    expect(box!.x + box!.width).toBeLessThanOrEqual(width);
    await capture('account');
    await page.keyboard.press('Escape');
    await expect(session).toBeFocused();
    deadline = 28800;
    await page.evaluate(() => document.dispatchEvent(new Event('visibilitychange')));
    await expect(session).toHaveCount(0);
    await expect(page.getByRole('button', { name: locale === 'es' ? 'Menú de cuenta' : 'Account menu', exact: true })).toBeFocused();
    deadline = 65;
    await page.evaluate(() => document.dispatchEvent(new Event('visibilitychange')));
    await expect(session).toBeVisible();
    await page.getByRole('button', { name: locale === 'es' ? 'Crear un espacio' : 'Create a space', exact: true }).click();
    const dialog = page.getByRole('dialog');
    await expect(dialog.locator('.notice.compact')).toBeVisible();
    await expect(page.getByRole('timer')).toHaveCount(0);
    await expect(session).toHaveCount(0);
    await expect(dialog).toHaveCSS('opacity', '1');
    expect(await dialog.evaluate(element => element.scrollWidth <= element.clientWidth)).toBe(true);
    await expect(dialog.getByRole('button', { name: locale === 'es' ? 'Crear espacio' : 'Create space', exact: true })).toBeVisible();
    await capture('dialog');
    await dialog.getByRole('button', { name: locale === 'es' ? 'Renovar sesión' : 'Renew session', exact: true }).focus();
    deadline = 28800;
    await page.evaluate(() => document.dispatchEvent(new Event('visibilitychange')));
    await expect(dialog.locator('.notice')).toHaveCount(0);
    await expect(dialog.getByRole('button', { name: locale === 'es' ? 'Cancelar' : 'Cancel', exact: true })).toBeFocused();
    await page.keyboard.press('Escape');
    await expect(dialog).toHaveCount(0);
    expired = true;
    await page.evaluate(() => document.dispatchEvent(new Event('visibilitychange')));
    await expect(page.getByRole('button', { name: locale === 'es' ? 'Iniciar sesión' : 'Sign in', exact: true })).toBeVisible();
    await expect(page.getByRole('button', { name: locale === 'es' ? 'Renovar sesión' : 'Renew session', exact: true })).toHaveCount(0);
    await capture('expired');
    expect(errors.filter(error => !error.includes('401 (Unauthorized)'))).toEqual([]);
  });
}

test('Spanish first-open search and upload panels retain their deferred translations', async ({ page }) => {
  await mockService(page);
  await page.route('**/bff/api/v1/profile', route => route.fulfill({ json: {
    subject: context.subject, display_name: 'Alex Rivera', locale: 'es-ES', time_zone: 'UTC', response_language: 'es', avatar_url: null, avatar_version: null,
  }}));
  await page.goto('/library');
  await page.getByRole('button', { name: 'Búsqueda y comandos', exact: true }).click();
  const palette = page.getByRole('dialog', { name: 'Buscar y navegar', exact: true });
  await expect(palette.getByRole('combobox', { name: 'Buscar archivos o una acción' })).toBeVisible();
  await expect(palette).toContainText('Escribe un nombre para buscar en este contexto.');
  await page.keyboard.press('Escape');
  for (const name of ['Research operations', 'Operations intelligence', 'Reference library'])
    await page.getByRole('button', { name, exact: true }).click();
  await page.getByRole('button', { name: 'Añadir conocimiento', exact: true }).click();
  await page.getByRole('dialog').getByRole('button', { name: /Subir archivos/ }).click();
  await expect(page.getByRole('dialog').locator('ffk-library-upload-panel')).toBeVisible();
  await page.getByLabel('Elegir archivos').setInputFiles({ name: 'first-open.csv', mimeType: 'text/csv', buffer: Buffer.from('region,count\nNorth,18\n') });
  await expect(page.getByRole('dialog').getByRole('button', { name: 'Subir 1 archivo', exact: true })).toBeEnabled();
  await expect(page.getByRole('dialog')).not.toContainText('Choose files');
});

test('session action and dialog remain keyboard reachable at 200 percent page zoom', async ({ page }) => {
  await page.setViewportSize({ width: 1440, height: 1000 });
  await mockService(page);
  await page.route('**/auth/me', route => route.fulfill({ json: {
    subject: context.subject, authenticated: true, server_time: new Date().toISOString(),
    expires_at: new Date(Date.now() + 65000).toISOString(), authenticated_at: '2026-11-01T09:00:00Z',
  }}));
  await page.goto('/library');
  await page.evaluate(() => { document.documentElement.style.zoom = '2'; });
  const session = page.getByRole('button', { name: /View session details/ });
  await session.focus(); await page.keyboard.press('Enter');
  const renew = page.getByRole('button', { name: 'Renew session', exact: true });
  await expect(renew).toBeVisible();
  const box = await renew.boundingBox();
  expect(box!.x).toBeGreaterThanOrEqual(0); expect(box!.x + box!.width).toBeLessThanOrEqual(1440);
  await page.keyboard.press('Escape'); await expect(session).toBeFocused();
  await page.getByRole('button', { name: 'Create a space', exact: true }).click();
  await page.getByRole('textbox', { name: 'Name', exact: true }).fill('Zoomed keyboard draft');
  const dialog = page.getByRole('dialog');
  const submit = dialog.getByRole('button', { name: 'Create space', exact: true });
  await submit.focus(); await expect(submit).toBeInViewport();
  expect(await dialog.evaluate(element => element.scrollWidth <= element.clientWidth)).toBe(true);
  const output = process.env['KOINON_SESSION_SCREENSHOTS'];
  if (output) await page.screenshot({ path: `${output}/session-1440-light-en-zoom200.png`, animations: 'disabled' });
  await page.keyboard.press('Escape'); await expect(dialog).toHaveCount(0);
});
