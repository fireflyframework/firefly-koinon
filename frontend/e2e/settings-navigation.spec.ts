// Copyright 2026 Firefly Software Foundation SPDX-License-Identifier: Apache-2.0
// Controlled deferred HTTP responses reproduce the real initial Settings navigation race.
import { expect, test } from '@playwright/test';
import { mkdir } from 'node:fs/promises';
import { resolve } from 'node:path';
import { mockService } from './fixtures';
for (const width of [1440, 390])
  for (const failed of [false, true])
    test(`later Agents navigation survives initial provider metadata ${failed ? 'failure' : 'completion'} at ${width}px`, async ({
      page,
    }) => {
      await page.setViewportSize({ width, height: 1000 });
      await mockService(page);
      let release!: () => void, requested!: () => void;
      const gate = new Promise<void>((resolve) => {
        release = resolve;
      });
      const started = new Promise<void>((resolve) => {
        requested = resolve;
      });
      let settingsReads = 0;
      await page.route('**/bff/api/v1/tenants/*/configuration', async (route) => {
        requested();
        await gate;
        await route.fulfill({
          status: failed ? 503 : 200,
          json: failed
            ? { detail: 'Initial metadata unavailable', code: 'UNAVAILABLE' }
            : {
                providers: [
                  {
                    id: 'provider',
                    name: 'Delayed provider',
                    kind: 'ollama',
                    base_url: 'http://fixture.invalid',
                    model_ids: ['fixture-model'],
                    enabled: true,
                    validated: true,
                    discovered: true,
                    revision: 1,
                    secret_configured: false,
                    checks: [],
                  },
                ],
                provider_types: [],
                connections: [],
                checks: [],
              },
        });
      });
      await page.route('**/bff/api/v1/tenants/*/agents**', (route) =>
        route.fulfill({ json: { items: [], page: 1, pages: 0, total: 0 } }),
      );
      await page.route('**/bff/api/v1/tenants/*/chat/settings**', (route) => {
        ++settingsReads;
        return route.fulfill({
          json: {
            tenant_id: 'tenant-one',
            default_agent_id: null,
            revision: 0,
            configured: false,
            can_run: false,
            status: 'unconfigured',
          },
        });
      });
      await page.goto('/');
      const menu = page.getByRole('button', { name: 'Open navigation', exact: true });
      if (await menu.isVisible()) await menu.click();
      await page.getByRole('button', { name: 'Settings', exact: true }).click();
      await started;
      await expect(page.locator('ffk-settings-page')).toBeVisible();
      const mobile = page.getByRole('combobox', { name: 'Settings section', exact: true });
      if (width < 700) await mobile.selectOption('agents');
      else await page.getByRole('button', { name: 'Agents', exact: true }).click();
      await expect(page.getByRole('heading', { name: 'Agents', exact: true })).toBeVisible();
      await expect(page.locator('ffk-organization-chat-settings')).toBeVisible();
      await expect.poll(() => settingsReads).toBe(1);
      const completed = page.waitForResponse(
        (response) =>
          response.url().endsWith('/configuration') && response.status() === (failed ? 503 : 200),
      );
      release();
      await completed;
      if (failed)
        await expect(page.getByRole('alert')).toContainText('Initial metadata unavailable');
      else
        await expect(
          page.getByRole('button', { name: 'Create an agent', exact: true }),
        ).toBeEnabled();
      await expect(page.getByRole('heading', { name: 'Agents', exact: true })).toBeVisible();
      await expect(page.getByRole('heading', { name: 'Providers', exact: true })).toHaveCount(0);
      if (width < 700) await expect(mobile).toHaveValue('agents');
      else
        await expect(page.getByRole('button', { name: 'Agents', exact: true })).toHaveAttribute(
          'aria-current',
          'page',
        );
      const directory = resolve(process.cwd(), '.qualification-v23-settings-navigation/captures');
      await mkdir(directory, { recursive: true });
      await page.screenshot({
        path: resolve(
          directory,
          `agents-after-initial-metadata-${failed ? 'failure' : 'success'}-${width}.png`,
        ),
        animations: 'disabled',
      });
    });

for (const width of [1440, 390])
  test(`initial Agents failure remains visible after successful provider metadata at ${width}px`, async ({
    page,
  }) => {
    await page.setViewportSize({ width, height: 1000 });
    await mockService(page);
    await page.route('**/bff/api/v1/tenants/*/agents**', (route) =>
      route.fulfill({ json: { items: [], page: 1, pages: 0, total: 0 } }),
    );
    await page.route('**/bff/api/v1/tenants/*/chat/threads**', (route) =>
      route.fulfill({ json: { items: [], page: 1, pages: 0, total: 0 } }),
    );
    await page.goto('/');
    const menu = page.getByRole('button', { name: 'Open navigation', exact: true });
    if (await menu.isVisible()) await menu.click();
    await page.getByRole('button', { name: 'Chat', exact: true }).click();
    await expect(
      page.getByRole('heading', { name: 'koinon is unavailable right now.', exact: true }),
    ).toBeVisible();
    let releaseAgents!: () => void,
      releaseMetadata!: () => void,
      startedAgents!: () => void,
      startedMetadata!: () => void;
    const agentsGate = new Promise<void>((resolve) => {
        releaseAgents = resolve;
      }),
      metadataGate = new Promise<void>((resolve) => {
        releaseMetadata = resolve;
      });
    const agentsStarted = new Promise<void>((resolve) => {
        startedAgents = resolve;
      }),
      metadataStarted = new Promise<void>((resolve) => {
        startedMetadata = resolve;
      });
    await page.route('**/bff/api/v1/tenants/*/agents**', async (route) => {
      if (new URL(route.request().url()).searchParams.get('page_size') === '100')
        return route.fulfill({ json: { items: [], page: 1, pages: 0, total: 0 } });
      startedAgents();
      await agentsGate;
      return route.fulfill({
        status: 503,
        json: { detail: 'Agents are temporarily unavailable', code: 'UNAVAILABLE' },
      });
    });
    await page.route('**/bff/api/v1/tenants/*/configuration', async (route) => {
      startedMetadata();
      await metadataGate;
      return route.fulfill({
        json: {
          providers: [
            {
              id: 'provider',
              name: 'Provider metadata succeeded',
              kind: 'ollama',
              base_url: 'http://fixture.invalid',
              model_ids: ['fixture-model'],
              enabled: true,
              validated: true,
              discovered: true,
              revision: 1,
              secret_configured: false,
              checks: [],
            },
          ],
          provider_types: [],
          connections: [],
          checks: [],
        },
      });
    });
    await page.getByRole('button', { name: 'Configure koinon', exact: true }).click();
    await agentsStarted;
    await expect(page.getByRole('heading', { name: 'Agents', exact: true })).toBeVisible();
    const agentResponse = page.waitForResponse(
      (response) =>
        new URL(response.url()).pathname.endsWith('/agents') && response.status() === 503,
    );
    releaseAgents();
    await agentResponse;
    await metadataStarted;
    const metadataResponse = page.waitForResponse(
      (response) => response.url().endsWith('/configuration') && response.status() === 200,
    );
    releaseMetadata();
    await metadataResponse;
    await expect(page.getByRole('button', { name: 'Create an agent', exact: true })).toBeEnabled();
    await expect(page.locator('.settings-content > .error')).toContainText(
      'Agents are temporarily unavailable',
    );
    await expect(
      page.getByRole('heading', { name: 'No agents in this view', exact: true }),
    ).toHaveCount(0);
    await expect(page.getByRole('heading', { name: 'Agents', exact: true })).toBeVisible();
    const directory = resolve(process.cwd(), '.qualification-v23-settings-errors/captures');
    await mkdir(directory, { recursive: true });
    await page.screenshot({
      path: resolve(directory, `agents-error-after-provider-success-${width}.png`),
      animations: 'disabled',
    });
  });
