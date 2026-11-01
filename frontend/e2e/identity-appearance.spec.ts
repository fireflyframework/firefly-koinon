// Copyright 2026 Firefly Software Foundation
// SPDX-License-Identifier: Apache-2.0
// Controlled service fixtures verify the interface and requests, not a deployed identity.
import { test, expect, type Page } from '@playwright/test';
import { mkdir } from 'node:fs/promises';
import { resolve } from 'node:path';
import { openAdministration,  mockService } from './fixtures';
const defaults = {
  product_name: 'koinon',
  assistant_name: 'koinon',
  font_family: 'Manrope',
  logo_light: null,
  logo_dark: null,
  symbol: null,
  favicon: null,
  palette: {
    light: {
      surface: '#ffffff',
      canvas: '#f3f1eb',
      text: '#272820',
      muted: '#62645b',
      line: '#d8d4ca',
      action: '#ffb34a',
      action_text: '#10110f',
      accent: '#855414',
    },
    dark: {
      surface: '#1d1f1a',
      canvas: '#10110f',
      text: '#f3f1eb',
      muted: '#bfb8ab',
      line: '#474a42',
      action: '#ffb34a',
      action_text: '#10110f',
      accent: '#ffb34a',
    },
  },
};
async function setup(page: Page) {
  await mockService(page);
  let branding = structuredClone(defaults),
    revision = 0,
    origin = 'deployment';
  const writes: unknown[] = [];
  await page.route('**/bff/api/v1/branding/defaults', (r) => r.fulfill({ json: defaults }));
  await page.route('**/bff/api/v1/tenants/*/branding{,/reset}', async (route) => {
    const req = route.request(),
      tenant = new URL(req.url()).pathname.split('/')[5];
    if (req.method() !== 'GET') {
      const body = req.postDataJSON();
      writes.push(body);
      if (body.expected_revision !== revision)
        return route.fulfill({ status: 409, json: { detail: 'Changed' } });
      branding = req.method() === 'POST' ? structuredClone(defaults) : body.branding;
      origin = req.method() === 'POST' ? 'deployment' : 'organization';
      ++revision;
    }
    await route.fulfill({
      json: { tenant_id: tenant, schema_version: 1, revision, origin, branding },
    });
  });
  await page.goto('/library');
  if ((page.viewportSize()?.width ?? 1440) < 1100)
    await page.getByRole('button', { name: 'Open navigation', exact: true }).click();
  await openAdministration(page, 'Settings');
  if ((page.viewportSize()?.width ?? 1440) < 700)
    await page.getByLabel('Settings section', { exact: true }).selectOption('identity');
  else await page.getByRole('button', { name: 'Identity & appearance', exact: true }).click();
  await expect(page.getByLabel('Product name', { exact: true })).toHaveValue('koinon');
  return writes;
}
async function screenshot(page: Page, name: string) {
  const output = resolve(__dirname, '../../../../outputs');
  await mkdir(output, { recursive: true });
  await page.evaluate(() => {
    const b =
      document.querySelector<HTMLElement>('[data-qualification=branding-fixtures]') ??
      document.createElement('div');
    document
      .querySelector<HTMLElement>('ffk-workbench')
      ?.style.setProperty('--koinon-workspace-height', 'calc(100dvh - 20px)');
    b.dataset['qualification'] = 'branding-fixtures';
    b.textContent = 'Controlled service fixtures, Identity & appearance';
    Object.assign(b.style, {
      position: 'fixed',
      bottom: '0',
      left: '0',
      right: '0',
      background: '#855414',
      color: '#fff',
      padding: '4px',
      font: '11px sans-serif',
      textAlign: 'center',
      zIndex: '99999',
    });
    document.body.append(b);
  });
  await page.locator('ffk-identity-appearance h2').scrollIntoViewIfNeeded();
  await page.screenshot({ path: resolve(output, name), fullPage: true, animations: 'disabled' });
}
test('previews, saves and resets organization identity with exact revision', async ({ page }) => {
  await page.setViewportSize({ width: 1440, height: 1080 });
  const writes = await setup(page);
  await page.getByLabel('Product name', { exact: true }).fill('Northstar Knowledge');
  await page.getByLabel('Assistant name', { exact: true }).fill('Northstar');
  await page.getByRole('tab', { name: 'Colors', exact: true }).click();
  await page.getByRole('textbox', { name: 'Primary button', exact: true }).fill('#2563eb');
  await page.getByRole('textbox', { name: 'Button text', exact: true }).fill('#ffffff');
  await page.getByRole('textbox', { name: 'Links & focus', exact: true }).fill('#1d4ed8');
  await expect(page.locator('ffk-shell .brand')).toHaveAccessibleName('koinon, Chat');
  await screenshot(page, 'koinon-identity-refined-palette.png');
  await page.getByRole('button', { name: 'Save changes', exact: true }).click();
  await expect(page.getByRole('status')).toContainText('Identity saved.');
  expect(writes[0]).toMatchObject({
    expected_revision: 0,
    branding: { product_name: 'Northstar Knowledge' },
  });
  await expect(page.locator('ffk-shell .brand')).toHaveAccessibleName(
    'Northstar Knowledge, Chat',
  );
  await expect(page).toHaveTitle('Northstar Knowledge');
  await page.getByRole('tab', { name: 'Identity', exact: true }).click();
  await screenshot(page, 'koinon-identity-refined-applied.png');
  await page
    .locator('ffk-identity-preview')
    .getByRole('button', { name: 'Sign-in', exact: true })
    .click();
  await screenshot(page, 'koinon-identity-refined-login.png');
  await page.getByRole('button', { name: 'Use deployment defaults', exact: true }).click();
  expect(writes).toHaveLength(1);
  await page.getByRole('button', { name: 'Save changes', exact: true }).click();
  expect(writes[1]).toEqual({ expected_revision: 1 });
  await expect(page).toHaveTitle('firefly koinon');
});
test('previews bundled Inter locally and applies it after saving the organization identity', async ({
  page,
}) => {
  await page.setViewportSize({ width: 1440, height: 1080 });
  const writes = await setup(page);
  await page.getByLabel('Interface font', { exact: true }).selectOption('Inter');
  await expect
    .poll(() =>
      page
        .locator('ffk-identity-preview')
        .evaluate((element) => getComputedStyle(element).getPropertyValue('--ffk-font')),
    )
    .toContain('KoinonInter');
  expect(
    await page
      .locator('ffk-workbench')
      .evaluate((element) => getComputedStyle(element).getPropertyValue('--ffk-font')),
  ).toContain('KoinonManrope');
  expect(writes).toHaveLength(0);
  await screenshot(page, 'koinon-identity-inter-preview-20261031.png');
  await page.getByRole('button', { name: 'Save changes', exact: true }).click();
  expect(writes[0]).toMatchObject({ expected_revision: 0, branding: { font_family: 'Inter' } });
  await expect
    .poll(() =>
      page
        .locator('ffk-workbench')
        .evaluate((element) => getComputedStyle(element).getPropertyValue('--ffk-font')),
    )
    .toContain('KoinonInter');
});
test('keeps mobile proportions and prevents inaccessible palette changes', async ({ page }) => {
  await page.setViewportSize({ width: 390, height: 844 });
  await setup(page);
  await page.getByRole('tab', { name: 'Colors', exact: true }).click();
  await page.getByRole('textbox', { name: 'Text', exact: true }).fill('#ffffff');
  await expect(page.getByRole('button', { name: 'Save changes', exact: true })).toBeDisabled();
  await expect(page.getByRole('alert')).toContainText('4.5:1');
  await page.getByRole('textbox', { name: 'Text', exact: true }).fill('#272820');
  expect(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth)).toBe(true);
  await page.getByRole('button', { name: 'Dark', exact: true }).click();
  await page.getByRole('button', { name: 'Preview your identity', exact: true }).click();
  await screenshot(page, 'koinon-identity-refined-mobile.png');
});

test('uses installation identity before sign-in without requesting organization branding', async ({
  page,
}) => {
  await mockService(page, { authenticated: false });
  const requests: string[] = [];
  await page.route('**/bff/api/v1/branding/defaults', (route) =>
    route.fulfill({
      json: { ...defaults, product_name: 'Northstar Knowledge', assistant_name: 'Northstar' },
    }),
  );
  await page.route('**/bff/api/v1/tenants/*/branding', (route) => {
    requests.push(route.request().url());
    return route.fulfill({ status: 401, json: { detail: 'Sign in required' } });
  });
  await page.goto('/library');
  await expect(
    page.getByRole('heading', { name: 'Welcome to Northstar Knowledge', exact: true }),
  ).toBeVisible();
  await expect(page.getByRole('button', { name: 'Sign in', exact: true })).toBeVisible();
  expect(requests).toEqual([]);
  await expect(page).toHaveTitle('Northstar Knowledge');
});
