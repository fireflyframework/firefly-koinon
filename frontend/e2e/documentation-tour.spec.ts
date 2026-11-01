// Copyright 2026 Firefly Software Foundation
// SPDX-License-Identifier: Apache-2.0
// Screenshots show the built interface with synthetic, controlled service data.
import { test, expect, type Page } from '@playwright/test';
import { mkdir } from 'node:fs/promises';
import { resolve } from 'node:path';
import { openAdministration,  mockService } from './fixtures';
const output = resolve(__dirname, '../../../../outputs/documentation-tour');
async function capture(page: Page, name: string) {
  await mkdir(output, { recursive: true });
  await page.evaluate(async () => {
    await document.fonts.ready;
    document
      .querySelector<HTMLElement>('ffk-workbench')
      ?.style.setProperty('--koinon-workspace-height', 'calc(100dvh - 22px)');
    let note = document.querySelector<HTMLElement>('[data-docs-example]');
    if (!note) {
      note = document.createElement('div');
      note.dataset['docsExample'] = 'true';
      document.body.append(note);
    }
    note.textContent = 'Example workspace using controlled service data.';
    note.style.cssText =
      'position:fixed;bottom:0;left:0;right:0;height:22px;background:#855414;color:white;font:11px/22px sans-serif;text-align:center;z-index:99999';
    await new Promise<void>((done) =>
      requestAnimationFrame(() => requestAnimationFrame(() => done())),
    );
  });
  expect(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth)).toBe(true);
  await page.screenshot({ path: resolve(output, name + '.png'), animations: 'disabled' });
}
test('captures the library, upload, settings and profile walkthrough', async ({ page }) => {
  await page.setViewportSize({ width: 1440, height: 1050 });
  await mockService(page);
  await page.route('**/bff/api/v1/branding/defaults', (route) => route.fulfill({ json: {} }));
  await page.goto('/library');
  await expect(
    page.getByRole('button', { name: 'Research operations', exact: true }),
  ).toBeVisible();
  await capture(page, 'library-home');
  for (const name of ['Research operations', 'Operations intelligence', 'Reference library'])
    await page.getByRole('button', { name, exact: true }).click();
  await expect(page.getByRole('heading', { name: 'Reference library', exact: true })).toBeVisible();
  await capture(page, 'library-folder');
  await page.getByRole('button', { name: 'Quarterly service activity', exact: true }).click();
  await expect(page.getByLabel('Resource details', { exact: true })).toBeVisible();
  await capture(page, 'resource-details');
  await page.getByRole('button', { name: 'Close details', exact: true }).click();
  await page.getByRole('button', { name: 'Add knowledge', exact: true }).click();
  await page
    .getByRole('dialog')
    .getByRole('button', { name: /Upload files/ })
    .click();
  await page.getByLabel('Use these files as', { exact: true }).selectOption('dataset');
  await page.getByLabel('Choose files').setInputFiles({
    name: 'team-records.csv',
    mimeType: 'text/csv',
    buffer: Buffer.from('team,records\nOperations,24\n'),
  });
  await capture(page, 'upload-review');
  await page.keyboard.press('Escape');
  await openAdministration(page, 'Settings');
  await expect(page.getByRole('heading', { name: 'Providers', exact: true })).toBeVisible();
  await capture(page, 'organization-settings');
  await page.getByRole('button', { name: 'Account menu', exact: true }).click();
  await page.getByRole('menuitem', { name: 'Your account', exact: true }).click();
  await expect(page.getByRole('textbox', { name: 'Display name', exact: true })).toHaveValue(
    'Alex Rivera',
  );
  await capture(page, 'profile-preferences');
});
const tokenScopes = [
  ['catalog:read', 'Browse knowledge', []],
  ['catalog:write', 'Maintain knowledge', ['catalog:read']],
  ['knowledge:search', 'Search documents', ['catalog:read']],
  ['query:execute', 'Query datasets', ['catalog:read']],
  ['chat:use', 'Use agents and chat', ['catalog:read']],
  ['ingest:write', 'Import knowledge', ['catalog:read', 'catalog:write']],
  ['providers:write', 'Manage model providers', []],
  ['agents:write', 'Configure agents', []],
  ['jobs:manage', 'Manage processing jobs', []],
  ['sources:configure', 'Configure sources', []],
  ['indexes:manage', 'Manage indexes', []],
  ['audit:read', 'Read audit records', []],
  ['members:write', 'Manage people and access', []],
  ['settings:write', 'Manage organization settings', []],
  ['identity:manage', 'Manage identity policy', []],
  ['profile:read', 'Read your profile', []],
  ['profile:write', 'Update your profile', ['profile:read']],
].map(([id, name, dependencies]) => ({ id, name, dependencies }));
test('captures writable and organization token setup without creating secrets', async ({
  page,
}) => {
  await page.setViewportSize({ width: 1440, height: 1300 });
  await mockService(page);
  await page.route('**/bff/api/v1/branding/defaults', (route) => route.fulfill({ json: {} }));
  await page.route('**/bff/api/v1/tokens**', (route) => {
    expect(route.request().method()).toBe('GET');
    return route.fulfill({
      json: new URL(route.request().url()).pathname.endsWith('/scopes')
        ? { items: tokenScopes, max_lifetime_days: 90, max_active_per_user: 10 }
        : { items: [], total: 0, page: 1, page_size: 25, pages: 0 },
    });
  });
  await page.goto('/library');
  await page.getByRole('button', { name: 'Research operations', exact: true }).click();
  await page.getByRole('button', { name: 'Account menu', exact: true }).click();
  await page.getByRole('menuitem', { name: 'API tokens', exact: true }).click();
  await page.getByRole('button', { name: 'Create a token', exact: true }).click();
  await page
    .getByRole('textbox', { name: 'Token name', exact: true })
    .fill('Knowledge publishing integration');
  await page.getByRole('button', { name: 'Create & maintain knowledge', exact: true }).click();
  await expect(page.getByRole('checkbox', { name: 'Import knowledge', exact: true })).toBeChecked();
  await expect(
    page.getByRole('checkbox', { name: 'Maintain knowledge', exact: true }),
  ).toBeChecked();
  await expect(
    page.getByRole('checkbox', { name: 'Browse knowledge', exact: true }),
  ).toBeDisabled();
  await expect(page.getByRole('checkbox', { name: /Limit to current workspace/ })).toBeChecked();
  await expect(
    page.getByRole('checkbox', { name: 'Manage people and access', exact: true }),
  ).not.toBeVisible();
  await capture(page, 'token-knowledge-write-v3');
  await page.getByRole('button', { name: 'Administration', exact: true }).click();
  await page
    .getByRole('textbox', { name: 'Token name', exact: true })
    .fill('Organization administration integration');
  await expect(
    page.getByRole('checkbox', { name: /Limit to current workspace/ }),
  ).not.toBeChecked();
  await expect(
    page.getByRole('checkbox', { name: 'Manage people and access', exact: true }),
  ).toBeChecked();
  await expect(
    page.getByRole('checkbox', { name: 'Manage processing jobs', exact: true }),
  ).toBeChecked();
  await page.setViewportSize({ width: 1440, height: 1450 });
  await capture(page, 'token-organization-admin-v3');
  await page.getByRole('checkbox', { name: /Limit to current workspace/ }).check();
  await expect(
    page.getByRole('checkbox', { name: 'Manage people and access', exact: true }),
  ).not.toBeVisible();
  await expect(page.getByRole('status')).toContainText('Organization permissions were removed');
  await page.setViewportSize({ width: 390, height: 844 });
  await page.getByRole('textbox', { name: 'Token name', exact: true }).scrollIntoViewIfNeeded();
  await capture(page, 'token-knowledge-write-mobile-v3');
});
