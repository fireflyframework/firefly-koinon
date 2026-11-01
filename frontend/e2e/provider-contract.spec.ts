// Copyright 2026 Firefly Software Foundation SPDX-License-Identifier: Apache-2.0
import { test, expect, type Page } from '@playwright/test';
import { openAdministration,  mockService } from './fixtures';
const provider = {
  id: 'provider-one',
  name: 'Controlled model connection',
  kind: 'openai',
  api: 'chat',
  base_url: 'https://api.openai.com/v1',
  model_ids: ['existing-model'],
  enabled: true,
  revision: 1,
  secret_configured: true,
  configured: true,
  connected: true,
  discovered: true,
  validated: false,
  checks: [],
  model_capabilities: [
    {
      model_id: 'existing-model',
      chat: { supported: null, verified: false },
      streaming: { supported: null, verified: false },
      tools: { supported: null, verified: false },
      observed_tools: [],
      option_fields: ['max_tokens', 'temperature', 'store_responses', 'stop_sequences'],
    },
  ],
};
async function contract(page: Page) {
  await mockService(page);
  const providers = [structuredClone(provider)],
    agents: Record<string, unknown>[] = [],
    writes: { path: string; body: Record<string, unknown> }[] = [];
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
            id: 'openai',
            name: 'OpenAI',
            fields: [
              {
                name: 'api',
                label: 'Model API',
                type: 'select',
                required: true,
                default: 'chat',
                options: [
                  { value: 'chat', label: 'chat' },
                  { value: 'responses', label: 'responses' },
                ],
              },
              { name: 'name', label: 'Display name', type: 'text', required: true },
              { name: 'base_url', label: 'Provider address', type: 'url', required: true },
              { name: 'model_ids', label: 'Models', type: 'string_list', required: true },
              {
                name: 'secret',
                label: 'API key',
                type: 'secret',
                required: true,
                write_only: true,
              },
            ],
          },
        ],
        connections: [],
        checks: [],
        model_options_schema: {
          properties: {
            max_tokens: { type: 'integer', minimum: 64, maximum: 16384, default: 4096 },
            temperature: { anyOf: [{ type: 'number', minimum: 0, maximum: 2 }, { type: 'null' }] },
            store_responses: { anyOf: [{ type: 'boolean' }, { type: 'null' }] },
            stop_sequences: {
              anyOf: [
                {
                  type: 'array',
                  maxItems: 8,
                  items: { type: 'string', minLength: 1, maxLength: 256 },
                },
                { type: 'null' },
              ],
            },
          },
        },
      });
    if (request.method() !== 'GET') {
      expect(request.headers()['x-xsrf-token']).toBe('synthetic-csrf+token');
      writes.push({ path, body: request.postDataJSON() });
    }
    if (path.endsWith('/providers/provider-one') && request.method() === 'PUT') {
      Object.assign(providers[0], request.postDataJSON(), {
        secret_configured: request.postDataJSON().secret === null ? false : true,
        discovered: false,
      });
      return json(providers[0]);
    }
    if (path.endsWith('/agents')) {
      if (request.method() === 'POST') {
        const agent = {
          ...request.postDataJSON(),
          id: 'trial-agent',
          revision: 1,
          status: 'unverified',
          can_run: true,
          configured: true,
          checks: [
            { id: 'generation', status: 'unverified', message: 'Generation has not been checked.' },
          ],
        };
        agents.push(agent);
        return json(agent, 201);
      }
      return json({ items: agents, total: agents.length, page: 1, page_size: 25, pages: 1 });
    }
    return route.fallback();
  });
  return { providers, agents, writes };
}
test('provider API choice and explicit key removal use the native request contract', async ({
  page,
}) => {
  const service = await contract(page);
  await page.goto('/library');
  await openAdministration(page, 'Settings');
  await page.getByRole('button', { name: 'Edit', exact: true }).click();
  await page.getByRole('combobox', { name: 'Model API', exact: true }).selectOption('responses');
  await page.getByRole('checkbox', { name: 'Remove the current API key', exact: true }).check();
  await expect(page.getByLabel('API key', { exact: true })).toBeDisabled();
  await page.getByRole('button', { name: 'Save provider', exact: true }).click();
  expect(service.writes[0].body).toMatchObject({ api: 'responses', secret: null });
  await expect(page.getByText('Ready', { exact: true })).toHaveCount(0);
});
test('schema-backed options reject invalid input and retain false before an unverified agent trial', async ({
  page,
}) => {
  const service = await contract(page);
  service.providers[0].api = 'responses';
  await page.goto('/library');
  await openAdministration(page, 'Settings');
  await page.getByText('Model capabilities', { exact: true }).first().click();
  await expect(page.getByRole('cell', { name: 'Not checked', exact: true })).toHaveCount(3);
  await page.getByRole('button', { name: 'Agents', exact: true }).click();
  await page.getByRole('button', { name: 'Create an agent', exact: true }).click();
  await page
    .getByRole('textbox', { name: 'Agent name', exact: true })
    .fill('Controlled trial agent');
  await page
    .getByRole('combobox', { name: 'Model provider', exact: true })
    .selectOption('provider-one');
  await page.getByRole('combobox', { name: 'Model', exact: true }).selectOption('existing-model');
  await page.getByText('Advanced model options', { exact: true }).click();
  await page.getByRole('spinbutton', { name: 'Maximum output tokens', exact: true }).fill('64.5');
  await page.getByRole('button', { name: 'Save agent', exact: true }).click();
  await expect(
    page.getByText('Enter a whole number within the displayed limits.', { exact: true }),
  ).toBeVisible();
  expect(service.writes.filter((write) => write.path.endsWith('/agents'))).toHaveLength(0);
  await page.getByRole('spinbutton', { name: 'Maximum output tokens', exact: true }).fill('8192');
  await page
    .getByRole('combobox', { name: 'Provider response storage', exact: true })
    .selectOption('false');
  await page.getByRole('button', { name: 'Add sequence', exact: true }).click();
  await page.getByRole('textbox', { name: 'Stop sequences 1', exact: true }).fill(' END ');
  await page.getByRole('button', { name: 'Save agent', exact: true }).click();
  expect(
    service.writes.find((write) => write.path.endsWith('/agents'))?.body['model_options'],
  ).toEqual({ max_tokens: 8192, store_responses: false, stop_sequences: [' END '] });
  await expect(page.getByRole('button', { name: 'Try agent', exact: true })).toBeVisible();
  await expect(page.getByText('Ready', { exact: true })).toHaveCount(0);
});
