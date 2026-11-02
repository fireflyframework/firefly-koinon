// Copyright 2026 Firefly Software Foundation
// SPDX-License-Identifier: Apache-2.0
import {
  KoinonClient,
  KoinonError,
  type FileBatchView,
  type FileBatchItemView,
  type KoinonTransport,
  type RequestOptions,
  type HttpMethod,
} from '@fireflyframework/koinon-sdk';
import { RetainedUploadsState } from './library-retained-uploads-state';
import { RetainedUploadJournal } from './library-retained-uploads-journal';
import type { RetainedUploadScope } from './library-retained-uploads-contract';
function setup() {
  let scope: RetainedUploadScope = {
    owner: {},
    subject: 'alex',
    tenantId: 'north',
    clientRevision: 0,
    transport: {},
    allowed: true,
  };
  let batch: FileBatchView = {
    id: 'batch',
    tenant_id: 'north',
    destination: { workspace_id: 'space', project_id: 'project', parent_id: 'folder' },
    status: 'staging',
    revision: 1,
    total_items: 1,
    total_bytes: 2,
    counts: { awaiting_upload: 1 },
    cancellation_requested: false,
    created_at: '2026-11-01T00:00:00Z',
    expires_at: '2099-01-01T00:00:00Z',
  };
  let item: FileBatchItemView = {
    id: 'item',
    client_item_id: 'client-item',
    filename: 'report.docx',
    mode: 'document',
    size_bytes: 2,
    sha256: 'a'.repeat(64),
    status: 'awaiting_upload',
    source_id: 'source',
    asset_id: 'asset',
    job_id: null,
    table_ids: [],
  };
  const calls: { method: string; path: string; options: RequestOptions }[] = [];
  let intercept:
    | ((method: string, path: string, options: RequestOptions) => Promise<unknown> | undefined)
    | undefined;
  const transport: KoinonTransport = {
    stream: () => {
      throw Error('Unexpected stream');
    },
    request: async <T>(method: HttpMethod, path: string, options: RequestOptions = {}) => {
      calls.push({ method, path, options });
      const replacement = intercept?.(method, path, options);
      if (replacement) return (await replacement) as T;
      if (path.endsWith('/batches'))
        return {
          items: [batch],
          total: 1,
          page: options.query?.['page'] ?? 1,
          page_size: 25,
          pages: 1,
        } as T;
      if (path.endsWith('/items'))
        return { items: [item], total: 1, page: 1, page_size: 50, pages: 1 } as T;
      if (path.endsWith('/original/reconcile')) {
        item = { ...item, status: 'staged' };
        batch = { ...batch, revision: batch.revision + 1, counts: { staged: 1 } };
        return batch as T;
      }
      if (path.endsWith('/submit')) {
        item = { ...item, status: 'queued', job_id: 'job' };
        batch = { ...batch, status: 'queued', revision: batch.revision + 1, counts: { queued: 1 } };
        return batch as T;
      }
      if (path.endsWith('/receipt'))
        return {
          receipt_id: 'receipt',
          batch_id: 'batch',
          item_id: 'item',
          status: 'staged',
          sha256: item.sha256,
          size_bytes: item.size_bytes,
        } as T;
      if (path.endsWith('/batch')) return batch as T;
      throw Error('Unexpected request');
    },
  };
  const values = new Map<string, string>();
  const journal = new RetainedUploadJournal({
    getItem: (key) => values.get(key) ?? null,
    setItem: (key, value) => {
      values.set(key, value);
    },
    removeItem: (key) => {
      values.delete(key);
    },
  });
  const client = new KoinonClient({ transport });
  const make = () =>
    new RetainedUploadsState({
      scope: () => scope,
      client: () => client,
      journal,
      access: () => ({ read: true, write: true }),
    });
  return {
    state: make(),
    make,
    calls,
    journal,
    setScope: (v: Partial<RetainedUploadScope>) => {
      scope = { ...scope, ...v };
    },
    scope: () => scope,
    intercept: (fn: typeof intercept) => {
      intercept = fn;
    },
    revise: () => {
      batch = { ...batch, revision: batch.revision + 1 };
    },
  };
}
it('lists and reopens server retained batches without checking blobs or sending any mutation', async () => {
  const f = setup();
  await f.state.load();
  await f.state.select('batch');
  expect(f.state.view().selected?.id).toBe('batch');
  expect(f.state.view().items[0].filename).toBe('report.docx');
  expect(f.calls.every((c) => c.method === 'GET' && !c.path.endsWith('/receipt'))).toBe(true);
  const restored = f.make();
  await restored.load();
  await restored.select('batch');
  expect(restored.view().selected?.id).toBe('batch');
  expect(f.calls.every((c) => c.method === 'GET')).toBe(true);
});
it('requires fresh explicit review for retained original verification then separate submission', async () => {
  const f = setup();
  await f.state.select('batch');
  await f.state.review('recover_original', 'item');
  expect(f.calls.every((c) => c.method === 'GET')).toBe(true);
  await Promise.all([f.state.confirm(), f.state.confirm()]);
  expect(f.state.view().items[0].status).toBe('staged');
  expect(f.calls.filter((c) => c.method === 'POST')).toHaveLength(1);
  expect(f.calls.some((c) => c.method === 'PUT' || c.path.endsWith('/submit'))).toBe(false);
  await f.state.review('submit');
  await f.state.confirm();
  expect(f.state.view().selected?.status).toBe('queued');
});
it('does not restore saved actions before fresh authorization under a different credential', async () => {
  const f = setup();
  f.journal.put({
    subject: 'alex',
    tenantId: 'north',
    batchId: 'batch',
    itemId: 'item',
    operation: 'recover_original',
    expectedRevision: 1,
    key: 'saved-key',
  });
  const restored = f.make();
  expect(restored.view().pending).toEqual([]);
  f.intercept((_, path) =>
    path.endsWith('/batch')
      ? Promise.reject(new KoinonError(403, 'ACCESS_DENIED', 'Private original'))
      : undefined,
  );
  await restored.select('batch');
  expect(restored.view().selected).toBeNull();
  expect(restored.view().pending).toEqual([]);
  expect(restored.view().error).not.toContain('Private original');
});
it('rejects stale reviewed revisions without a write', async () => {
  const f = setup();
  await f.state.select('batch');
  await f.state.review('recover_original', 'item');
  f.revise();
  await f.state.confirm();
  expect(f.calls.some((c) => c.method === 'POST')).toBe(false);
  expect(f.state.view().error).toContain('changed');
});
it('aborts and masks the old account response', async () => {
  const f = setup();
  let resolve!: (v: unknown) => void;
  f.intercept((_, path) =>
    path.endsWith('/batches')
      ? new Promise((yes) => {
          resolve = yes;
        })
      : undefined,
  );
  const load = f.state.load();
  await vi.waitFor(() => expect(typeof resolve).toBe('function'));
  f.setScope({ owner: {}, subject: 'sam' });
  f.state.syncScope();
  resolve({ items: [], total: 0, page: 1, page_size: 25, pages: 0 });
  await load;
  expect(f.state.view().rows).toEqual([]);
  expect(f.calls[0].options.signal?.aborted).toBe(true);
});

it('keeps an unknown request across reload but resends only after fresh batch authorization and explicit same-key review', async () => {
  const f = setup();
  await f.state.select('batch');
  await f.state.review('recover_original', 'item');
  let first = true;
  f.intercept((method, path) =>
    method === 'POST' && path.endsWith('/original/reconcile') && first
      ? ((first = false), Promise.reject(new TypeError('network')))
      : undefined,
  );
  await f.state.confirm();
  const original = f.calls.find((c) => c.method === 'POST')!;
  expect(f.state.view().pending).toHaveLength(1);
  const restored = f.make();
  expect(restored.view().pending).toEqual([]);
  await restored.load();
  await restored.select('batch');
  expect(restored.view().pending).toHaveLength(1);
  expect(f.calls.filter((c) => c.method === 'POST')).toHaveLength(1);
  await restored.reviewSaved(restored.view().pending[0]);
  expect(f.calls.filter((c) => c.method === 'POST')).toHaveLength(1);
  await restored.confirm();
  const writes = f.calls.filter((c) => c.method === 'POST');
  expect(writes).toHaveLength(2);
  expect(writes[1].options.headers).toEqual(original.options.headers);
  expect(writes[1].options.body).toEqual(original.options.body);
  expect(restored.view().items[0].status).toBe('staged');
});
it('makes a blob receipt check only on an explicit request and binds it to the exact current item', async () => {
  const f = setup();
  await f.state.select('batch');
  await f.state.review('recover_original', 'item');
  await f.state.confirm();
  expect(f.calls.some((c) => c.path.endsWith('/receipt'))).toBe(false);
  await f.state.verifyReceipt('item');
  expect(f.calls.filter((c) => c.path.endsWith('/receipt'))).toHaveLength(1);
  expect(f.state.view().receipts['item'].value.sha256).toBe('a'.repeat(64));
});
it('clears names and saved actions when current authorization returns 401', async () => {
  const f = setup();
  await f.state.select('batch');
  f.intercept((_, path) =>
    path.endsWith('/batch')
      ? Promise.reject(new KoinonError(401, 'SESSION_REQUIRED', 'Private exception text'))
      : undefined,
  );
  await f.state.select('batch');
  expect(f.state.view().items).toEqual([]);
  expect(f.state.view().rows).toEqual([]);
  expect(f.state.view().pending).toEqual([]);
  expect(f.state.view().error).not.toContain('Private exception');
});
it('does not restore a journal action for an item outside the freshly authorized batch', async () => {
  const f = setup();
  f.journal.put({
    subject: 'alex',
    tenantId: 'north',
    batchId: 'batch',
    itemId: 'foreign-item',
    operation: 'recover_original',
    expectedRevision: 1,
    key: 'foreign-key',
  });
  await f.state.select('batch');
  expect(f.state.view().pending).toEqual([]);
  expect(f.state.view().journalError).toBe(true);
  expect(f.state.canAct('recover_original', 'item')).toBe(false);
  expect(f.calls.every((c) => c.method === 'GET')).toBe(true);
});
it('reviews the saved exact body instead of a caller-modified request with the same key', async () => {
  const f = setup();
  const request = {
    subject: 'alex',
    tenantId: 'north',
    batchId: 'batch',
    itemId: 'item',
    operation: 'recover_original' as const,
    expectedRevision: 1,
    key: 'saved-key',
  };
  f.journal.put(request);
  await f.state.select('batch');
  await f.state.reviewSaved({ ...request, expectedRevision: 99 });
  expect(f.state.view().review?.request.expectedRevision).toBe(1);
});
