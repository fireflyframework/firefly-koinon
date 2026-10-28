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
import { KoinonTableLineage } from './table-lineage';
const target = {
  datasetId: 'dataset',
  tableId: 'table',
  datasetName: 'Sales',
  tableName: 'Orders',
};
const summary = {
  dataset_id: 'dataset',
  table_id: 'table',
  native_dataset_id: 'native-dataset',
  native_table_id: 'native-table',
  snapshot_id: 'old',
  status: 'not_recorded',
  snapshot_status: 'READY',
  level: 'file_section',
};
const history = {
  items: [summary],
  total: 27,
  page: 1,
  page_size: 25,
  pages: 2,
  has_next: true,
  has_previous: false,
  current_snapshot_id: 'current',
};
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
      KoinonTableLineage,
      { provide: KoinonFacade, useValue: facade },
      { provide: KoinonClientContext, useValue: clients },
    ],
  });
  return { state: TestBed.inject(KoinonTableLineage), facade, clients };
}
it('reads bounded server history then only the exact selected version, without substituting current metadata', async () => {
  const calls: { path: string; options?: RequestOptions }[] = [];
  const { state } = setup(async <T>(method: unknown, path: string, options?: RequestOptions) => {
    expect(method).toBe('GET');
    calls.push({ path, options });
    return (path.endsWith('/snapshots') ? history : summary) as T;
  });
  await state.open(target);
  expect(calls).toHaveLength(1);
  expect(calls[0].options?.query).toEqual({ page: 1, page_size: 25 });
  expect(state.history()?.total).toBe(27);
  await state.selectVersion('old');
  expect(calls[1].path).toBe('/tenants/north/datasets/dataset/tables/table/provenance');
  expect(calls[1].options?.query).toEqual({ snapshot_id: 'old' });
  expect(state.detail()?.status).toBe('not_recorded');
  expect(state.detail()?.artifact).toBeUndefined();
  expect(state.isCurrent()).toBe(false);
});
it('forwards server pagination and rejects a foreign or mismatched returned version', async () => {
  const { state } = setup(async <T>(_method: unknown, path: string, options?: RequestOptions) => {
    if (path.endsWith('/snapshots')) return { ...history, page: options?.query?.['page'] } as T;
    return {
      ...summary,
      snapshot_id: 'different',
      artifact: { original_filename: 'foreign.xlsx' },
    } as T;
  });
  await state.open(target);
  await state.goToPage(2);
  expect(state.history()?.page).toBe(2);
  await state.selectVersion('old');
  expect(state.detail()).toBeNull();
  expect(state.error()).toContain('requested');
});
it('immediately hides stale data and ignores pending responses after identity refresh or close', async () => {
  let finish!: (value: unknown) => void;
  let pendingSignal!: AbortSignal;
  const { state, facade } = setup(
    <T>(_method: unknown, _path: string, options?: RequestOptions) => {
      pendingSignal = options!.signal!;
      return new Promise<T>((resolve) => {
        finish = (value) => resolve(value as T);
      });
    },
  );
  const pending = state.open(target);
  facade.context.set({ subject: 'owner' });
  expect(state.target()).toBeNull();
  expect(state.history()).toBeNull();
  TestBed.tick();
  expect(pendingSignal.aborted).toBe(true);
  finish(history);
  await pending;
  expect(state.history()).toBeNull();
});
it('does not read without catalog permission and hides data on client identity changes', async () => {
  let calls = 0;
  const { state, facade, clients } = setup(async <T>() => {
    calls++;
    return history as T;
  });
  facade.permissions.set(new Set());
  await state.open(target);
  expect(calls).toBe(0);
  expect(state.target()).toBeNull();
  facade.permissions.set(new Set(['catalog:read']));
  await state.open(target);
  clients.revision.update((value) => value + 1);
  expect(state.history()).toBeNull();
  TestBed.tick();
  expect(state.target()).toBeNull();
});
it('keeps permission failures actionable and expires the session only on authentication failure', async () => {
  let status = 403;
  const { state, facade } = setup(async () => {
    throw new KoinonError(status, 'DENIED', 'Access denied');
  });
  await state.open(target);
  expect(state.error()).toBe('Access denied');
  expect(facade.authRequired()).toBe(false);
  status = 401;
  await state.retry();
  expect(facade.authRequired()).toBe(true);
  expect(state.history()).toBeNull();
  expect(state.target()).toBeNull();
});
it('discards an earlier version request when another version is selected', async () => {
  let finish!: (value: unknown) => void;
  const { state } = setup(<T>(_method: unknown, path: string, options?: RequestOptions) => {
    if (path.endsWith('/snapshots')) return Promise.resolve(history as T);
    if (options?.query?.['snapshot_id'] === 'old')
      return new Promise<T>((resolve) => {
        finish = (value) => resolve(value as T);
      });
    return Promise.resolve({ ...summary, snapshot_id: 'current' } as T);
  });
  await state.open(target);
  const old = state.selectVersion('old');
  await state.selectVersion('current');
  expect(state.isCurrent()).toBe(true);
  finish(summary);
  await old;
  expect(state.detail()?.snapshot_id).toBe('current');
  state.close();
  expect(state.detail()).toBeNull();
});
