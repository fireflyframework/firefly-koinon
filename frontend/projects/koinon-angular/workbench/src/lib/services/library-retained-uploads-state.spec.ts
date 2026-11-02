// Copyright 2026 Firefly Software Foundation
// SPDX-License-Identifier: Apache-2.0
import {
  FetchTransport,
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
function setup(httpTransport?: KoinonTransport) {
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
  let writeAccess = true;
  const client = new KoinonClient({ transport: httpTransport ?? transport });
  const make = () =>
    new RetainedUploadsState({
      scope: () => scope,
      client: () => client,
      journal,
      access: () => ({ read: true, write: writeAccess }),
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
    revokeWrite: () => {
      writeAccess = false;
    },
    processingFailure: () => {
      item = {
        ...item,
        status: 'reconciling',
        job_id: 'job',
        error_code: 'INGEST_EXECUTION_CONTEXT_REQUIRED',
      };
      batch = { ...batch, status: 'reconciling' };
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

const recovery = (
  operation:
    'retry_processing' | 'finalize_publication' | 'acknowledge_commit' | null = 'retry_processing',
) => ({
  batch_id: 'batch',
  item_id: 'item',
  batch_revision: 1,
  native_state:
    operation === 'finalize_publication'
      ? 'prepared'
      : operation === 'acknowledge_commit'
        ? 'committed'
        : 'absent',
  operation,
  reason_code: null,
  attempts: 1,
  max_attempts: 3,
  checked_at: '2026-11-01T01:00:00Z',
  job_status: 'failed',
  original_receipt_state: 'verified',
});
it('never inspects or repeats processing on list/reload; fresh recovery needs a separate explicit review and confirmation', async () => {
  const f = setup();
  f.processingFailure();
  f.intercept((method, path) =>
    path.endsWith('/recovery')
      ? Promise.resolve(recovery())
      : path.endsWith('/recover') && method === 'POST'
        ? Promise.resolve(f.state.view().selected)
        : undefined,
  );
  await f.state.load();
  await f.state.select('batch');
  expect(f.calls.some((c) => c.path.endsWith('/recovery'))).toBe(false);
  await f.state.inspectRecovery('item');
  expect(f.state.view().recovery['item'].job_status).toBe('failed');
  expect(f.calls.some((c) => c.method === 'POST')).toBe(false);
  await f.state.review('retry_processing', 'item');
  expect(f.state.view().review?.request.operation).toBe('retry_processing');
  await f.state.confirm();
  const writes = f.calls.filter((c) => c.method === 'POST');
  expect(writes).toHaveLength(1);
  expect(writes[0].path).toBe('/tenants/north/sources/batches/batch/items/item/recover');
  expect(writes[0].options.body).toEqual({ expected_revision: 1, operation: 'retry_processing' });
  expect(f.calls.some((c) => c.method === 'PUT' || c.path.endsWith('/receipt'))).toBe(false);
});
it('refuses a changed recovery action before sending and never substitutes processing for publication', async () => {
  const f = setup();
  f.processingFailure();
  let offered = 'finalize_publication' as 'finalize_publication' | 'retry_processing';
  f.intercept((_, path) =>
    path.endsWith('/recovery') ? Promise.resolve(recovery(offered)) : undefined,
  );
  await f.state.select('batch');
  await f.state.inspectRecovery('item');
  await f.state.review('finalize_publication', 'item');
  offered = 'retry_processing';
  await f.state.confirm();
  expect(f.calls.some((c) => c.method === 'POST')).toBe(false);
  expect(f.state.view().error).toContain('changed');
});
it('does not offer recovery from an unknown outcome or changed credential', async () => {
  const f = setup();
  f.processingFailure();
  f.intercept((_, path) =>
    path.endsWith('/recovery')
      ? Promise.resolve({
          ...recovery(null),
          native_state: 'unknown',
          reason_code: 'BULK_NATIVE_OUTCOME_UNRESOLVED',
        })
      : undefined,
  );
  await f.state.select('batch');
  await f.state.inspectRecovery('item');
  expect(f.state.canAct('retry_processing', 'item')).toBe(false);
  await f.state.review('retry_processing', 'item');
  expect(f.state.view().review).toBeNull();
  f.setScope({ clientRevision: 1 });
  f.state.syncScope();
  expect(f.state.view().recovery).toEqual({});
  expect(f.calls.some((c) => c.method === 'POST')).toBe(false);
});
it('retains an uncertain exact recovery request across reload and permits only explicit same-key reconciliation even when the descriptor no longer offers an action', async () => {
  const f = setup();
  f.processingFailure();
  let first = true;
  f.intercept((method, path) =>
    path.endsWith('/recovery')
      ? Promise.resolve(recovery(first ? 'acknowledge_commit' : null))
      : path.endsWith('/recover') && method === 'POST'
        ? first
          ? ((first = false), Promise.reject(new TypeError('network')))
          : Promise.resolve(f.state.view().selected)
        : undefined,
  );
  await f.state.select('batch');
  await f.state.inspectRecovery('item');
  await f.state.review('acknowledge_commit', 'item');
  await f.state.confirm();
  const original = f.calls.find((c) => c.method === 'POST')!;
  const restored = f.make();
  await restored.select('batch');
  expect(restored.view().pending).toHaveLength(1);
  expect(f.calls.filter((c) => c.method === 'POST')).toHaveLength(1);
  await restored.reviewSaved(restored.view().pending[0]);
  await restored.confirm();
  const writes = f.calls.filter((c) => c.method === 'POST');
  expect(writes).toHaveLength(2);
  expect(writes[1].options.body).toEqual(original.options.body);
  expect(writes[1].options.headers).toEqual(original.options.headers);
});

it('rejects mismatched server recovery identities and refuses writes after current permission loss', async () => {
  const f = setup();
  f.processingFailure();
  let forged = true;
  f.intercept((_, path) =>
    path.endsWith('/recovery')
      ? Promise.resolve({ ...recovery(), item_id: forged ? 'other-item' : 'item' })
      : undefined,
  );
  await f.state.select('batch');
  await f.state.inspectRecovery('item');
  expect(f.state.view().recovery).toEqual({});
  expect(f.state.canAct('retry_processing', 'item')).toBe(false);
  forged = false;
  await f.state.inspectRecovery('item');
  await f.state.review('retry_processing', 'item');
  f.revokeWrite();
  await f.state.confirm();
  expect(f.calls.some((c) => c.method === 'POST')).toBe(false);
});
it('masks descriptor and original metadata after recovery inspection authorization fails', async () => {
  const f = setup();
  f.processingFailure();
  f.intercept((_, path) =>
    path.endsWith('/recovery')
      ? Promise.reject(new KoinonError(403, 'ACCESS_DENIED', 'Private native exception'))
      : undefined,
  );
  await f.state.select('batch');
  await f.state.inspectRecovery('item');
  expect(f.state.view().selected).toBeNull();
  expect(f.state.view().recovery).toEqual({});
  expect(f.state.view().items).toEqual([]);
  expect(f.state.view().error).not.toContain('Private native');
});

it.each([
  { native_state: 'admitted' },
  { attempts: 4, max_attempts: 3 },
  { job_status: 'running' },
])('rejects inconsistent actionable recovery descriptors: %o', async (invalid) => {
  const f = setup();
  f.processingFailure();
  f.intercept((_, path) =>
    path.endsWith('/recovery') ? Promise.resolve({ ...recovery(), ...invalid }) : undefined,
  );
  await f.state.select('batch');
  await f.state.inspectRecovery('item');
  expect(f.state.view().recovery).toEqual({});
  expect(f.state.canAct('retry_processing', 'item')).toBe(false);
  expect(f.calls.some((c) => c.method === 'POST')).toBe(false);
});

it.each(['unavailable', 'revision-change', 'denied', 'invalid-destination'])(
  'clears an acknowledged HTTP202 recovery before a failed status refresh: %s',
  async (failure) => {
    const batch = {
      id: 'batch',
      tenant_id: 'north',
      destination: { workspace_id: 'space', project_id: 'project', parent_id: 'folder' },
      status: 'reconciling',
      revision: 1,
      total_items: 1,
      total_bytes: 8,
      counts: { reconciling: 1 },
      cancellation_requested: false,
      created_at: '2026-11-02T01:00:00.000000Z',
      expires_at: '2026-11-09T01:00:00.000000Z',
    };
    const item = {
      id: 'item',
      client_item_id: 'one',
      filename: 'facts.md',
      mode: 'document',
      size_bytes: 8,
      sha256: 'a'.repeat(64),
      status: 'reconciling',
      source_id: 'source',
      asset_id: 'asset',
      job_id: 'job',
      table_ids: [],
      error_code: 'INGEST_EXECUTION_CONTEXT_REQUIRED',
    };
    let acknowledged = false;
    let readsAfterAck = 0;
    const writes: unknown[] = [];
    const fetcher: typeof fetch = async (input, init) => {
      const path = new URL(String(input));
      let body: unknown;
      let status = 200;
      if (init?.method === 'POST') {
        writes.push(JSON.parse(String(init.body)));
        acknowledged = true;
        status = 202;
        body = {
          ...batch,
          revision: 2,
          status: 'queued',
          counts: { queued: 1 },
          ...(failure === 'invalid-destination'
            ? { destination: { ...batch.destination, workspace_id: 'other-space' } }
            : {}),
        };
      } else if (acknowledged) {
        if (failure === 'denied') {
          status = 401;
          body = { code: 'SESSION_REQUIRED', detail: 'Private account failure' };
        } else if (failure === 'unavailable') {
          status = 503;
          body = { code: 'STATUS_UNAVAILABLE', detail: 'Private upstream failure' };
        } else if (path.pathname.endsWith('/items')) {
          body = { items: [item], total: 1, page: 1, page_size: 50, pages: 1 };
        } else {
          body = { ...batch, revision: 2 + readsAfterAck++, counts: { reconciling: 1 } };
        }
      } else if (path.pathname.endsWith('/recovery')) body = recovery();
      else if (path.pathname.endsWith('/items'))
        body = { items: [item], total: 1, page: 1, page_size: 50, pages: 1 };
      else body = batch;
      return new Response(JSON.stringify(body), {
        status,
        headers: { 'Content-Type': 'application/json' },
      });
    };
    const f = setup(new FetchTransport({ baseUrl: 'http://127.0.0.1/bff/api/v1', fetch: fetcher }));
    try {
      await f.state.select('batch');
      await f.state.inspectRecovery('item');
      await f.state.review('retry_processing', 'item');
      await f.state.confirm();
      expect(writes).toEqual([{ expected_revision: 1, operation: 'retry_processing' }]);
      if (failure === 'invalid-destination') {
        expect(f.state.view().pending).toHaveLength(1);
        expect(f.journal.forBatch('alex', 'north', 'batch')).toHaveLength(1);
        expect(f.state.view().notice).toBe('');
        expect(f.state.view().error).toContain('could not be confirmed');
        return;
      }
      expect(f.state.view().pending).toEqual([]);
      expect(f.journal.forBatch('alex', 'north', 'batch')).toEqual([]);
      if (failure === 'denied') {
        expect(f.state.view().denied).toBe(true);
        expect(f.state.view().selected).toBeNull();
        expect(f.state.view().items).toEqual([]);
        expect(f.state.view().notice).toBe('');
        expect(f.state.view().error).not.toContain('Private account');
        return;
      }
      expect(f.state.view().selected?.revision).toBe(2);
      expect(f.state.view().notice).toBe('');
      expect(f.state.view().items).toEqual([]);
      expect(f.state.view().error).toBe(
        'The action was acknowledged, but the current status could not be refreshed. Inspect the upload again; do not repeat the action.',
      );
      expect(f.state.view().error).not.toContain('Private upstream');
    } finally {
      f.state.dispose();
    }
  },
);
