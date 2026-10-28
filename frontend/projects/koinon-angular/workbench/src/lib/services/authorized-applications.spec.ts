// Copyright 2026 Firefly Software Foundation SPDX-License-Identifier: Apache-2.0
import { TestBed } from '@angular/core/testing';
import {
  KoinonClient,
  type KoinonTransport,
  type HttpMethod,
  type RequestOptions,
  type AuthorizedApplication,
} from '@fireflyframework/koinon-sdk';
import { provideKoinonClient } from '../client-provider';
import { KoinonFacade } from '../koinon-facade';
import { KoinonClientContext } from './client-context';
import { KoinonAuthorizedApplications, applicationLifecycle } from './authorized-applications';

const application: AuthorizedApplication = {
  id: 'app-one',
  client_id: 'research-client',
  name: 'Research desktop',
  resource: 'https://knowledge.example.test/mcp',
  tenant_id: 'tenant-one',
  tenant_name: 'Knowledge operations',
  workspace_id: 'workspace-one',
  workspace_name: 'Research operations',
  scopes: ['catalog:read', 'knowledge:search'],
  status: 'active',
  connected_at: '2026-10-26T09:00:00Z',
  expires_at: '2026-11-26T09:00:00Z',
  last_used_at: '2026-10-28T10:23:49Z',
  revoked_at: null,
};
function setup(request: KoinonTransport['request']) {
  const transport: KoinonTransport = {
    request,
    stream: () => {
      throw new Error('Unexpected stream');
    },
  };
  TestBed.configureTestingModule({
    providers: [
      KoinonFacade,
      KoinonAuthorizedApplications,
      ...provideKoinonClient(new KoinonClient({ transport }), transport),
    ],
  });
  return TestBed.inject(KoinonAuthorizedApplications);
}
function nextClient(request: KoinonTransport['request']) {
  TestBed.inject(KoinonClientContext).bind(
    new KoinonClient({
      transport: {
        request,
        stream: () => {
          throw new Error('Unexpected stream');
        },
      },
    }),
  );
  TestBed.tick();
}

describe('authorized application account state', () => {
  it('shows known expiry without changing a revoked lifecycle or inventing a renewal', () => {
    const now = Date.parse('2026-11-26T10:00:00Z');
    expect(applicationLifecycle(application, now)).toBe('expired');
    expect(applicationLifecycle({ ...application, status: 'revoked' }, now)).toBe('revoked');
    expect(applicationLifecycle(application, Date.parse('2026-11-26T08:00:00Z'))).toBe('active');
  });
  it('passes bounded server filters and gets the application detail through the typed SDK', async () => {
    const requests: { method: string; path: string; query: unknown }[] = [];
    const state = setup(async <T>(method: HttpMethod, path: string, options?: RequestOptions) => {
      requests.push({ method, path, query: options?.query });
      return (
        path.endsWith('/app-one')
          ? application
          : {
              items: [application],
              total: 31,
              page: 2,
              page_size: 25,
              pages: 2,
            }
      ) as T;
    });
    await state.load({ q: ' Research ', status: 'active', page: 2, sort: 'name', order: 'asc' });
    expect(state.page().total).toBe(31);
    expect(state.page().items).toHaveLength(1);
    expect(requests[0].query).toEqual({
      q: 'Research',
      status: 'active',
      page: 2,
      page_size: 25,
      sort: 'name',
      order: 'asc',
    });
    await state.open('app-one');
    expect(state.detail()).toEqual(application);
    expect(requests.map((value) => value.path)).toEqual([
      '/authorized-applications',
      '/authorized-applications/app-one',
    ]);
  });
  it('uses recorded lifecycle data after revoke and never fabricates a timestamp', async () => {
    let revoked = false;
    const methods: string[] = [];
    const state = setup(async <T>(method: HttpMethod, path: string) => {
      methods.push(method);
      if (method === 'DELETE') {
        revoked = true;
        return undefined as T;
      }
      const row = {
        ...application,
        status: revoked ? 'revoked' : 'active',
        revoked_at: revoked ? '2026-10-28T11:00:00Z' : null,
      };
      return (
        path.endsWith('/app-one')
          ? row
          : { items: [row], total: 1, page: 1, page_size: 25, pages: 1 }
      ) as T;
    });
    await state.load();
    await state.open('app-one');
    expect(await state.revoke('app-one')).toBe(true);
    expect(state.detail()?.revoked_at).toBe('2026-10-28T11:00:00Z');
    expect(methods.filter((value) => value === 'DELETE')).toHaveLength(1);
    expect(state.notice()).toBe('Application access revoked.');
  });
  it('clears detail and ignores a list arriving after the host identity changes', async () => {
    let finish!: (value: unknown) => void;
    const state = setup(
      <T>() =>
        new Promise<T>((resolve) => {
          finish = resolve as (value: unknown) => void;
        }),
    );
    const pending = state.load();
    nextClient(async <T>() => ({ items: [] }) as T);
    finish({ items: [application], total: 1, page: 1, page_size: 25, pages: 1 });
    await pending;
    expect(state.page().items).toEqual([]);
    expect(state.detail()).toBeNull();
    expect(state.loaded()).toBe(false);
  });
  it('does not show a detail response or error from the previous client', async () => {
    let finish!: (value: unknown) => void;
    const state = setup(<T>(_method: HttpMethod, path: string) =>
      path.endsWith('/app-one')
        ? new Promise<T>((resolve) => {
            finish = resolve as (value: unknown) => void;
          })
        : Promise.resolve({
            items: [application],
            total: 1,
            page: 1,
            page_size: 25,
            pages: 1,
          } as T),
    );
    await state.load();
    const pending = state.open('app-one');
    nextClient(async <T>() => ({ items: [] }) as T);
    finish(application);
    await pending;
    expect(state.detail()).toBeNull();
    expect(state.error()).toBe('');
  });
  it('stale revoke completion cannot reload applications or announce success to a new client', async () => {
    let finish!: (value: void) => void;
    const state = setup(<T>(method: HttpMethod) =>
      method === 'DELETE'
        ? new Promise<T>((resolve) => {
            finish = resolve as (value: void) => void;
          })
        : Promise.resolve({
            items: [application],
            total: 1,
            page: 1,
            page_size: 25,
            pages: 1,
          } as T),
    );
    await state.load();
    const pending = state.revoke('app-one');
    let newCalls = 0;
    nextClient(async <T>() => {
      newCalls++;
      return { items: [] } as T;
    });
    finish();
    expect(await pending).toBe(false);
    expect(newCalls).toBe(0);
    expect(state.notice()).toBe('');
    expect(state.page().items).toEqual([]);
  });
  it('latest filter request wins when the server returns out of order', async () => {
    const pending: ((value: unknown) => void)[] = [];
    const state = setup(
      <T>() => new Promise<T>((resolve) => pending.push(resolve as (value: unknown) => void)),
    );
    const first = state.load({ q: 'old' }),
      second = state.load({ q: 'new' });
    pending[1]({
      items: [{ ...application, name: 'New result' }],
      total: 1,
      page: 1,
      page_size: 25,
      pages: 1,
    });
    await second;
    pending[0]({ items: [application], total: 1, page: 1, page_size: 25, pages: 1 });
    await first;
    expect(state.page().items[0].name).toBe('New result');
  });
});
