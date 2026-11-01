// Copyright 2026 Firefly Software Foundation SPDX-License-Identifier: Apache-2.0
import { mkdir } from 'node:fs/promises';
import { resolve } from 'node:path';
import { test, expect, type Page } from '@playwright/test';
import { openAdministration,  mockService } from './fixtures';
async function configurationFixture(page: Page) {
  await mockService(page);
  const providers: Record<string, unknown>[] = [],
    agents: Record<string, unknown>[] = [],
    writes: { path: string; body: unknown }[] = [];
  await page.route('**/bff/api/v1/tenants/*/**', async (route) => {
    const request = route.request(),
      path = new URL(request.url()).pathname,
      json = (body: unknown, status = 200) =>
        route.fulfill({ status, contentType: 'application/json', body: JSON.stringify(body) });
    if (path.endsWith('/configuration'))
      return json({
        providers,
        provider_types: [
          {
            id: 'ollama',
            name: 'Ollama',
            fields: [
              { name: 'name', label: 'Display name', type: 'text', required: true },
              {
                name: 'base_url',
                label: 'Provider address',
                type: 'url',
                required: true,
                default: 'http://127.0.0.1:11434',
              },
              { name: 'model_ids', label: 'Models', type: 'string_list', required: true },
            ],
          },
        ],
        connections: [],
        checks: [],
      });
    if (request.method() !== 'GET') writes.push({ path, body: request.postDataJSON() });
    if (path.endsWith('/providers') && request.method() === 'POST') {
      const provider = {
        ...request.postDataJSON(),
        id: 'provider-one',
        revision: 1,
        secret_configured: false,
        validated: false,
        checks: [],
      };
      providers.push(provider);
      return json(provider, 201);
    }
    if (path.endsWith('/providers/provider-one/validate')) {
      Object.assign(providers[0], {
        validated: true,
        checks: [
          { id: 'reachable', status: 'passed', message: 'The selected local model is available' },
        ],
      });
      return json({
        provider_id: 'provider-one',
        revision: 1,
        status: 'ready',
        checks: providers[0]['checks'],
      });
    }
    if (path.endsWith('/agents')) {
      if (request.method() === 'POST') {
        const agent = {
          ...request.postDataJSON(),
          id: 'agent-one',
          revision: 1,
          status: 'needs_setup',
          checks: [],
        };
        agents.push(agent);
        return json(agent, 201);
      }
      return json({ items: agents, total: agents.length, page: 1, page_size: 25, pages: 1 });
    }
    if (path.endsWith('/agents/agent-one/validate')) {
      Object.assign(agents[0], {
        status: 'ready',
        checks: [{ id: 'model', status: 'passed', message: 'Agent checks passed' }],
      });
      return json(agents[0]);
    }
    return route.fallback();
  });
  return { providers, agents, writes };
}
test('operator saves and checks a descriptor-backed provider before configuring an agent', async ({
  page,
}) => {
  const service = await configurationFixture(page);
  await page.goto('/library');
  await openAdministration(page, 'Settings');
  await page.getByRole('button', { name: 'Connect a model', exact: true }).click();
  await page.getByRole('button', { name: 'Ollama', exact: true }).click();
  await page
    .getByRole('textbox', { name: 'Display name', exact: true })
    .fill('Local research model');
  await page.getByRole('textbox', { name: 'Models', exact: true }).fill('existing-local-model');
  await page.getByRole('button', { name: 'Save provider', exact: true }).click();
  expect(service.providers[0]['validated']).toBe(false);
  await page.getByRole('button', { name: 'Check connection', exact: true }).click();
  await expect(page.getByText('The selected local model is available')).toBeVisible();
  expect(service.providers[0]['validated']).toBe(true);
  await page.getByRole('button', { name: 'Done', exact: true }).click();
  await page.getByRole('button', { name: 'Agents', exact: true }).click();
  await page.getByRole('button', { name: 'Create an agent', exact: true }).click();
  await page.getByRole('textbox', { name: 'Agent name', exact: true }).fill('Research assistant');
  await page
    .getByRole('combobox', { name: 'Model provider', exact: true })
    .selectOption('provider-one');
  await page
    .getByRole('combobox', { name: 'Model', exact: true })
    .selectOption('existing-local-model');
  await page.getByRole('checkbox', { name: 'Search knowledge', exact: true }).check();
  await page.getByRole('button', { name: 'Save agent', exact: true }).click();
  await page.getByRole('button', { name: 'Check agent', exact: true }).click();
  await expect(page.getByText('Agent checks passed')).toBeVisible();
  expect(service.agents[0]['status']).toBe('ready');
  expect(
    service.writes.some(
      (write) =>
        write.path.endsWith('/providers') && (write.body as { kind: string }).kind === 'ollama',
    ),
  ).toBe(true);
});
test('required provider fields are validated before a write is sent', async ({ page }) => {
  const service = await configurationFixture(page);
  await page.goto('/library');
  await openAdministration(page, 'Settings');
  await page.getByRole('button', { name: 'Connect a model', exact: true }).click();
  await page.getByRole('button', { name: 'Ollama', exact: true }).click();
  await page.getByRole('button', { name: 'Save provider', exact: true }).click();
  await expect(page.getByText('This field is required.').first()).toBeVisible();
  expect(service.writes.some((write) => write.path.endsWith('/providers'))).toBe(false);
});

for (const width of [1440, 390])
  test(`controlled Settings review ${width}`, async ({ page }) => {
    await page.setViewportSize({ width, height: 1000 });
    await configurationFixture(page);
    await page.goto('/library');
    if (width < 700)
      await page.getByRole('button', { name: 'Open navigation', exact: true }).click();
    await openAdministration(page, 'Settings');
    await expect(page.getByRole('heading', { name: 'Providers', exact: true })).toBeVisible();
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
    const dir = resolve('../../control/frontend-captures/atomic-stage3');
    await mkdir(dir, { recursive: true });
    expect(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth)).toBe(
      true,
    );
    await page.screenshot({
      path: resolve(dir, `settings-${width}.png`),
      fullPage: true,
      animations: 'disabled',
    });
    await page.getByRole('button', { name: 'Connect a model', exact: true }).click();
    await page.getByRole('button', { name: 'Ollama', exact: true }).click();
    await page.screenshot({
      path: resolve(dir, `provider-form-${width}.png`),
      fullPage: true,
      animations: 'disabled',
    });
  });
test('mobile sections retain a visible label and provider Back retains entered details', async ({
  page,
}) => {
  await page.setViewportSize({ width: 390, height: 900 });
  await configurationFixture(page);
  await page.goto('/library');
  await page.getByRole('button', { name: 'Open navigation', exact: true }).click();
  await openAdministration(page, 'Settings');
  await expect(page.getByRole('combobox', { name: 'Settings section', exact: true })).toHaveValue(
    'providers',
  );
  await page.getByRole('button', { name: 'Connect a model', exact: true }).click();
  await page.getByRole('button', { name: 'Ollama', exact: true }).click();
  await page
    .getByRole('textbox', { name: 'Display name', exact: true })
    .fill('Existing local model');
  await expect(page.getByText('Provider type: Ollama', { exact: true })).toBeVisible();
  await page.getByRole('button', { name: 'Back', exact: true }).click();
  await page.getByRole('button', { name: 'Ollama', exact: true }).click();
  await expect(page.getByRole('textbox', { name: 'Display name', exact: true })).toHaveValue(
    'Existing local model',
  );
  expect(
    await page
      .locator('ffk-shell footer')
      .evaluate((el) => parseFloat(getComputedStyle(el).fontSize)),
  ).toBeGreaterThanOrEqual(11);
});
test('Settings keeps local navigation visible while its form pane scrolls', async ({ page }) => {
  await page.setViewportSize({ width: 1440, height: 600 });
  await configurationFixture(page);
  await page.goto('/library');
  await openAdministration(page, 'Settings');
  await page.getByRole('button', { name: 'Connect a model', exact: true }).click();
  await page.getByRole('button', { name: 'Ollama', exact: true }).click();
  const navigation = page.getByRole('navigation', { name: 'Settings sections', exact: true });
  const pane = page.locator('.settings-content');
  await expect(page.getByRole('button', { name: 'Save provider', exact: true })).toBeVisible();
  await expect.poll(() => pane.evaluate((el) => el.scrollHeight > el.clientHeight)).toBe(true);
  const before = await navigation.boundingBox();
  await pane.evaluate((el) => (el.scrollTop = el.scrollHeight));
  await expect(page.getByRole('button', { name: 'Save provider', exact: true })).toBeInViewport();
  const after = await navigation.boundingBox();
  expect(after?.y).toBe(before?.y);
  expect(await page.locator('.settings-content').evaluate((el) => el.scrollTop)).toBeGreaterThan(0);
  expect(
    await page.locator('ffk-shell main#knowledge-content').evaluate((el) => el.scrollTop),
  ).toBe(0);
});
test('deployment diagnostics keep an unprobed store unknown and expose no edit action', async ({
  page,
}) => {
  await mockService(page);
  const observed = {
    configured: true,
    available: null,
    status: 'unknown',
    observed_at: '2026-10-26T10:00:00Z',
    reason: 'Storage is configured; no external probe was performed.',
  };
  await page.route('**/bff/api/v1/tenants/*/configuration', (route) =>
    route.fulfill({
      contentType: 'application/json',
      body: JSON.stringify({
        providers: [],
        provider_types: [],
        connections: [],
        checks: [],
        deployment: {
          ownership: 'deployment',
          read_only: true,
          datasources: [
            {
              ...observed,
              id: 'structured',
              kind: 'database',
              driver: 'postgresql',
              available: false,
              status: 'failed',
              reason: 'Database probe failed',
              pool: { size: 5, max_overflow: 10, timeout: 30, recycle: 3600, pre_ping: true },
            },
          ],
          storage: [
            {
              ...observed,
              id: 'documents',
              backend: 's3',
              ownership: 'deployment',
              read_only: true,
              store_originals: true,
            },
          ],
          indexes: [
            {
              ...observed,
              id: 'document-vectors',
              available: true,
              status: 'passed',
              reason: 'Vector prerequisites checked',
              embedding_sets: 1,
              physical_indexes: 1,
            },
          ],
          metrics: { ...observed, exporter_configured: true, names: [] },
          limits: {
            worker_concurrency: 1,
            max_queued_per_subject: 50,
            job_lease_seconds: 60,
            max_index_workspaces: 32,
          },
        },
      }),
    }),
  );
  await page.goto('/library');
  await openAdministration(page, 'Settings');
  await page.getByRole('button', { name: 'Storage & indexing', exact: true }).click();
  await page.getByText('Deployment observations', { exact: true }).click();
  await expect(
    page.getByText('Managed by your deployment administrator.', { exact: true }),
  ).toBeVisible();
  const storage = page
    .locator('ffk-deployment-panel article')
    .filter({ has: page.getByRole('heading', { name: 'Documents', exact: true }) });
  await expect(storage.getByText('Not checked', { exact: true })).toBeVisible();
  await expect(storage.getByText('Available', { exact: true })).toHaveCount(0);
  await expect(page.getByRole('button', { name: 'Save', exact: true })).toHaveCount(0);
  await expect(page.getByText('Needs attention', { exact: true })).toBeVisible();
});
