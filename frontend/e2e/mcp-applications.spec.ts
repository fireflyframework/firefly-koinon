// Copyright 2026 Firefly Software Foundation
// SPDX-License-Identifier: Apache-2.0
// Controlled HTTP fixtures exercise the actual Angular interface, not hosted client linking.
import { test, expect, type Page } from '@playwright/test';
import type { McpOAuthClient } from '@fireflyframework/koinon-sdk';
import { mkdir } from 'node:fs/promises';
import { resolve } from 'node:path';
import { openAdministration,  mockService } from './fixtures';

const registered: McpOAuthClient = {
  id: 'client-one',
  tenant_id: 'tenant-one',
  client_id: 'koinon_org_team_chat',
  name: 'Team chat',
  client_type: 'confidential',
  redirect_uris: ['https://chat.example.test/callback'],
  scopes: ['catalog:read', 'knowledge:search'],
  enabled: true,
  revision: 1,
  created_at: '2026-10-29T09:00:00Z',
  updated_at: '2026-10-29T10:30:00Z',
  created_by: 'alex.rivera@example.test',
  updated_by: 'alex.rivera@example.test',
};
async function setup(page: Page, conflict = false, total = 3, spanish = false) {
  await mockService(page);
  if (spanish)
    await page.route('**/bff/api/v1/profile', (route) =>
      route.fulfill({
        json: {
          subject: 'synthetic.reviewer',
          display_name: 'Alex Rivera',
          locale: 'es-ES',
          time_zone: 'Europe/Madrid',
          response_language: 'es',
          avatar_url: null,
          avatar_version: null,
        },
      }),
    );
  const writes: { method: string; body: Record<string, unknown> }[] = [];
  const reads: Record<string, string>[] = [];
  let row = structuredClone(registered);
  await page.route('**/bff/api/v1/tenants/tenant-one/mcp/oauth-clients**', async (route) => {
    const request = route.request(),
      url = new URL(request.url());
    if (url.pathname.endsWith('/readiness'))
      return route.fulfill({
        json: {
          ready: true,
          endpoint_enabled: true,
          oauth_enabled: true,
          encryption_configured: true,
          missing_configuration: [],
          static_clients_read_only: true,
        },
      });
    if (request.method() === 'GET') {
      reads.push(Object.fromEntries(url.searchParams));
      return route.fulfill({
        json: url.pathname.endsWith('/client-one')
          ? row
          : {
              items: [
                row,
                {
                  ...registered,
                  id: 'client-two',
                  client_id: 'koinon_org_research_desktop',
                  name: 'Research desktop',
                  client_type: 'public',
                },
                {
                  ...registered,
                  id: 'client-three',
                  client_id: 'koinon_org_reporting',
                  name: 'Team reporting',
                  enabled: false,
                },
              ],
              total,
              page: Number(url.searchParams.get('page') ?? 1),
              page_size: Number(url.searchParams.get('page_size') ?? 25),
              pages: Math.ceil(total / Number(url.searchParams.get('page_size') ?? 25)),
            },
      });
    }
    const body: Record<string, unknown> = request.postDataJSON();
    writes.push({ method: request.method(), body });
    if (conflict)
      return route.fulfill({
        status: 409,
        json: { detail: 'Registration changed', code: 'CONFLICT' },
      });
    if (request.method() === 'POST') {
      row = { ...row, ...body, revision: row.revision + 1 } as McpOAuthClient;
      return route.fulfill({
        status: 201,
        json: { client: row, client_secret: 'example-once-not-a-real-credential' },
      });
    }
    row = { ...row, ...body, revision: row.revision + 1 } as McpOAuthClient;
    return route.fulfill({ json: row });
  });
  await page.goto('/library');
  await expect(page.locator('ffk-shell .topbar')).toBeVisible();
  const navigation = page.getByRole('button', {
    name: spanish ? 'Abrir navegación' : 'Open navigation',
    exact: true,
  });
  if (await navigation.isVisible()) await navigation.click();
  await openAdministration(page, spanish ? 'Configuración' : 'Settings');
  if ((page.viewportSize()?.width ?? 1440) < 700)
    await page
      .getByLabel(spanish ? 'Sección de configuración' : 'Settings section', { exact: true })
      .selectOption('applications');
  else
    await page
      .getByRole('button', { name: spanish ? 'Aplicaciones' : 'Applications', exact: true })
      .click();
  await expect(
    page.getByRole('heading', { name: spanish ? 'Aplicaciones' : 'Applications', exact: true }),
  ).toBeVisible();
  await expect(
    page.getByRole('button', {
      name: spanish ? 'Registrar aplicación' : 'Register application',
      exact: true,
    }),
  ).toBeEnabled();
  return { writes, reads };
}
async function screenshot(page: Page, name: string) {
  const output = resolve(__dirname, '../../../../outputs/oauth-applications');
  await mkdir(output, { recursive: true });
  await page.evaluate(() => {
    const note = document.createElement('div');
    note.dataset['qualification'] = 'oauth-applications';
    note.textContent = 'Application administration using controlled service data';
    note.style.cssText =
      'position:fixed;bottom:0;left:0;right:0;padding:4px;background:#855414;color:#fff;text-align:center;font:11px/16px Manrope,sans-serif;z-index:99999';
    document
      .querySelector<HTMLElement>('ffk-workbench')
      ?.style.setProperty('--koinon-workspace-height', 'calc(100dvh - 24px)');
    document.body.append(note);
  });
  await page.screenshot({ path: resolve(output, name + '.png'), fullPage: true });
  await page
    .locator('[data-qualification=oauth-applications]')
    .evaluateAll((nodes) => nodes.forEach((node) => node.remove()));
}
for (const width of [1440, 390]) {
  test(`guided application registration and one-time credential at ${width}`, async ({ page }) => {
    await page.setViewportSize({ width, height: 1100 });
    const { writes } = await setup(page);
    await screenshot(page, `list-${width}`);
    await page.getByRole('button', { name: 'Register application', exact: true }).click();
    await page.getByLabel('Application name', { exact: true }).fill('Organization research');
    await page.getByLabel('Callback URLs', { exact: true }).fill('https://chat.example.test/*');
    await expect(page.getByRole('button', { name: 'Continue', exact: true })).toBeDisabled();
    await page
      .getByLabel('Callback URLs', { exact: true })
      .fill('https://chat.example.test/exact-callback');
    await page.getByRole('radio', { name: /Confidential application/ }).check();
    await page.getByRole('button', { name: 'Continue', exact: true }).click();
    await page.getByRole('checkbox', { name: /Upload files/ }).check();
    await expect(page.getByRole('checkbox', { name: /Maintain knowledge/ })).toBeChecked();
    await page.getByRole('button', { name: 'Continue', exact: true }).click();
    await expect(
      page.getByRole('button', { name: 'Register application', exact: true }),
    ).toBeDisabled();
    await screenshot(page, `review-${width}`);
    await page
      .getByRole('checkbox', { name: 'I reviewed the callbacks and allowed access.', exact: true })
      .check();
    await page.getByRole('button', { name: 'Register application', exact: true }).click();
    await expect(
      page.getByRole('heading', { name: 'Save this client secret', exact: true }),
    ).toBeVisible();
    const secret = page.getByLabel('Client secret', { exact: true });
    await expect(secret).toHaveAttribute('type', 'password');
    await expect(
      page.getByRole('searchbox', { name: 'Search applications', exact: true }),
    ).toBeDisabled();
    await expect(page.getByLabel('Status', { exact: true })).toBeDisabled();
    await expect(page.getByLabel('Sort by', { exact: true })).toBeDisabled();
    await expect(page.getByLabel('Order', { exact: true })).toBeDisabled();
    expect(writes).toEqual([
      {
        method: 'POST',
        body: {
          name: 'Organization research',
          client_type: 'confidential',
          redirect_uris: ['https://chat.example.test/exact-callback'],
          scopes: ['catalog:read', 'catalog:write', 'ingest:write'],
        },
      },
    ]);
    expect(await page.evaluate(() => JSON.stringify([localStorage, sessionStorage]))).not.toContain(
      'example-once',
    );
    await page.getByRole('button', { name: 'I saved the secret', exact: true }).click();
    await expect(secret).toHaveCount(0);
    expect(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth)).toBe(
      true,
    );
  });
}
test('application filters, sorting and pagination are sent to the server', async ({ page }) => {
  const { reads } = await setup(page, false, 31);
  await page.getByRole('searchbox', { name: 'Search applications', exact: true }).fill('Team');
  await page.getByRole('button', { name: 'Apply application filter', exact: true }).click();
  await page.getByLabel('Status', { exact: true }).selectOption('enabled');
  await page.getByLabel('Sort by', { exact: true }).selectOption('updated_at');
  await page.getByLabel('Order', { exact: true }).selectOption('desc');
  await expect(
    page.getByRole('button', { name: 'Next applications page', exact: true }),
  ).toBeEnabled();
  await page.getByRole('button', { name: 'Next applications page', exact: true }).click();
  await expect
    .poll(() => reads.at(-1))
    .toMatchObject({ q: 'Team', status: 'enabled', sort: 'updated_at', order: 'desc', page: '2' });
});
test('disabling an application requires review and sends the displayed revision once', async ({
  page,
}) => {
  const { writes } = await setup(page);
  await page.getByRole('button', { name: 'Manage application Team chat', exact: true }).click();
  await page.getByRole('button', { name: 'Disable application', exact: true }).click();
  const confirmation = page.getByRole('region', { name: 'Disable this application?', exact: true });
  await expect(confirmation).toBeVisible();
  const apply = confirmation.getByRole('button', { name: 'Disable application', exact: true });
  await expect(apply).toBeDisabled();
  await screenshot(page, 'disable-1440');
  await confirmation
    .getByRole('checkbox', {
      name: 'I understand that existing connections will be revoked.',
      exact: true,
    })
    .check();
  await apply.click();
  await expect.poll(() => writes.length).toBe(1);
  expect(writes[0]).toEqual({ method: 'PATCH', body: { expected_revision: 1, enabled: false } });
});
test('a revision conflict requires reload without replaying the write', async ({ page }) => {
  const { writes } = await setup(page, true);
  await page.getByRole('button', { name: 'Manage application Team chat', exact: true }).click();
  await page.getByRole('button', { name: 'Disable application', exact: true }).click();
  const confirmation = page.getByRole('region', { name: 'Disable this application?', exact: true });
  await confirmation
    .getByRole('checkbox', {
      name: 'I understand that existing connections will be revoked.',
      exact: true,
    })
    .check();
  await confirmation.getByRole('button', { name: 'Disable application', exact: true }).click();
  await expect(page.getByRole('alert')).toBeVisible();
  await expect(
    page.getByRole('button', { name: 'Register application', exact: true }),
  ).toBeDisabled();
  expect(writes).toHaveLength(1);
});

test('Spanish mobile application setup preserves readable labels and scope vocabulary', async ({
  page,
}) => {
  await page.setViewportSize({ width: 390, height: 1100 });
  await setup(page, false, 3, true);
  await page.getByRole('button', { name: 'Registrar aplicación', exact: true }).click();
  await page.getByLabel('Nombre de la aplicación', { exact: true }).fill('Aplicación del equipo');
  await page
    .getByLabel('URLs de retorno', { exact: true })
    .fill('https://chat.example.test/callback');
  await page.getByRole('button', { name: 'Continuar', exact: true }).click();
  await expect(
    page.getByRole('checkbox', { name: 'Consultar el conocimiento', exact: true }),
  ).toBeChecked();
  await expect(
    page.getByRole('checkbox', { name: 'Inspeccionar respuestas guardadas', exact: true }),
  ).toBeVisible();
  expect(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth)).toBe(true);
});
