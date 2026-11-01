// Copyright 2026 Firefly Software Foundation
// SPDX-License-Identifier: Apache-2.0
import { describe, expect, it, vi } from 'vitest';
import {
  KoinonClient,
  KoinonError,
  type KoinonTransport,
  type RequestOptions,
} from '@fireflyframework/koinon-sdk';
import {
  effectiveUploadLimits,
  LibraryUploadCoordinator,
  type UploadScope,
} from './library-upload-coordinator';

function fixture(configured = true) {
  const calls: { method: string; path: string; options: RequestOptions }[] = [];
  let status = 'staging',
    revision = 1,
    created = false;
  const batch = () => ({
    id: 'batch',
    tenant_id: 'tenant',
    destination: { workspace_id: 'space', project_id: 'project', parent_id: 'folder' },
    status,
    revision,
    total_items: 1,
    total_bytes: 1,
    counts: {},
    cancellation_requested: status === 'cancelled',
    created_at: '2026-11-01T00:00:00Z',
    expires_at: '2026-11-02T00:00:00Z',
  });
  let item = {
    id: 'item',
    client_item_id: '',
    filename: 'office.docx',
    mode: 'document',
    size_bytes: 1,
    sha256: 'a'.repeat(64),
    status: 'awaiting_upload',
    source_id: 'source',
    asset_id: 'asset',
    job_id: null,
  };
  const transport: KoinonTransport = {
    request: async <T>(method: string, path: string, options: RequestOptions = {}) => {
      calls.push({ method, path, options });
      if (path.endsWith('/catalog/availability'))
        return {
          observed_at: '2026-11-01T00:00:00Z',
          items: { asset: { phase: status === 'queued' ? 'queued' : 'unknown' } },
        } as T;
      if (path.endsWith('source-batch-capabilities'))
        return {
          configured,
          modes: ['document', 'dataset'],
          max_file_bytes: 134217728,
          max_batch_bytes: 536870912,
          max_files: 100,
          synchronous_max_file_bytes: 33554432,
        } as T;
      if (path.endsWith('/batches') && method === 'GET')
        return {
          items: created ? [batch()] : [],
          total: created ? 1 : 0,
          page: 1,
          page_size: 10,
          pages: created ? 1 : 0,
        } as T;
      if (path.endsWith('/batches') && method === 'POST') {
        created = true;
        item = { ...item, ...(options.body as { items: (typeof item)[] }).items[0] };
        return batch() as T;
      }
      if (path.endsWith('/items'))
        return { items: [item], total: 1, page: 1, page_size: 50, pages: 1 } as T;
      if (path.endsWith('/content')) {
        item.status = 'staged';
        revision++;
        return {
          status: 'staged',
          batch_id: 'batch',
          item_id: 'item',
          size_bytes: item.size_bytes,
          sha256: item.sha256,
        } as T;
      }
      if (path.endsWith('/original/reconcile')) {
        item.status = 'staged';
        revision++;
        return batch() as T;
      }
      if (path.endsWith('/submit')) {
        status = 'queued';
        item.status = 'queued';
        revision++;
        return batch() as T;
      }
      if (path.endsWith('/cancel')) {
        status = 'cancelled';
        revision++;
        return batch() as T;
      }
      if (path.endsWith('/batch')) return batch() as T;
      throw new Error('Unexpected fixture request');
    },
    stream: () => {
      throw new Error('Streaming is outside this upload fixture');
    },
  };
  const scope: UploadScope = {
    owner: {},
    clientRevision: 1,
    tenantId: 'tenant',
    workspaceId: 'space',
    projectId: 'project',
    parentId: 'folder',
    transport,
  };
  const client = new KoinonClient({ transport });
  const synchronous = vi.fn(async () => true);
  const changed = vi.fn(async () => undefined);
  const hash = vi.fn(async () => 'a'.repeat(64));
  const state = new LibraryUploadCoordinator({
    scope: () => scope,
    client: () => client,
    synchronous,
    hash,
    changed,
  });
  return { calls, scope, transport, state, synchronous, hash, changed };
}
describe('durable regular Library uploads', () => {
  it('shares honest displayed and enforced limits when server caps exceed browser or synchronous bounds', async () => {
    const f = fixture();
    await f.state.start([new File(['one'], 'office.docx')], 'document');
    const capabilities = {
      ...f.state.view().capabilities!,
      max_file_bytes: 536870912,
      max_batch_bytes: 1073741824,
      synchronous_max_file_bytes: 134217728,
    };
    expect(effectiveUploadLimits(capabilities)).toEqual({
      max_file_bytes: 134217728,
      max_batch_bytes: 536870912,
      max_files: 100,
    });
    expect(effectiveUploadLimits({ ...capabilities, configured: false }).max_file_bytes).toBe(
      33554432,
    );
    f.state.dispose();
  });
  it('keeps transfer ownership active between observed staging requests, then clears it', async () => {
    const f = fixture();
    const request = f.transport.request.bind(f.transport);
    const observed: boolean[] = [];
    f.transport.request = async (method, path, options) => {
      if (path.endsWith('/content') || path.endsWith('/submit'))
        observed.push(f.state.view().transferring);
      return request(method, path, options);
    };
    await f.state.start([new File(['original'], 'office.docx')], 'document');
    expect(observed).toEqual([true, true]);
    expect(f.state.view().transferring).toBe(false);
    f.state.dispose();
  });
  it('routes configured ordinary uploads through raw staging and fresh-revision submission, never synchronous parsing', async () => {
    const f = fixture();
    await f.state.start([new File(['original'], 'office.docx')], 'document');
    expect(f.synchronous).not.toHaveBeenCalled();
    expect(f.calls.filter((call) => call.method === 'PUT')).toHaveLength(1);
    const put = f.calls.find((call) => call.method === 'PUT')!;
    expect(put.options.body).toBeInstanceOf(Blob);
    expect(put.options.headers?.['Content-Type']).toBe('application/octet-stream');
    expect(f.calls.find((call) => call.path.endsWith('/submit'))?.options.body).toEqual({
      expected_revision: 2,
    });
    expect(f.state.view().batch?.status).toBe('queued');
    expect(f.state.view().message).not.toContain('Searchable');
    f.state.dispose();
  });
  it('blocks large files when queued storage is unavailable instead of falling back to API parsing', async () => {
    const f = fixture(false);
    const file = new File(['bounded fixture'], 'large.xlsx');
    Object.defineProperty(file, 'size', { value: 33554433 });
    await f.state.start([file], 'dataset');
    expect(f.synchronous).not.toHaveBeenCalled();
    expect(f.calls.every((call) => call.method === 'GET')).toBe(true);
    expect(f.state.view().message).toContain('queued');
    f.state.dispose();
  });
  it('cancels only through the native batch operation using a fresh observed revision', async () => {
    const f = fixture();
    await f.state.start([new File(['original'], 'office.docx')], 'document');
    await f.state.cancel();
    expect(f.calls.find((call) => call.path.endsWith('/cancel'))?.options.body).toEqual({
      expected_revision: 3,
    });
    expect(f.calls.some((call) => call.path.includes('/jobs/'))).toBe(false);
    expect(f.state.view().batch?.status).toBe('cancelled');
    f.state.dispose();
  });
});

it('does not replay a committed original whose acknowledgement was lost, and resumes only after explicit review', async () => {
  const f = fixture();
  const original = f.transport.request.bind(f.transport);
  f.transport.request = async <T>(
    method: Parameters<KoinonTransport['request']>[0],
    path: string,
    options?: RequestOptions,
  ) => {
    const response = await original<T>(method, path, options);
    if (path.endsWith('/content')) throw new Error('Lost receipt');
    return response;
  };
  const files = [new File(['original'], 'office.docx')];
  await f.state.start(files, 'document');
  expect(f.state.view().uncertain).toBe(true);
  await f.state.start(files, 'document');
  expect(f.state.view().uncertain).toBe(false);
  expect(f.calls.filter((call) => call.method === 'PUT')).toHaveLength(1);
  expect(f.calls.filter((call) => call.path.endsWith('/submit'))).toHaveLength(0);
  await f.state.continue();
  expect(f.calls.filter((call) => call.path.endsWith('/submit'))).toHaveLength(1);
  expect(f.synchronous).not.toHaveBeenCalled();
  f.state.dispose();
});
it('recovers an unacknowledged create using bounded owner-scoped reads, without a second create', async () => {
  const f = fixture();
  const original = f.transport.request.bind(f.transport);
  f.transport.request = async <T>(
    method: Parameters<KoinonTransport['request']>[0],
    path: string,
    options?: RequestOptions,
  ) => {
    const response = await original<T>(method, path, options);
    if (method === 'POST' && path.endsWith('/batches')) throw new Error('Lost create response');
    return response;
  };
  await f.state.start([new File(['original'], 'office.docx')], 'document');
  expect(f.state.view().uncertain).toBe(true);
  await f.state.refresh();
  expect(f.state.view().batch?.id).toBe('batch');
  expect(
    f.calls.filter((call) => call.method === 'POST' && call.path.endsWith('/batches')),
  ).toHaveLength(1);
  expect(f.calls.filter((call) => call.method === 'PUT')).toHaveLength(0);
  f.state.dispose();
});
it('never resubmits an uncertain submission after status reads prove it was queued', async () => {
  const f = fixture();
  const original = f.transport.request.bind(f.transport);
  f.transport.request = async <T>(
    method: Parameters<KoinonTransport['request']>[0],
    path: string,
    options?: RequestOptions,
  ) => {
    const response = await original<T>(method, path, options);
    if (path.endsWith('/submit')) throw new Error('Lost submit response');
    return response;
  };
  await f.state.start([new File(['original'], 'office.docx')], 'document');
  await f.state.refresh();
  await f.state.continue();
  expect(f.state.view().batch?.status).toBe('queued');
  expect(f.calls.filter((call) => call.path.endsWith('/submit'))).toHaveLength(1);
  f.state.dispose();
});
it('discards an old actor during hashing and never creates or uploads with the old scope', async () => {
  const f = fixture();
  let finish!: (value: string) => void;
  f.hash.mockImplementationOnce(
    () =>
      new Promise((resolve) => {
        finish = resolve;
      }),
  );
  const pending = f.state.start([new File(['original'], 'office.docx')], 'document');
  await vi.waitFor(() => expect(f.hash).toHaveBeenCalledOnce());
  f.scope.owner = {};
  f.scope.transport = null;
  f.scope.clientRevision++;
  expect(f.state.view().batch).toBeNull();
  expect(f.state.view().stage).toBe('idle');
  f.state.invalidate();
  finish('a'.repeat(64));
  await pending;
  expect(f.calls.every((call) => call.method === 'GET')).toBe(true);
  expect(f.state.view().stage).toBe('idle');
});
it('permits a corrected selection after a pre-admission limit rejection', async () => {
  const f = fixture();
  const tooLarge = new File(['bounded fixture'], 'oversized.docx');
  Object.defineProperty(tooLarge, 'size', { value: 134217729 });
  await f.state.start([tooLarge], 'document');
  await f.state.start([new File(['valid'], 'office.docx')], 'document');
  expect(f.state.view().batch?.status).toBe('queued');
  f.state.dispose();
});

it('uses explicit retained-original reconciliation and never reuploads an uncertain original', async () => {
  const f = fixture();
  const original = f.transport.request.bind(f.transport);
  f.transport.request = async <T>(
    method: Parameters<KoinonTransport['request']>[0],
    path: string,
    options?: RequestOptions,
  ) => {
    if (path.endsWith('/content')) {
      f.calls.push({ method, path, options: options || {} });
      throw new Error('Unknown transfer outcome');
    }
    return original<T>(method, path, options);
  };
  await f.state.start([new File(['original'], 'office.docx')], 'document');
  expect(f.state.canRecover(f.state.view().items[0]!)).toBe(true);
  await f.state.recoverOriginal('item');
  await f.state.recoverOriginal('item');
  expect(f.calls.filter((call) => call.path.endsWith('/original/reconcile'))).toHaveLength(1);
  expect(f.calls.filter((call) => call.method === 'PUT')).toHaveLength(1);
  expect(f.state.view().uncertain).toBe(false);
  expect(f.state.view().items[0]?.status).toBe('staged');
  expect(f.calls.find((call) => call.path.endsWith('/original/reconcile'))?.options.body).toEqual({
    expected_revision: 1,
  });
  await f.state.continue();
  expect(f.state.view().batch?.status).toBe('queued');
  f.state.dispose();
});
it('permits only the observed small synchronous fallback when queued storage is explicitly unconfigured', async () => {
  const f = fixture(false);
  await f.state.start([new File(['small'], 'small.txt')], 'document');
  expect(f.synchronous).toHaveBeenCalledOnce();
  expect(f.calls.every((call) => call.method === 'GET')).toBe(true);
  expect(f.state.view().received).toBe(1);
  expect(f.state.view().batch).toBeNull();
  f.state.dispose();
});
it('blocks fallback after a capability error without sending file bytes', async () => {
  const f = fixture();
  f.transport.request = async () => {
    throw new Error('Service unavailable');
  };
  await f.state.start([new File(['small'], 'small.txt')], 'document');
  expect(f.synchronous).not.toHaveBeenCalled();
  expect(f.hash).not.toHaveBeenCalled();
  expect(f.state.view().message).toContain('No files were sent');
  f.state.dispose();
});
it('never submits when an original receipt disagrees with the immutable manifest', async () => {
  const f = fixture();
  const original = f.transport.request.bind(f.transport);
  f.transport.request = async <T>(
    method: Parameters<KoinonTransport['request']>[0],
    path: string,
    options?: RequestOptions,
  ) => {
    const value = await original<T>(method, path, options);
    return path.endsWith('/content')
      ? ({ ...(value as object), sha256: 'b'.repeat(64) } as T)
      : value;
  };
  await f.state.start([new File(['original'], 'office.docx')], 'document');
  expect(f.state.view().uncertain).toBe(true);
  expect(f.calls.some((call) => call.path.endsWith('/submit'))).toBe(false);
  f.state.dispose();
});

it('retains an acknowledged queued state when a later status read fails', async () => {
  const f = fixture();
  await f.state.start([new File(['original'], 'office.docx')], 'document');
  f.transport.request = async () => {
    throw new Error('Read unavailable');
  };
  await f.state.refresh();
  expect(f.state.view().batch?.status).toBe('queued');
  expect(f.state.view().uncertain).toBe(false);
  expect(f.state.view().message).toContain('Last observations');
  f.state.dispose();
});

it('removes prior batch observations when fresh access is denied', async () => {
  const f = fixture();
  await f.state.start([new File(['original'], 'office.docx')], 'document');
  f.transport.request = async () => {
    throw new KoinonError(403, 'ACCESS_DENIED', 'Unavailable');
  };
  await f.state.refresh();
  expect(f.state.view().batch).toBeNull();
  expect(f.state.view().items).toEqual([]);
  expect(f.state.view().message).toContain('Current upload access');
  f.state.dispose();
});

it('keeps confirmed small synchronous files and refreshes the folder without resending an uncertain remainder', async () => {
  const f = fixture(false);
  f.synchronous.mockResolvedValueOnce(true).mockResolvedValueOnce(false);
  await f.state.start([new File(['one'], 'one.txt'), new File(['two'], 'two.txt')], 'document');
  expect(f.state.view().received).toBe(1);
  expect(f.state.view().uncertain).toBe(true);
  await f.state.refresh();
  expect(f.changed).toHaveBeenCalledOnce();
  expect(f.synchronous).toHaveBeenCalledTimes(2);
  expect(f.state.view().message).toContain('synchronous upload');
  f.state.dispose();
});
