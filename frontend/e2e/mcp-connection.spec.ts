// Copyright 2026 Firefly Software Foundation
// SPDX-License-Identifier: Apache-2.0
import { test, expect, type Page } from '@playwright/test';
import { mockService } from './fixtures';
import { mkdir } from 'node:fs/promises';
import { resolve } from 'node:path';
async function setup(page: Page) {
  await mockService(page);
  await page.route('**/bff/api/v1/authorized-applications**', (route) =>
    route.fulfill({
      json: { items: [], total: 0, page: 1, page_size: 25, pages: 0 },
    }),
  );
}

for (const width of [1440, 390])
  test(`connection setup uses the deployment endpoint and explicit OAuth client at ${width}`, async ({
    page,
  }) => {
    await page.setViewportSize({ width, height: 1100 });
    await setup(page);
    await page.route('**/bff/api/v1/tenants/tenant-one/mcp/connection', (r) =>
      r.fulfill({
        json: {
          enabled: true,
          endpoint: 'https://knowledge.northstar.example/mcp',
          transport: 'streamable-http',
          authentication: ['personal_token', 'oauth'],
          oauth_enabled: true,
          oauth_registration: 'pre_registered',
          supported_scopes: ['catalog:read', 'catalog:write', 'ingest:write'],
          tools: [],
          review: {
            supported: true,
            mechanism: 'mcp_apps',
            resource_uri: 'ui://koinon/knowledge-review',
            mime_type: 'text/html;profile=mcp-app',
            external_redirect: false,
            client_support: 'not_observed',
          },
          clients: [
            {
              client_id: 'northstar-chat-client',
              name: 'Organization chat client',
              scopes: ['catalog:read', 'catalog:write', 'ingest:write'],
              client_auth: 'public',
            },
          ],
          client_acceptance: 'not_verified',
        },
      }),
    );
    await page.goto('/');
    await page.getByRole('button', { name: 'Account menu', exact: true }).click();
    await page.getByRole('menuitem', { name: 'Authorized applications', exact: true }).click();
    await page.getByRole('button', { name: 'Connect an app', exact: true }).click();
    await expect(page.getByRole('textbox', { name: 'MCP server URL', exact: true })).toHaveValue(
      'https://knowledge.northstar.example/mcp',
    );
    await page
      .getByLabel('Registered OAuth application', { exact: true })
      .selectOption('northstar-chat-client');
    await expect(page.getByRole('textbox', { name: 'OAuth client ID', exact: true })).toHaveValue(
      'northstar-chat-client',
    );
    await page.getByLabel('Chat application', { exact: true }).selectOption('chatgpt');
    await expect(page.getByText('Add the MCP server in ChatGPT.', { exact: true })).toBeVisible();
    expect(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth)).toBe(
      true,
    );
    const out = resolve(__dirname, '../../../../outputs/mcp-connection');
    await mkdir(out, { recursive: true });
    await page.screenshot({ path: resolve(out, `connection-${width}.png`) });
  });
test('disabled MCP gives an operator action without suggesting an unusable connection', async ({
  page,
}) => {
  await setup(page);
  await page.route('**/bff/api/v1/tenants/tenant-one/mcp/connection', (r) =>
    r.fulfill({
      json: {
        enabled: false,
        endpoint: null,
        transport: 'streamable-http',
        authentication: ['personal_token'],
        oauth_enabled: false,
        oauth_registration: null,
        supported_scopes: [],
        tools: [],
        review: {
          supported: false,
          mechanism: 'mcp_apps',
          resource_uri: 'ui://koinon/knowledge-review',
          mime_type: 'text/html;profile=mcp-app',
          external_redirect: false,
          client_support: 'not_observed',
        },
        clients: [],
        client_acceptance: 'not_verified',
      },
    }),
  );
  await page.goto('/');
  await page.getByRole('button', { name: 'Account menu', exact: true }).click();
  await page.getByRole('menuitem', { name: 'Authorized applications', exact: true }).click();
  await page.getByRole('button', { name: 'Connect an app', exact: true }).click();
  await expect(
    page.getByText('MCP is disabled for this installation.', { exact: true }),
  ).toBeVisible();
  await expect(page.getByRole('textbox', { name: 'MCP server URL', exact: true })).toHaveCount(0);
});

test('local listener URL explains desktop access without promising hosted connectivity', async ({
  page,
}) => {
  await page.setViewportSize({ width: 1440, height: 1100 });
  await setup(page);
  await page.route('**/bff/api/v1/tenants/tenant-one/mcp/connection', (route) =>
    route.fulfill({
      json: {
        enabled: true,
        endpoint: 'http://127.0.0.1:18781/mcp',
        local_only: true,
        transport: 'streamable-http',
        authentication: ['personal_token'],
        oauth_enabled: false,
        oauth_registration: null,
        clients: [],
        supported_scopes: ['catalog:read'],
        tools: [],
        review: {
          supported: true,
          mechanism: 'mcp_apps',
          resource_uri: 'ui://koinon/knowledge-review',
          mime_type: 'text/html;profile=mcp-app',
          external_redirect: false,
          client_support: 'not_observed',
        },
        client_acceptance: 'not_verified',
      },
    }),
  );
  await page.goto('/');
  await page.getByRole('button', { name: 'Account menu', exact: true }).click();
  await page.getByRole('menuitem', { name: 'Authorized applications', exact: true }).click();
  await page.getByRole('button', { name: 'Connect an app', exact: true }).click();
  const address = page.getByRole('textbox', { name: 'MCP server URL', exact: true });
  await expect(address).toHaveValue('http://127.0.0.1:18781/mcp');
  await expect(address).toHaveAccessibleDescription(/This address is local to the server computer/);
  await expect(
    page.getByText(
      'Hosted chat applications need a reachable HTTPS address configured by your administrator.',
      { exact: true },
    ),
  ).toBeVisible();
  await page.evaluate(() => {
    const note = document.createElement('p');
    note.textContent = 'Local connection preview using controlled service data.';
    document
      .querySelector<HTMLElement>('ffk-workbench')
      ?.style.setProperty('--koinon-workspace-height', 'calc(100dvh - 26px)');
    note.style.cssText =
      'position:fixed;bottom:0;left:0;right:0;margin:0;padding:5px;background:#855414;color:white;text-align:center;font:11px/16px sans-serif;z-index:99999';
    document.body.append(note);
  });
  const output = resolve(__dirname, '../../../../outputs/mcp-connection');
  await mkdir(output, { recursive: true });
  await page.screenshot({ path: resolve(output, 'local-1440.png') });
});
