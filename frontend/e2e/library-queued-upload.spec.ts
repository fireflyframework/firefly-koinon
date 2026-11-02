// Copyright 2026 Firefly Software Foundation
// SPDX-License-Identifier: Apache-2.0
// Controlled transport/state fixtures; this does not qualify Office parsing or a deployed worker.
import { test, expect, type Page } from '@playwright/test';
import { createHash } from 'node:crypto';
import { mkdir } from 'node:fs/promises';
import { resolve } from 'node:path';
import type {
  FileBatchCapabilities,
  FileBatchCreate,
  FileBatchItemView,
} from '@fireflyframework/koinon-sdk';
import { context, entry, mockService } from './fixtures';
import { officeFile } from './office-fixtures';
import officeFormats from './office-format-capabilities.json';
test.use({ trace: 'off' });
async function fixture(page: Page, options: { configured?: boolean; loseSubmit?: boolean } = {}) {
  const service = await mockService(page, {
    queuedStorageConfigured: options.configured !== false,
  });
  await page.route('**/source-batch-capabilities*', (route) =>
    route.fulfill({
      json: {
        configured: options.configured !== false,
        modes: ['document', 'dataset'],
        formats: officeFormats as FileBatchCapabilities['formats'],
        max_active_batches_per_subject: 3,
        max_files: 100,
        max_file_bytes: 134217728,
        max_batch_bytes: 536870912,
        synchronous_max_file_bytes: 33554432,
      } satisfies FileBatchCapabilities,
    }),
  );
  await page.route('**/bff/api/v1/context', (route) =>
    route.fulfill({
      json: {
        ...context,
        memberships: [
          {
            id: 'upload-grant',
            subject: context.subject,
            tenant_id: 'tenant-one',
            workspace_id: null,
            role: 'admin',
            active: true,
          },
        ],
      },
    }),
  );
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
    if (method === 'GET' && path.endsWith('/batches'))
      return json({
        items: input ? [batch()] : [],
        total: input ? 1 : 0,
        page: 1,
        page_size: 25,
        pages: 1,
      });
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
    await expect(dialog.getByText('Worker state not verified', { exact: true })).toBeVisible();
    state.advance('running', true);
    await expect(dialog.getByText('Processing', { exact: true }).first()).toBeVisible();
    state.advance('succeeded');
    await expect(dialog.getByText('Extraction complete', { exact: true }).first()).toBeVisible();
    await expect(dialog.getByText('Text available; search pending', { exact: true })).toBeVisible();
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
    await expect(dialog.getByText('Queued', { exact: true }).first()).toBeVisible({
      timeout: 12000,
    });
    await expect(
      dialog.getByRole('button', { name: 'Try updating status', exact: true }),
    ).toHaveCount(0);
    expect(state.calls.filter((call) => call.path.endsWith('/submit'))).toHaveLength(1);
    expect(state.calls.filter((call) => call.method === 'PUT')).toHaveLength(1);
    await dialog.getByText('Upload details', { exact: true }).click();
    await dialog.getByRole('button', { name: 'Request cancellation', exact: true }).click();
    await expect(dialog.getByText('Cancelled', { exact: true }).first()).toBeVisible();
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
  await expect(dialog.getByRole('button', { name: 'Upload 1 file', exact: true })).toBeDisabled();
  await expect(dialog).toContainText('This file exceeds the maximum file size.');
  await expect(dialog).toContainText('Maximum per file: 32 MiB.');
  expect(state.transferred).toBe(0);
  expect(state.service.writes.some((call) => call.path.endsWith('/sources/upload'))).toBe(false);
  expect(state.calls.some((call) => call.method === 'POST' || call.method === 'PUT')).toBe(false);
});
test('observed larger server limits display the same effective bounds enforced by the upload coordinator', async ({
  page,
}) => {
  const state = await fixture(page);
  await page.route('**/source-batch-capabilities*', (route) =>
    route.fulfill({
      json: {
        configured: true,
        modes: ['dataset'],
        max_files: 100,
        max_file_bytes: 536870912,
        max_batch_bytes: 1073741824,
        synchronous_max_file_bytes: 134217728,
      },
    }),
  );
  const dialog = await open(page);
  await dialog
    .getByLabel('Choose files')
    .setInputFiles({ name: 'policy.txt', mimeType: 'text/plain', buffer: Buffer.from('bounded') });
  await expect(dialog.getByRole('button', { name: 'Upload 1 file', exact: true })).toBeDisabled();
  await expect(dialog.getByRole('alert')).toContainText(
    'Remove files that cannot be uploaded before continuing.',
  );
  await expect(dialog).toContainText('Maximum per file: 128 MiB.');
  await expect(dialog).toContainText('Maximum batch: 512 MiB.');
  expect(state.transferred).toBe(0);
});

for (const width of [1440, 390]) {
  test(`upload capabilities and individual file rejection are visible before transfer at ${width}px`, async ({
    page,
  }) => {
    const height = width < 600 ? 844 : 1000;
    await page.setViewportSize({ width, height });
    const state = await fixture(page);
    await page.route('**/source-batch-capabilities*', (route) =>
      route.fulfill({
        json: {
          configured: true,
          modes: ['document', 'dataset'],
          max_files: 3,
          max_file_bytes: 1048576,
          max_batch_bytes: 2097152,
          synchronous_max_file_bytes: 1048576,
          formats: [
            { mode: 'document', extensions: ['.txt', '.pdf'], available: true },
            { mode: 'dataset', extensions: ['.csv'], available: true },
          ],
        },
      }),
    );
    const dialog = await open(page);
    await expect(dialog.locator('ffk-file-formats')).toContainText('PDF');
    await expect(dialog.locator('ffk-file-formats')).toContainText('Text');
    await expect(dialog).toContainText('Maximum per file: 1 MiB.');
    await expect(dialog).toContainText('Maximum files: 3.');
    await dialog.getByLabel('Choose files').setInputFiles([
      { name: 'Policy.txt', mimeType: 'text/plain', buffer: Buffer.from('policy') },
      { name: 'Rejected.exe', mimeType: 'application/octet-stream', buffer: Buffer.from('binary') },
    ]);
    await expect(dialog).toContainText('6 bytes');
    await expect(dialog).toContainText('This file type is not supported for the selected use.');
    await expect(
      dialog.getByRole('button', { name: 'Upload 2 files', exact: true }),
    ).toBeDisabled();
    const rows = dialog.locator('.upload-preview > div');
    const firstRemove = await rows.nth(0).getByRole('button').boundingBox();
    const secondRemove = await rows.nth(1).getByRole('button').boundingBox();
    expect(Math.abs(firstRemove!.x - secondRemove!.x)).toBeLessThan(2);
    const name = await rows.nth(0).getByText('Policy.txt', { exact: true }).boundingBox();
    const size = await rows.nth(0).locator('.file-size').boundingBox();
    const labelBottom = width < 600 ? size!.y + size!.height : name!.y + name!.height;
    expect(
      Math.abs(firstRemove!.y + firstRemove!.height / 2 - (name!.y + labelBottom) / 2),
    ).toBeLessThan(2);
    if (width < 600) expect((await rows.nth(0).boundingBox())!.height).toBeLessThan(100);
    await capture(page, 'formats-rejected-' + width);
    const submit = dialog.getByRole('button', { name: 'Upload 2 files', exact: true });
    await submit.scrollIntoViewIfNeeded();
    await expect(submit).toBeInViewport();
    const actions = await submit.boundingBox();
    expect(actions!.y + actions!.height).toBeLessThan(height);
    if (width < 600) await capture(page, 'formats-actions-' + width);
    await dialog.getByRole('button', { name: 'Remove file: Rejected.exe', exact: true }).click();
    await expect(dialog.getByRole('button', { name: 'Upload 1 file', exact: true })).toBeEnabled();
    expect(state.transferred).toBe(0);
  });
}

test('empty Library upload explains how to create a destination without a bootstrap folder', async ({
  page,
}) => {
  const service = await mockService(page);
  service.rows.splice(0);
  await page.goto('/library');
  await page.getByRole('button', { name: 'Add knowledge', exact: true }).click();
  await page.getByRole('button', { name: /Upload files/ }).click();
  const dialog = page.getByRole('dialog');
  await expect(dialog).toContainText(
    'Create a space, project and folder in Library, then return to upload.',
  );
  await expect(dialog.getByRole('button', { name: 'Upload files', exact: true })).toBeDisabled();
  await dialog.getByRole('button', { name: 'Back to Library', exact: true }).click();
  await expect(page.getByRole('button', { name: 'Create a space', exact: true })).toBeVisible();
  expect(service.writes).toHaveLength(0);
});

test('multiple originals show confirmed per-file transfer progress before queued processing', async ({
  page,
}) => {
  await fixture(page);
  let release!: () => void;
  const gate = new Promise<void>((resolve) => {
    release = resolve;
  });
  await page.route('**/queued-item-1/content', async (route) => {
    await gate;
    await route.fallback();
  });
  const dialog = await open(page);
  await dialog.getByLabel('Choose files').setInputFiles([
    { name: 'First.txt', mimeType: 'text/plain', buffer: Buffer.from('first') },
    { name: 'Second.txt', mimeType: 'text/plain', buffer: Buffer.from('second') },
  ]);
  await dialog.getByRole('button', { name: 'Upload 2 files', exact: true }).click();
  await expect(dialog.getByText('Original staged', { exact: true })).toBeVisible();
  await expect(dialog.getByText('Transferring original', { exact: true })).toBeVisible();
  await expect(dialog.getByRole('progressbar', { name: 'Bytes transferred' })).toHaveAttribute(
    'value',
    '5',
  );
  await expect(dialog.getByText('5 bytes', { exact: true })).toBeVisible();
  await expect(dialog.getByText('6 bytes', { exact: true })).toBeVisible();
  await capture(page, 'multi-file-transfer');
  release();
  await expect(dialog.getByText('Queued', { exact: true }).first()).toBeVisible();
  await expect(dialog.getByRole('progressbar', { name: 'Bytes transferred' })).toHaveAttribute(
    'value',
    '11',
  );
});

for (const width of [1440, 390]) {
  test(`Office files explain supported formats and automatic individual uses at ${width}px`, async ({
    page,
  }) => {
    await page.setViewportSize({ width, height: width < 600 ? 844 : 1000 });
    const state = await fixture(page),
      dialog = await open(page);
    const formats = dialog.locator('ffk-file-formats');
    for (const family of ['Word', 'Excel', 'PowerPoint', 'PDF'])
      await expect(formats.locator('.format-families')).toContainText(family);
    await expect(formats.locator('.format-families')).not.toContainText('.gz');
    await expect(dialog.getByLabel('Use these files as')).toHaveCount(0);
    await expect(dialog).toContainText(
      'Spreadsheets and CSV are prepared for questions about rows and totals.',
    );
    await capture(page, 'office-types-' + width);
    await formats.getByText('All file formats', { exact: true }).focus();
    await formats.getByText('All file formats', { exact: true }).press('Enter');
    await expect(formats).toContainText('Renaming the file does not convert it.');
    await formats.getByText('All file formats', { exact: true }).focus();
    await formats.getByText('All file formats', { exact: true }).press('Enter');
    const kinds = ['docx', 'pptx', 'xlsx', 'csv'] as const;
    const files = kinds.map((kind) => ({
      name: 'review.' + kind,
      mimeType: 'application/octet-stream',
      buffer: officeFile(kind),
    }));
    await dialog.getByLabel('Choose files').setInputFiles([
      ...files,
      {
        name: 'older.ppt',
        mimeType: 'application/vnd.ms-powerpoint',
        buffer: Buffer.from([0xd0, 0xcf, 0x11, 0xe0, 0xa1, 0xb1, 0x1a, 0xe1]),
      },
    ]);
    await expect(dialog).toContainText(
      'Open this .ppt file in PowerPoint and use Save As .pptx, then upload the converted file.',
    );
    await dialog.getByRole('button', { name: 'Remove file: older.ppt', exact: true }).click();
    await expect(dialog.locator('.upload-file')).toHaveCount(4);
    const submit = dialog.getByRole('button', { name: 'Upload 4 files', exact: true });
    await expect(submit).toBeEnabled();
    await expect(dialog.getByRole('heading', { name: 'Add files', exact: true })).toBeInViewport();
    await expect(
      dialog.getByRole('button', { name: 'Close dialog', exact: true }),
    ).toBeInViewport();
    await expect(submit).toBeInViewport();
    await dialog.locator('.upload-preview').evaluate((element) => (element.scrollTop = 0));
    await capture(page, 'office-files-' + width);
    const lastUse = dialog.getByLabel('How to use: review.csv', { exact: true });
    if (width < 600) await lastUse.focus();
    await expect(lastUse).toBeInViewport({ ratio: 1 });
    if (width === 1440) expect((await dialog.boundingBox())!.height).toBeLessThan(750);
    await submit.click();
    await expect(dialog.getByText('Queued', { exact: true }).first()).toBeVisible();
    expect(state.input?.items.map((item) => item.mode)).toEqual([
      'document',
      'document',
      'dataset',
      'dataset',
    ]);
    expect(state.transferred).toBe(files.reduce((size, file) => size + file.buffer.length, 0));
    for (const kind of kinds) await expect(dialog).toContainText('review.' + kind);
    await capture(page, 'office-queued-' + width);
  });
}
test('an individual spreadsheet can be read as text while CSV keeps automatic analysis', async ({
  page,
}) => {
  const state = await fixture(page),
    dialog = await open(page);
  await expect(dialog.locator('ffk-file-formats .format-families')).toContainText('Excel');
  await dialog.getByLabel('Choose files').setInputFiles(
    ['xlsx', 'csv'].map((kind) => ({
      name: 'review.' + kind,
      mimeType: 'application/octet-stream',
      buffer: officeFile(kind as 'xlsx' | 'csv'),
    })),
  );
  await dialog.getByLabel('How to use: review.xlsx', { exact: true }).selectOption('document');
  await dialog.getByRole('button', { name: 'Upload 2 files', exact: true }).click();
  await expect(dialog.getByText('Queued', { exact: true }).first()).toBeVisible();
  expect(state.input?.items.map((item) => item.mode)).toEqual(['document', 'dataset']);
});

for (const width of [1440, 390]) {
  test(`a closed upload keeps its destination and completes through the inbox at ${width}px`, async ({
    page,
  }) => {
    await page.setViewportSize({ width, height: width < 600 ? 844 : 1000 });
    const state = await fixture(page);
    let release!: () => void;
    const gate = new Promise<void>((resolve) => {
      release = resolve;
    });
    await page.route('**/queued-item-0/content', async (route) => {
      await gate;
      await route.fallback();
    });
    const dialog = await open(page);
    await dialog.getByLabel('Choose files').setInputFiles({
      name: 'review.docx',
      mimeType: 'application/octet-stream',
      buffer: officeFile('docx'),
    });
    await dialog.getByRole('button', { name: 'Upload 1 file', exact: true }).click();
    await expect(dialog.getByText('Transferring original', { exact: true })).toBeVisible();
    const destination = state.input!.destination;
    await dialog.getByRole('button', { name: 'Continue in background', exact: true }).click();
    await expect(dialog).toHaveCount(0);
    if (width < 600)
      await page.getByRole('button', { name: 'Open navigation', exact: true }).click();
    await page.getByRole('button', { name: 'Chat', exact: true }).first().click();
    await expect(page.locator('.upload-activity')).toContainText('Uploading files');
    await capture(page, 'background-transfer-' + width);
    release();
    await expect(page.locator('.upload-activity')).toContainText('Processing files');
    expect(state.input!.destination).toEqual(destination);
    await page
      .locator('.upload-activity')
      .getByRole('button', { name: 'View uploads', exact: true })
      .click();
    const inbox = page.locator('ffk-library-retained-uploads-panel');
    await inbox.getByRole('button', { name: 'Inspect upload queue-batch', exact: true }).click();
    await expect(inbox).toContainText('review.docx');
    state.advance('succeeded');
    await expect(inbox.getByText('Processing completed', { exact: true }).first()).toBeVisible({
      timeout: 12000,
    });
    await capture(page, 'background-complete-' + width);
    expect(state.calls.filter((call) => call.method === 'PUT')).toHaveLength(1);
    expect(
      state.calls.filter((call) => call.method === 'POST' && call.path.endsWith('/submit')),
    ).toHaveLength(1);
  });
}
