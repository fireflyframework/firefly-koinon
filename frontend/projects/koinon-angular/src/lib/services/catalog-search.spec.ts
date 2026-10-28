// Copyright 2026 Firefly Software Foundation
// SPDX-License-Identifier: Apache-2.0
import { signal } from '@angular/core';
import { TestBed } from '@angular/core/testing';
import {
  KoinonClient,
  KoinonError,
  type CatalogEntry,
  type KoinonTransport,
  type RequestOptions,
} from '@fireflyframework/koinon-sdk';
import { KoinonFacade } from '../koinon-facade';
import { KoinonClientContext } from './client-context';
import { KoinonCatalogSearch } from './catalog-search';
function entry(id = 'policy'): CatalogEntry {
  return {
    id,
    name: id,
    kind: 'document',
    tenant_id: 'north',
    workspace_id: 'space',
    project_id: 'project',
    parent_id: 'source',
    description: '',
    status: 'ready',
    metadata: {},
    created_at: '2026-10-27',
  };
}
function setup(request: KoinonTransport['request']) {
  const facade = {
    tenantId: signal('north'),
    workspaceId: signal('space'),
    projectId: signal('project'),
    permissions: signal(new Set(['catalog:read'])),
    authRequired: signal(false),
    context: signal({ subject: 'issuer|admin', tenants: [], workspaces: [] }),
    entries: signal([]),
  };
  const transport: KoinonTransport = {
    request,
    stream: () => {
      throw Error('Unexpected model stream');
    },
  };
  const clients = { get: () => new KoinonClient({ transport }), revision: signal(0) };
  TestBed.configureTestingModule({
    providers: [
      KoinonCatalogSearch,
      { provide: KoinonFacade, useValue: facade },
      { provide: KoinonClientContext, useValue: clients },
    ],
  });
  return { search: TestBed.inject(KoinonCatalogSearch), facade, clients };
}
const settle = async () => {
  TestBed.tick();
  await vi.advanceTimersByTimeAsync(250);
  TestBed.tick();
};
afterEach(() => vi.useRealTimers());
it('debounces real scoped catalog requests and preserves observed totals', async () => {
  vi.useFakeTimers();
  const calls: RequestOptions[] = [];
  const { search } = setup(async <T>(method: unknown, path: string, options?: RequestOptions) => {
    expect(method).toBe('GET');
    expect(path).toBe('/tenants/north/catalog');
    calls.push(options!);
    return { items: [entry()], total: 43, page: 1, page_size: 8, pages: 6 } as T;
  });
  search.setOpen(true);
  search.setQuery('pol');
  TestBed.tick();
  await vi.advanceTimersByTimeAsync(200);
  expect(calls).toHaveLength(0);
  expect(search.pending()).toBe(true);
  search.setQuery('policy');
  await settle();
  expect(calls).toHaveLength(1);
  expect(calls[0].query).toEqual({
    q: 'policy',
    workspace_id: 'space',
    project_id: 'project',
    view: 'library',
    page: 1,
    page_size: 8,
    sort: 'name',
    order: 'asc',
  });
  expect(calls[0].signal).toBeInstanceOf(AbortSignal);
  expect(search.page().total).toBe(43);
});
it('aborts and hides stale scope responses even when the transport ignores abort', async () => {
  vi.useFakeTimers();
  let complete!: (value: unknown) => void;
  let previous!: AbortSignal;
  const { search, facade } = setup(
    <T>(_method: unknown, _path: string, options?: RequestOptions) => {
      previous = options!.signal!;
      return new Promise<T>((resolve) => {
        complete = resolve as (value: unknown) => void;
      });
    },
  );
  search.setOpen(true);
  search.setQuery('policy');
  await settle();
  facade.tenantId.set('south');
  expect(search.page().items).toEqual([]);
  TestBed.tick();
  expect(previous.aborted).toBe(true);
  complete({ items: [entry()], total: 99, page: 1, pages: 13 });
  await Promise.resolve();
  expect(search.page().items).toEqual([]);
  expect(search.page().total).toBeUndefined();
});
it('fences visible entries on principal, project and client changes and cancels on close', async () => {
  vi.useFakeTimers();
  let requestSignal!: AbortSignal;
  const { search, facade, clients } = setup(
    async <T>(_method: unknown, _path: string, options?: RequestOptions) => {
      requestSignal = options!.signal!;
      return { items: [entry()], page: 1, pages: 1 } as T;
    },
  );
  search.setOpen(true);
  search.setQuery('policy');
  await settle();
  const resource = search.page().items[0];
  expect(search.isCurrent(resource)).toBe(true);
  facade.context.set({ ...facade.context(), subject: 'issuer|other' });
  expect(search.isCurrent(resource)).toBe(false);
  facade.projectId.set('other-project');
  expect(search.page().items).toEqual([]);
  TestBed.tick();
  clients.revision.update((x) => x + 1);
  TestBed.tick();
  search.setOpen(false);
  TestBed.tick();
  expect(requestSignal.aborted).toBe(true);
  await vi.advanceTimersByTimeAsync(500);
  expect(search.page().items).toEqual([]);
});
it('requests only selected server pages without inventing totals or crawling the catalog', async () => {
  vi.useFakeTimers();
  const pages: number[] = [];
  const { search } = setup(async <T>(_method: unknown, _path: string, options?: RequestOptions) => {
    const page = Number(options!.query!['page']);
    pages.push(page);
    return { items: [entry('page-' + page)], page, page_size: 8, pages: 20, total: 153 } as T;
  });
  search.setOpen(true);
  search.setQuery('page');
  await settle();
  await search.goToPage(2);
  expect(pages).toEqual([1, 2]);
  expect(search.page().total).toBe(153);
  await search.goToPage(100);
  expect(pages).toEqual([1, 2]);
  search.setQuery('new');
  expect(search.page().items).toEqual([]);
  await settle();
  expect(pages).toEqual([1, 2, 1]);
});
it('does not search without current tenant, catalog permission, query or open state', async () => {
  vi.useFakeTimers();
  const request = vi.fn();
  const { search, facade } = setup(request);
  search.setQuery('policy');
  await settle();
  expect(request).not.toHaveBeenCalled();
  search.setOpen(true);
  facade.permissions.set(new Set());
  await settle();
  expect(request).not.toHaveBeenCalled();
  facade.permissions.set(new Set(['catalog:read']));
  facade.tenantId.set('');
  await settle();
  expect(request).not.toHaveBeenCalled();
});
it('surfaces current failures, propagates401 and rejects out-of-scope response items', async () => {
  vi.useFakeTimers();
  let mode = 403;
  const { search, facade } = setup(async <T>() => {
    if (mode === 200)
      return { items: [{ ...entry(), tenant_id: 'south' }], page: 1, pages: 1 } as T;
    throw new KoinonError(mode, 'DENIED', 'Search is denied');
  });
  search.setOpen(true);
  search.setQuery('policy');
  await settle();
  expect(search.error()).toBe('Search is denied');
  mode = 200;
  await search.retry();
  expect(search.page().items).toEqual([]);
  expect(search.error()).toContain('current scope');
  mode = 401;
  await search.retry();
  expect(facade.authRequired()).toBe(true);
  expect(search.page().items).toEqual([]);
});
