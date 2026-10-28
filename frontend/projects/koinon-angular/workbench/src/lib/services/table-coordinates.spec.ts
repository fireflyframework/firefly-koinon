// Copyright 2026 Firefly Software Foundation
// SPDX-License-Identifier: Apache-2.0
import { signal } from '@angular/core';
import { TestBed } from '@angular/core/testing';
import {
  KoinonClient,
  KoinonError,
  type KoinonTransport,
  type RequestOptions,
} from '@fireflyframework/koinon-sdk';
import { KoinonFacade } from '../koinon-facade';
import { KoinonClientContext } from './client-context';
import { KoinonTableCoordinates } from './table-coordinates';

const target = { datasetId: 'dataset', tableId: 'table', snapshotId: 'selected' };
const manifest = {
  dataset_id: 'dataset',
  table_id: 'table',
  native_dataset_id: 'native-dataset',
  native_table_id: 'native-table',
  snapshot_id: 'selected',
  status: 'complete',
  index_base: 0,
  row_count: 300,
  column_count: 2,
  artifact_id: 'artifact',
  run_id: 'run',
  input_sha256: 'a'.repeat(64),
  mapping_sha256: 'b'.repeat(64),
  source_format: 'excel',
  source_variant: 'xlsx',
  row_kind: 'sheet_row',
  source_sheet: 'Orders',
  source_path: [],
  parser_decisions: [],
  dependencies: [],
  rejected_source_rows: [],
};
function rows(page = 1) {
  const start = (page - 1) * 25;
  return {
    manifest,
    items: Array.from({ length: page === 1 ? 25 : 5 }, (_, i) => ({
      output_start: (start + i) * 10,
      count: 10,
      source_start: 100 + (start + i) * 20,
      source_stride: 1,
    })),
    total: 30,
    page,
    page_size: 25,
    pages: 2,
    has_next: page === 1,
    has_previous: page === 2,
  };
}
function setup(request: KoinonTransport['request']) {
  const facade = {
    tenantId: signal('north'),
    workspaceId: signal('w'),
    projectId: signal('p'),
    context: signal({ subject: 'owner' }),
    permissions: signal(new Set(['catalog:read'])),
    authRequired: signal(false),
  };
  const transport: KoinonTransport = {
    request,
    stream: () => {
      throw Error('Unexpected inference');
    },
  };
  const clients = { revision: signal(0), get: () => new KoinonClient({ transport }) };
  TestBed.configureTestingModule({
    providers: [
      KoinonTableCoordinates,
      { provide: KoinonFacade, useValue: facade },
      { provide: KoinonClientContext, useValue: clients },
    ],
  });
  return { state: TestBed.inject(KoinonTableCoordinates), facade, clients };
}
it('opens only the selected immutable manifest, then uses real server row pagination on demand', async () => {
  const calls: { path: string; options?: RequestOptions }[] = [];
  const { state } = setup(async <T>(_method: unknown, path: string, options?: RequestOptions) => {
    calls.push({ path, options });
    return (path.endsWith('/rows') ? rows(Number(options?.query?.['page'])) : manifest) as T;
  });
  await state.open(target);
  expect(calls).toHaveLength(1);
  expect(calls[0].path).toBe('/tenants/north/datasets/dataset/tables/table/coordinates');
  expect(calls[0].options?.query).toEqual({ snapshot_id: 'selected' });
  expect(state.rowsPage()).toBeNull();
  await state.choose('rows');
  expect(calls[1].options?.query).toEqual({ snapshot_id: 'selected', page: 1, page_size: 25 });
  await state.pageRows(2);
  expect(state.rowsPage()?.page).toBe(2);
  expect(state.rowsPage()?.total).toBe(30);
  expect(state.rowsPage()?.items).toHaveLength(5);
});
it('converts one-based user input to exact zero-based cell positions without sending values', async () => {
  const calls: { method: unknown; path: string; options?: RequestOptions }[] = [];
  const { state } = setup(async <T>(method: unknown, path: string, options?: RequestOptions) => {
    calls.push({ method, path, options });
    return (
      path.endsWith('/cells')
        ? {
            manifest,
            items: [
              {
                output_row: 1,
                output_column: 0,
                source_row: 4,
                source_column: 3,
                source_path: [],
                header_cells: [{ row: 3, column: 3 }],
                source_type: null,
              },
            ],
          }
        : manifest
    ) as T;
  });
  await state.open(target);
  await state.choose('cell');
  expect(calls).toHaveLength(1);
  await state.find('2', '1');
  expect(calls[1].method).toBe('POST');
  expect(calls[1].options?.body).toEqual({
    snapshot_id: 'selected',
    cells: [{ row: 1, column: 0 }],
  });
  expect(state.selection()?.items[0].source_row).toBe(4);
  await state.find('1.5', '1');
  await state.find('0', '1');
  await state.find('301', '1');
  expect(calls).toHaveLength(2);
});
it('hides and aborts pending data immediately after context, client or authority changes', async () => {
  let finish!: (value: unknown) => void;
  let requestSignal!: AbortSignal;
  const { state, facade, clients } = setup(
    <T>(_method: unknown, _path: string, options?: RequestOptions) => {
      requestSignal = options!.signal!;
      return new Promise<T>((resolve) => {
        finish = (value) => resolve(value as T);
      });
    },
  );
  const pending = state.open(target);
  facade.context.set({ subject: 'owner' });
  expect(state.manifest()).toBeNull();
  TestBed.tick();
  expect(requestSignal.aborted).toBe(true);
  finish(manifest);
  await pending;
  expect(state.manifest()).toBeNull();
  const next = state.open(target);
  clients.revision.update((x) => x + 1);
  expect(state.target()).toBeNull();
  TestBed.tick();
  finish(manifest);
  await next;
  facade.permissions.set(new Set());
  await state.open(target);
  expect(state.target()).toBeNull();
});
it('rejects a mismatched response and never substitutes current metadata for an unknown version', async () => {
  let foreign = true;
  const { state } = setup(
    async <T>() =>
      (foreign
        ? { ...manifest, snapshot_id: 'other' }
        : {
            dataset_id: 'dataset',
            table_id: 'table',
            native_dataset_id: 'native-dataset',
            native_table_id: 'native-table',
            snapshot_id: 'selected',
            status: 'not_recorded',
            index_base: 0,
            source_path: [],
            parser_decisions: [],
            dependencies: [],
            rejected_source_rows: [],
          }) as T,
  );
  await state.open(target);
  expect(state.manifest()).toBeNull();
  expect(state.error()).toContain('selected version');
  foreign = false;
  await state.open(target);
  expect(state.manifest()?.status).toBe('not_recorded');
  expect(state.manifest()?.artifact_id).toBeUndefined();
});
it('rejects pages or cell receipts whose immutable mapping disagrees with the selected manifest', async () => {
  const { state } = setup(
    async <T>(_method: unknown, path: string) =>
      (path.endsWith('/rows')
        ? { ...rows(), manifest: { ...manifest, mapping_sha256: 'c'.repeat(64) } }
        : manifest) as T,
  );
  await state.open(target);
  await state.choose('rows');
  expect(state.rowsPage()).toBeNull();
  expect(state.error()).toContain('selected version');
});
it('requires catalog permission and distinguishes expired sessions from denied access', async () => {
  let calls = 0,
    status = 403;
  const { state, facade } = setup(async () => {
    calls++;
    throw new KoinonError(status, 'DENIED', 'Access denied');
  });
  facade.permissions.set(new Set());
  await state.open(target);
  expect(calls).toBe(0);
  facade.permissions.set(new Set(['catalog:read']));
  await state.open(target);
  expect(state.error()).toBe('Access denied');
  expect(facade.authRequired()).toBe(false);
  status = 401;
  await state.retry();
  expect(facade.authRequired()).toBe(true);
  expect(state.manifest()).toBeNull();
});
it('aborts an earlier cell lookup when a new submitted position is invalid', async () => {
  let finish!: (value: unknown) => void;
  let requestSignal!: AbortSignal;
  const { state } = setup(<T>(_method: unknown, path: string, options?: RequestOptions) => {
    if (!path.endsWith('/cells')) return Promise.resolve(manifest as T);
    requestSignal = options!.signal!;
    return new Promise<T>((resolve) => {
      finish = (value) => resolve(value as T);
    });
  });
  await state.open(target);
  await state.choose('cell');
  const pending = state.find('1', '1');
  await state.find('invalid', '1');
  expect(requestSignal.aborted).toBe(true);
  finish({
    manifest,
    items: [
      {
        output_row: 0,
        output_column: 0,
        source_row: 1,
        source_column: 0,
        source_path: [],
        header_cells: [],
        source_type: null,
      },
    ],
  });
  await pending;
  expect(state.selection()).toBeNull();
});
it('uses the column SDK operation and hides known metadata after a later denial', async () => {
  let deny = false;
  const calls: { path: string; options?: RequestOptions }[] = [];
  const { state, facade } = setup(
    async <T>(_method: unknown, path: string, options?: RequestOptions) => {
      calls.push({ path, options });
      if (deny) throw new KoinonError(403, 'DENIED', 'Access denied');
      return (
        path.endsWith('/columns')
          ? {
              manifest,
              items: [0, 1].map((i) => ({
                output_position: i,
                source_field_index: i,
                source_path: [],
                source_type: null,
                header_cells: [],
              })),
              total: 2,
              page: 1,
              page_size: 25,
              pages: 1,
              has_next: false,
              has_previous: false,
            }
          : manifest
      ) as T;
    },
  );
  await state.open(target);
  await state.choose('columns');
  expect(state.columnsPage()?.items).toHaveLength(2);
  expect(calls[1].path).toBe('/tenants/north/datasets/dataset/tables/table/coordinates/columns');
  expect(calls[1].options?.query).toEqual({ snapshot_id: 'selected', page: 1, page_size: 25 });
  deny = true;
  await state.choose('rows');
  expect(state.manifest()).toBeNull();
  expect(state.columnsPage()).toBeNull();
  expect(state.error()).toBe('Access denied');
  expect(facade.authRequired()).toBe(false);
});
