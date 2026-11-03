// Copyright 2026 Firefly Software Foundation
// SPDX-License-Identifier: Apache-2.0
// Controlled observation fixtures; not deployed worker or provider qualification.
import { test, expect } from '@playwright/test';
import { mkdir } from 'node:fs/promises';
import { context, entry, mockService, setDarkAppearance } from './fixtures';

for (const width of [1440, 390]) test(`automatically updates Library and an initially empty Uploads view at ${width}px`, async ({ page }) => {
  await page.setViewportSize({ width, height: 1000 });
  await page.clock.install();
  const service = await mockService(page);
  service.rows.splice(4);
  const names = ['Operating policy.pdf', 'Operating guide.docx', 'Service activity.xlsx', 'Quarterly review.pptx'];
  names.forEach((name, i) => service.rows.push(entry('status-' + i, i === 2 ? 'dataset' : 'document', name, 'source-one')));
  let processing = true, unavailable = false, listReady = false, availabilityCalls = 0, listCalls = 0;
  const writes: string[] = [];
  await page.route('**/bff/api/v1/**', route => {
    const request = route.request(), path = new URL(request.url()).pathname;
    if (path.endsWith('/context')) return route.fulfill({ json: { ...context, memberships: [{ id: 'grant', subject: context.subject, tenant_id: 'tenant-one', workspace_id: null, role: 'admin', active: true }] } });
    if (path.endsWith('/catalog/availability')) {
      availabilityCalls++;
      if (unavailable) return route.fulfill({ status: 503, json: { code: 'UNAVAILABLE', message: 'Temporary failure' } });
      const ids = request.postDataJSON().asset_ids as string[];
      return route.fulfill({ json: { observed_at: new Date().toISOString(), items: Object.fromEntries(ids.map(id => [id, {
        phase: id === 'status-1' && processing ? 'processing' : id === 'status-2' ? 'failed' : id === 'status-3' ? 'reconciliation_required' : 'complete',
        read: { state: 'ready', reason: 'RECORDED' },
        search: { state: ['status-0', 'status-1'].includes(id) && (id !== 'status-1' || !processing) ? 'ready' : 'pending', reason: 'OBSERVED' },
        query: { state: 'unknown', reason: 'NOT_CHECKED' }, revision: {},
      }])) } });
    }
    if (path.endsWith('/sources/batches')) {
      if (request.method() !== 'GET') { writes.push(path); return route.abort(); }
      listCalls++;
      const items = listReady ? ['succeeded', 'running', 'failed', 'reconciling'].map((status, i) => ({
        id: 'status-batch-' + i, tenant_id: 'tenant-one', status, revision: 1,
        destination: { workspace_id: 'workspace-one', project_id: 'project-one', parent_id: 'collection-one' },
        total_items: 1, total_bytes: 32768, counts: { [status]: 1 }, cancellation_requested: false,
        created_at: `2026-11-03T0${i}:00:00Z`, expires_at: '2099-01-01T00:00:00Z',
      })) : [];
      return route.fulfill({ json: { items, page: 1, page_size: 25, pages: items.length ? 1 : 0, total: items.length } });
    }
    return route.fallback();
  });
  await page.goto('/library');
  for (const name of ['Research operations', 'Operations intelligence', 'Reference library'])
    await page.getByRole('button', { name, exact: true }).dblclick();
  const indicators = page.locator('ffk-resource-list ffk-knowledge-availability');
  await expect(indicators).toHaveCount(4);
  for (const tone of ['ready', 'processing', 'error', 'attention'])
    await expect(indicators.locator('ffk-badge span.' + tone)).toHaveCount(1);
  const directory = process.env['KOINON_STATUS_SCREENSHOTS'];
  if (directory) { await mkdir(directory, { recursive: true }); await page.screenshot({ path: `${directory}/library-status-${width}.png`, animations: 'disabled' }); }
  if (width === 390 && directory) {
    await indicators.last().scrollIntoViewIfNeeded();
    await page.screenshot({ path: `${directory}/library-status-scrolled-${width}.png`, animations: 'disabled' });
  }
  for (let i = 0; i < 14; ++i) {
    const response = page.waitForResponse(url => url.url().endsWith('/catalog/availability'));
    await page.clock.runFor(5000);
    await (await response).finished();
    await page.evaluate(() => Promise.resolve());
  }
  expect(availabilityCalls).toBeGreaterThan(12);
  processing = false;
  await page.clock.runFor(5000);
  await expect(indicators.locator('ffk-badge span.ready')).toHaveCount(2);
  unavailable = true;
  await page.clock.runFor(5000);
  await expect(indicators.getByText('Status temporarily unavailable', { exact: true })).toHaveCount(4);
  await expect(indicators.locator('ffk-badge span.ready')).toHaveCount(0);
  unavailable = false;
  await page.clock.runFor(30000);
  await expect(indicators.locator('ffk-badge span.ready')).toHaveCount(2);
  if (width === 1440) {
    await setDarkAppearance(page);
    await expect(page.locator('.brand img')).toHaveAttribute('src', /reversed\.svg$/);
    await page.locator('.brand img').evaluate(async image => {
      await (image as HTMLImageElement).decode();
      await document.fonts.ready;
    });
    await page.clock.runFor(300);
    if (directory) await page.screenshot({ path: `${directory}/library-status-dark-${width}.png`, animations: 'disabled' });
  }
  await page.getByRole('button', { name: 'Uploads', exact: true }).click();
  const panel = page.locator('ffk-library-retained-uploads-panel');
  await expect(panel.getByText('No uploads yet', { exact: true })).toBeVisible();
  await expect(panel.getByRole('button', { name: 'Refresh uploads', exact: true })).toHaveCount(0);
  listReady = true;
  await page.clock.runFor(30000);
  await expect(panel.locator(width === 390 ? '.mobile-list' : '.table-wrap').getByText('Processing completed', { exact: true }).first()).toBeVisible();
  expect(listCalls).toBeGreaterThan(1);
  for (const tone of ['ready', 'processing', 'error', 'attention'])
    await expect(panel.locator('ffk-badge span.' + tone).first()).toBeAttached();
  if (directory) await page.screenshot({ path: `${directory}/uploads-status-${width}.png`, animations: 'disabled' });
  expect(writes).toEqual([]);
});
