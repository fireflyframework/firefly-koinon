// Copyright 2026 Firefly Software Foundation
// SPDX-License-Identifier: Apache-2.0
// Controlled transport/state fixtures; this does not qualify Office parsing or a deployed worker.
import { test, expect, type Page } from '@playwright/test';
import { createHash } from 'node:crypto';
import { mkdir } from 'node:fs/promises';
import { resolve } from 'node:path';
import type { FileBatchCreate, FileBatchItemView } from '@fireflyframework/koinon-sdk';
import { entry, mockService } from './fixtures';
test.use({ trace: 'off' });
async function fixture(page: Page, options: { configured?: boolean; loseSubmit?: boolean } = {}) {
  const service = await mockService(page, {
    queuedStorageConfigured: options.configured !== false,
  });
  let status = 'staging',
    revision = 1,
    live = false;
  let items: FileBatchItemView[] = [];
  let input: FileBatchCreate | null = null;
  const calls: { method: string; path: string; body: unknown; headers: Record<string, string> }[] =
    [];
  let transferred = 0;
  const batch = () => ({
    id: 'queue-batch',
    tenant_id: 'tenant-one',
    destination: input!.destination,
    status,
    revision,
    total_items: items.length,
    total_bytes: items.reduce((sum, item) => sum + item.size_bytes, 0),
    counts: Object.fromEntries(
      [...new Set(items.map((item) => item.status))].map((value) => [
        value,
        items.filter((item) => item.status === value).length,
      ]),
    ),
    cancellation_requested: status === 'cancelled',
    created_at: '2026-11-01T08:00:00Z',
    expires_at: '2026-11-02T08:00:00Z',
  });
  await page.route('**/bff/api/v1/tenants/*/sources/batches**', async (route) => {
    const request = route.request(),
      path = new URL(request.url()).pathname,
      method = request.method();
    const body = method === 'POST' ? request.postDataJSON() : null;
    calls.push({ method, path, body, headers: request.headers() });
    const json = (value: unknown, code = 200) => route.fulfill({ status: code, json: value });
    if (method === 'POST' && path.endsWith('/batches')) {
      input = body as FileBatchCreate;
      items = input.items.map((item, index) => ({
        ...item,
        id: 'queued-item-' + index,
        status: 'awaiting_upload',
        source_id: 'queued-source-' + index,
        asset_id: 'queued-asset-' + index,
        job_id: null,
      }));
      for (const item of items) {
        service.rows.push(
          entry(item.source_id, 'source', item.filename, input.destination.parent_id, {
            status: 'pending',
          }),
          entry(item.asset_id, item.mode, item.filename, item.source_id, { status: 'pending' }),
        );
      }
      return json(batch(), 201);
    }
    if (method === 'GET' && path.endsWith('/items'))
      return json({ items, total: items.length, page: 1, page_size: 50, pages: 1 });
    if (method === 'PUT' && path.endsWith('/content')) {
      const item = items.find((value) => path.includes('/' + value.id + '/'))!;
      const bytes = request.postDataBuffer()!;
      expect(bytes.length).toBe(item.size_bytes);
      expect(createHash('sha256').update(bytes).digest('hex')).toBe(item.sha256);
      expect(request.headers()['content-type']).toBe('application/octet-stream');
      transferred += bytes.length;
      item.status = 'staged';
      revision++;
      return json({
        receipt_id: 'verified-original',
        batch_id: 'queue-batch',
        item_id: item.id,
        status: 'staged',
        size_bytes: item.size_bytes,
        sha256: item.sha256,
      });
    }
    if (method === 'POST' && path.endsWith('/submit')) {
      expect(body).toEqual({ expected_revision: revision });
      status = 'queued';
      revision++;
      for (const item of items) {
        item.status = 'queued';
        item.job_id = 'native-job';
      }
      if (options.loseSubmit) return route.abort('failed');
      return json(batch());
    }
    if (method === 'POST' && path.endsWith('/cancel')) {
      expect(body).toEqual({ expected_revision: revision });
      status = 'cancelled';
      revision++;
      for (const item of items) item.status = 'cancelled';
      return json(batch());
    }
    if (method === 'GET' && path.endsWith('/queue-batch')) return json(batch());
    return json({ code: 'UNEXPECTED_QUEUE_FIXTURE' }, 404);
  });
  await page.route('**/catalog/availability', (route) => {
    const ids = (route.request().postDataJSON() as { asset_ids: string[] }).asset_ids;
    return route.fulfill({
      json: {
        observed_at: '2026-11-01T09:00:00Z',
        items: Object.fromEntries(
          ids.map((id) => [
            id,
            items.some((item) => item.asset_id === id)
              ? {
                  phase:
                    status === 'queued'
                      ? 'queued'
                      : status === 'running'
                        ? live
                          ? 'processing'
                          : 'unknown'
                        : status === 'succeeded'
                          ? 'complete'
                          : 'unknown',
                  read: {
                    state: status === 'succeeded' ? 'ready' : 'unknown',
                    reason: 'CURRENT_TEXT_RECORDED',
                  },
                  search: { state: 'pending', reason: 'ACTIVE_INDEX_INCOMPLETE' },
                  query: { state: 'not_applicable', reason: 'DOCUMENT' },
                  revision:
                    status === 'succeeded'
                      ? {
                          source_version_id: 'recorded-version',
                          extraction_id: 'recorded-extraction',
                        }
                      : {},
                }
              : { phase: 'unknown' },
          ]),
        ),
      },
    });
  });
  return {
    service,
    calls,
    get transferred() {
      return transferred;
    },
    get input() {
      return input;
    },
    advance(value: 'running' | 'succeeded', verified = false) {
      status = value;
      live = verified;
      for (const item of items) item.status = value;
      revision++;
    },
  };
}
async function open(page: Page) {
  await page.goto('/library');
  for (const name of ['Research operations', 'Operations intelligence', 'Reference library'])
    await page.getByRole('button', { name, exact: true }).click();
  await page.getByRole('button', { name: 'Add knowledge', exact: true }).click();
  const dialog = page.getByRole('dialog');
  await dialog.getByRole('button', { name: /Upload files/ }).click();
  await expect(dialog.locator('ffk-library-upload-panel')).toBeVisible();
  return dialog;
}
async function capture(page: Page, name: string) {
  const directory = process.env['KOINON_QUEUE_CAPTURES'];
  if (!directory) return;
  await mkdir(directory, { recursive: true });
  await page.evaluate(() => document.fonts.ready);
  await page.screenshot({ path: resolve(directory, name + '.png'), animations: 'disabled' });
}
for (const width of [1440, 390]) {
  test(`ordinary upload is durable and processing requires current native evidence at ${width}px`, async ({
    page,
  }) => {
    await page.setViewportSize({ width, height: width === 390 ? 844 : 1000 });
    const state = await fixture(page),
      dialog = await open(page);
    await expect(dialog.getByText('Destination folder', { exact: true })).toHaveCount(1);
    await expect(dialog.getByRole('button', { name: 'Choose folder', exact: true })).toHaveCount(0);
    await capture(page, 'queue-destination-' + width);
    await dialog.getByLabel('Choose files').setInputFiles({
      name: 'policy.txt',
      mimeType: 'text/plain',
      buffer: Buffer.from('A controlled original for worker extraction.'),
    });
    await dialog.getByRole('button', { name: 'Upload 1 file', exact: true }).click();
    await expect(dialog.getByText('Queued', { exact: true }).first()).toBeVisible();
    expect(state.input?.processing_policy).toBe('extract_only_v1');
    expect(state.service.writes.some((call) => call.path.endsWith('/sources/upload'))).toBe(false);
    expect(state.calls.find((call) => call.method === 'POST')?.headers['x-xsrf-token']).toBe(
      'synthetic-csrf+token',
    );
    expect(state.transferred).toBeGreaterThan(0);
    await capture(page, 'queue-observed-' + width);
    state.advance('running');
    await dialog.getByRole('button', { name: 'Check status', exact: true }).click();
    await expect(dialog.getByText('Worker state not verified', { exact: true })).toBeVisible();
    state.advance('running', true);
    await dialog.getByRole('button', { name: 'Check status', exact: true }).click();
    await expect(dialog.getByText('Processing', { exact: true }).first()).toBeVisible();
    state.advance('succeeded');
    await dialog.getByRole('button', { name: 'Check status', exact: true }).click();
    await expect(dialog.getByText('Extraction complete', { exact: true }).first()).toBeVisible();
    await expect(
      dialog.getByText('Current availability: Text available; search pending', { exact: true }),
    ).toBeVisible();
    await expect(dialog.getByText('Searchable', { exact: true })).toHaveCount(0);
    await capture(page, 'queue-extracted-' + width);
    expect(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth)).toBe(
      true,
    );
  });
  test(`unknown submission is inspected without a duplicate mutation and cancellation uses the native batch at ${width}px`, async ({
    page,
  }) => {
    await page.setViewportSize({ width, height: width === 390 ? 844 : 1000 });
    const state = await fixture(page, { loseSubmit: true }),
      dialog = await open(page);
    await dialog.getByLabel('Choose files').setInputFiles({
      name: 'policy.txt',
      mimeType: 'text/plain',
      buffer: Buffer.from('Controlled original.'),
    });
    await dialog.getByRole('button', { name: 'Upload 1 file', exact: true }).click();
    await expect(
      dialog.getByRole('heading', { name: 'Upload outcome not confirmed', exact: true }),
    ).toBeVisible();
    await dialog.getByRole('button', { name: 'Check status', exact: true }).click();
    await expect(dialog.getByText('Queued', { exact: true }).first()).toBeVisible();
    expect(state.calls.filter((call) => call.path.endsWith('/submit'))).toHaveLength(1);
    expect(state.calls.filter((call) => call.method === 'PUT')).toHaveLength(1);
    await dialog.getByRole('button', { name: 'Request cancellation', exact: true }).click();
    await expect(dialog.getByText('Stopped', { exact: true }).first()).toBeVisible();
    expect(state.calls.filter((call) => call.path.endsWith('/cancel'))).toHaveLength(1);
    expect(state.service.writes.some((call) => call.path.includes('/jobs/'))).toBe(false);
  });
}
test('a real generated original larger than 32MiB uses raw queued transfer and never synchronous upload', async ({
  page,
}) => {
  const state = await fixture(page),
    dialog = await open(page);
  const bytes = Buffer.alloc(33 * 1024 * 1024, 65);
  await dialog
    .getByLabel('Choose files')
    .setInputFiles({ name: 'large-transfer.txt', mimeType: 'text/plain', buffer: bytes });
  await dialog.getByRole('button', { name: 'Upload 1 file', exact: true }).click();
  await expect(dialog.getByText('Queued', { exact: true }).first()).toBeVisible();
  expect(state.transferred).toBe(bytes.length);
  expect(state.service.writes.some((call) => call.path.endsWith('/sources/upload'))).toBe(false);
});
test('large originals are not sent when queued storage is unavailable', async ({ page }) => {
  const state = await fixture(page, { configured: false }),
    dialog = await open(page);
  await dialog.getByLabel('Choose files').setInputFiles({
    name: 'large-transfer.txt',
    mimeType: 'text/plain',
    buffer: Buffer.alloc(33 * 1024 * 1024, 65),
  });
  await dialog.getByRole('button', { name: 'Upload 1 file', exact: true }).click();
  await expect(dialog.getByRole('alert')).toContainText(
    'Large files need configured queued storage',
  );
  expect(state.transferred).toBe(0);
  expect(state.service.writes.some((call) => call.path.endsWith('/sources/upload'))).toBe(false);
  expect(state.calls.some((call) => call.method === 'POST' || call.method === 'PUT')).toBe(false);
});
