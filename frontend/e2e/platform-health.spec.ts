// Copyright 2026 Firefly Software Foundation
// SPDX-License-Identifier: Apache-2.0
import { test, expect, type Page } from '@playwright/test';
import { mkdir, writeFile } from 'node:fs/promises';
import { mockService, context } from './fixtures';
import type {
  HealthComponent,
  PlatformHealth,
  SystemInformation,
} from '@fireflyframework/koinon-sdk/platform-health';
const output = process.env['KOINON_HEALTH_SCREENSHOTS'];
async function capture(page: Page, name: string) {
  if (!output) return;
  await mkdir(output, { recursive: true });
  await page.screenshot({ path: `${output}/${name}.png`, animations: 'disabled' });
}
async function setup(
  page: Page,
  options: { spanish?: boolean; grant?: 'organization' | 'workspace' | 'viewer' } = {},
) {
  await mockService(page);
  const observed_at = new Date(Date.now() - 60000).toISOString(),
    expires_at = new Date(Date.now() + 300000).toISOString();
  const component = (
    id: HealthComponent['id'],
    patch: Partial<HealthComponent> = {},
  ): HealthComponent => ({
    id,
    configured: true,
    status: 'passed',
    basis: 'observed',
    freshness: 'current',
    observed_at,
    expires_at,
    reason: 'DATABASE_OK',
    remediation: 'none',
    coverage: 'complete',
    ...patch,
  });
  const unobserved: Partial<HealthComponent> = {
    status: 'unknown',
    basis: 'configuration',
    observed_at: null,
    expires_at: null,
    coverage: 'unavailable',
  };
  const health: PlatformHealth = {
    tenant_id: 'tenant-one',
    checked_at: new Date().toISOString(),
    components: [
      component('database-primary'),
      component('database-documents'),
      component('database-documents-control', {
        status: 'failed',
        reason: 'RUNTIME_ROLE_UNSAFE',
        remediation: 'review_configuration',
      }),
      component('database-structured'),
      component('database-structured-control', {
        ...unobserved,
        reason: 'RUNTIME_ROLE_UNVERIFIED',
      }),
      component('storage-documents', { ...unobserved, reason: 'STORAGE_NOT_PROBED' }),
      component('storage-structured', { ...unobserved, reason: 'STORAGE_NOT_PROBED' }),
      component('indexes-documents', {
        status: 'failed',
        reason: 'INDEXES_INCOMPLETE',
        remediation: 'review_indexes',
        coverage: 'partial',
        counts: { observed_total: 8, observed_ready: 6, observed_pending: 1, observed_failed: 1 },
      }),
      component('indexes-structured', {
        ...unobserved,
        reason: 'INDEXES_NOT_PROBED',
        remediation: 'review_indexes',
      }),
      component('ingestion-documents', {
        status: 'failed',
        reason: 'INGESTION_FAILURES',
        remediation: 'review_ingestion',
        coverage: 'partial',
        counts: {
          observed_total: 9,
          observed_ready: 5,
          observed_pending: 2,
          observed_running: 1,
          observed_failed: 1,
        },
      }),
      component('ingestion-structured', {
        reason: 'INGESTION_STATE_OBSERVED',
        counts: { observed_total: 8, observed_ready: 8 },
      }),
      component('model-configuration', {
        ...unobserved,
        reason: 'MODEL_CONFIGURATION_PRESENT',
        remediation: 'review_configuration',
      }),
      component('communications', {
        ...unobserved,
        reason: 'COMMUNICATIONS_CONFIGURED',
        remediation: 'review_communications',
      }),
      component('workers', {
        ...unobserved,
        reason: 'WORKER_LIVENESS_UNKNOWN',
        remediation: 'review_worker',
      }),
    ],
  };
  const info: SystemInformation = {
    tenant_id: 'tenant-one',
    checked_at: health.checked_at,
    product: 'koinon',
    components: [
      { id: 'backend', distribution: 'firefly-koinon', version: '26.11.3', available: true },
      {
        id: 'documents',
        distribution: 'firefly-koinon-documents',
        version: '26.11.3',
        available: true,
      },
      {
        id: 'structured',
        distribution: 'firefly-koinon-structured',
        version: '26.11.3',
        available: true,
      },
      {
        id: 'storage',
        distribution: 'firefly-koinon-storage',
        version: '26.11.3',
        available: true,
      },
      { id: 'python-sdk', distribution: 'firefly-koinon-sdk', version: '26.11.3', available: true },
      { id: 'framework', distribution: 'pyfly', version: '26.10.32', available: true },
    ],
    serving_role: 'api',
    capabilities: {
      knowledge_enabled: true,
      mcp_enabled: true,
      communications_enabled: true,
      scheduled_consumers_enabled: false,
    },
    limits: [
      { id: 'api_capacity', value: 16, unit: 'operations', scope: 'process' },
      { id: 'worker_concurrency', value: 2, unit: 'operations', scope: 'process' },
      { id: 'max_index_workspaces', value: 25, unit: 'workspaces', scope: 'process' },
      { id: 'ingestion_raw_max_bytes', value: 268435456, unit: 'bytes', scope: 'file' },
      { id: 'ingestion_scratch_max_bytes', value: 1073741824, unit: 'bytes', scope: 'process' },
    ],
    license_expression: 'Apache-2.0',
    copyright: 'Copyright 2026 Firefly Software Foundation',
    artifacts: [
      {
        component: 'backend',
        kind: 'license',
        present: true,
        sha256: '1'.repeat(64),
        content_type: 'text/plain',
      },
      {
        component: 'backend',
        kind: 'notice',
        present: true,
        sha256: '2'.repeat(64),
        content_type: 'text/plain',
      },
      { component: 'backend', kind: 'sbom', present: null },
    ],
  };
  const requests: { method: string; path: string }[] = [];
  let denied = false;
  await page.route('**/bff/api/v1/**', (route) => {
    const path = new URL(route.request().url()).pathname.replace('/bff/api/v1', '');
    if (path === '/context')
      return route.fulfill({
        json: {
          ...context,
          memberships: [
            {
              id: 'health-admin',
              subject: context.subject,
              tenant_id: 'tenant-one',
              workspace_id: options.grant === 'workspace' ? 'workspace-one' : null,
              role: options.grant === 'viewer' ? 'viewer' : 'admin',
              active: true,
            },
          ],
        },
      });
    if (options.spanish && path === '/profile')
      return route.fulfill({
        json: {
          subject: context.subject,
          display_name: 'Alex Rivera',
          locale: 'es-ES',
          time_zone: 'Europe/Madrid',
          response_language: 'es',
        },
      });
    if (!path.includes('/platform/')) return route.fallback();
    requests.push({ method: route.request().method(), path });
    if (denied)
      return route.fulfill({
        status: 403,
        json: { code: 'DENIED', message: 'postgresql://secret@internal.example/private' },
      });
    return route.fulfill({ json: path.endsWith('/health') ? health : info });
  });
  return {
    requests,
    deny: () => {
      denied = true;
    },
  };
}
async function open(page: Page, width: number, spanish = false) {
  await page.goto('/settings');
  if (width <= 760)
    await page
      .getByLabel(spanish ? 'Sección de configuración' : 'Settings section', { exact: true })
      .selectOption('health');
  else
    await page
      .getByRole('button', {
        name: spanish ? 'Salud de la plataforma' : 'Platform health',
        exact: true,
      })
      .click();
  const panel = page.locator('ffk-platform-health-panel');
  await expect(
    panel.getByRole('heading', {
      name: spanish ? 'Salud de la plataforma' : 'Platform health',
      exact: true,
    }),
  ).toBeVisible();
  await expect(panel.locator('.service-row')).toHaveCount(14);
  return panel;
}
for (const width of [1440, 1200, 390])
  for (const dark of [false, true])
    test(`platform health and system information ${width}px ${dark ? 'dark' : 'light'}`, async ({
      page,
    }) => {
      await page.setViewportSize({ width, height: 960 });
      await page.addInitScript(
        (value) => localStorage.setItem('koinon-theme', value),
        dark ? 'dark' : 'light',
      );
      const service = await setup(page),
        panel = await open(page, width);
      await expect(panel.getByText('All systems operational', { exact: true })).toHaveCount(0);
      await panel.getByLabel('Show checks', { exact: true }).selectOption('failed');
      await expect(panel.locator('.service-row')).toHaveCount(3);
      await panel.locator('.service-row').filter({ hasText: 'Document ingestion' }).click();
      await expect(panel.locator('#health-detail')).toContainText('Partial coverage');
      await expect(panel.locator('#health-detail')).toContainText('not organization totals');
      expect(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth)).toBe(
        true,
      );
      const content = (await panel.boundingBox())!;
      expect(content.x).toBeGreaterThanOrEqual(0);
      expect(content.x + content.width).toBeLessThanOrEqual(width);
      if (width > 760) {
        const rail = (await page
          .getByRole('navigation', { name: 'Settings sections' })
          .boundingBox())!;
        expect(rail.width).toBeLessThan(300);
        expect(content.x).toBeGreaterThan(rail.x + rail.width);
      }
      await panel.locator('.heading').scrollIntoViewIfNeeded();
      await capture(page, `health-${width}-${dark ? 'dark' : 'light'}`);
      let focusedActionBounds = content;
      if (width === 390) {
        const action = panel.getByRole('button', { name: 'Review settings', exact: true });
        await action.focus();
        await action.scrollIntoViewIfNeeded();
        await expect(action).toBeFocused();
        await expect(action).toBeInViewport({ ratio: 1 });
        focusedActionBounds = (await action.boundingBox())!;
        const footer = (await page.locator('ffk-shell footer').boundingBox())!;
        expect(focusedActionBounds.y + focusedActionBounds.height).toBeLessThanOrEqual(footer.y);
        expect(focusedActionBounds.y).toBeGreaterThanOrEqual(
          (await page.locator('ffk-settings-page .settings-content').boundingBox())!.y,
        );
        await capture(page, `health-detail-${width}-${dark ? 'dark' : 'light'}`);
      }
      await panel.getByRole('tab', { name: 'System information', exact: true }).click();
      await expect(panel.getByText('26.10.32', { exact: true })).toBeVisible();
      await expect(panel.getByText('Verified build revision', { exact: true })).toBeVisible();
      await expect(panel.locator('.artifacts')).toContainText('Unknown');
      await expect(panel.locator('.artifacts a')).toHaveCount(0);
      await panel.locator('.heading').scrollIntoViewIfNeeded();
      await capture(page, `system-information-${width}-${dark ? 'dark' : 'light'}`);
      if (width === 390) {
        const lastLimit = panel
          .locator('.information-section')
          .filter({ has: page.getByRole('heading', { name: 'Configured limits', exact: true }) })
          .locator('dd')
          .last();
        await lastLimit.scrollIntoViewIfNeeded();
        const limitBounds = (await lastLimit.boundingBox())!;
        const scrollViewport = (await page
          .locator('ffk-settings-page .settings-content')
          .boundingBox())!;
        expect(limitBounds.y).toBeGreaterThanOrEqual(scrollViewport.y);
        const lastArtifact = panel.locator('.artifacts article').last();
        await lastArtifact.scrollIntoViewIfNeeded();
        await expect(lastArtifact).toBeInViewport({ ratio: 1 });
        const artifactBounds = (await lastArtifact.boundingBox())!;
        const footer = (await page.locator('ffk-shell footer').boundingBox())!;
        expect(limitBounds.y + limitBounds.height).toBeLessThanOrEqual(footer.y);
        expect(artifactBounds.y + artifactBounds.height).toBeLessThanOrEqual(footer.y);
        expect(artifactBounds.y).toBeGreaterThanOrEqual(scrollViewport.y);
        await capture(page, `system-artifacts-${width}-${dark ? 'dark' : 'light'}`);
        if (output)
          await writeFile(
            `${output}/footer-geometry-${width}-${dark ? 'dark' : 'light'}.json`,
            JSON.stringify({ focusedActionBounds, limitBounds, artifactBounds, footer }, null, 2),
          );
      }
      expect(service.requests.every((request) => request.method === 'GET')).toBe(true);
      expect(
        service.requests.every((request) =>
          /\/platform\/(health|system-information)$/.test(request.path),
        ),
      ).toBe(true);
    });
test('Spanish health remains readable on mobile with localized reasons', async ({ page }) => {
  await page.setViewportSize({ width: 390, height: 960 });
  await setup(page, { spanish: true });
  const panel = await open(page, 390, true);
  await panel.getByLabel('Mostrar comprobaciones').selectOption('unknown');
  await panel
    .locator('.service-row')
    .filter({ hasText: 'Configuración de modelos de conocimiento' })
    .click();
  await expect(panel.locator('#health-detail')).toContainText(
    'Aquí no se han probado la generación ni la conectividad.',
  );
  await panel.locator('#health-detail').scrollIntoViewIfNeeded();
  await capture(page, 'health-detail-390-spanish');
});
for (const grant of ['workspace', 'viewer'] as const)
  test(`does not request organization health for ${grant} grants`, async ({ page }) => {
    const service = await setup(page, { grant });
    await page.goto('/settings');
    await expect(page.locator('ffk-settings-page')).toBeVisible();
    await expect(page.getByRole('button', { name: 'Platform health', exact: true })).toHaveCount(0);
    await expect(page.locator('ffk-platform-health-panel')).toHaveCount(0);
    expect(service.requests).toEqual([]);
  });
test('access denial clears reports and never renders the raw diagnostic', async ({ page }) => {
  const service = await setup(page),
    panel = await open(page, 1440);
  service.deny();
  await panel.getByRole('button', { name: 'Refresh observations', exact: true }).click();
  await expect(panel.getByRole('alert')).toContainText(
    'Current organization administrator access is required.',
  );
  await expect(panel.locator('.service-row')).toHaveCount(0);
  await expect(panel).not.toContainText('secret');
  await expect(panel).not.toContainText('internal.example');
});
test('health report tabs support keyboard navigation and scope changes remove old reports', async ({
  page,
}) => {
  await setup(page);
  const panel = await open(page, 1440);
  const tab = panel.getByRole('tab', { name: 'Health', exact: true });
  await tab.focus();
  await page.keyboard.press('ArrowRight');
  await expect(panel.getByRole('tab', { name: 'System information', exact: true })).toBeFocused();
  await expect(panel.getByRole('tab', { name: 'System information', exact: true })).toHaveAttribute(
    'aria-selected',
    'true',
  );
  await page
    .getByRole('combobox', { name: 'Organization', exact: true })
    .selectOption('tenant-two');
  await expect(page.locator('ffk-platform-health-panel')).toHaveCount(0);
});
