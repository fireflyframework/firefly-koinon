// Copyright 2026 Firefly Software Foundation
// SPDX-License-Identifier: Apache-2.0
import { TestBed } from '@angular/core/testing';
import {
  KoinonClient,
  KoinonError,
  type KoinonTransport,
  type McpOAuthClient,
  type McpOAuthClientInput,
  type McpOAuthClientReadiness,
  type HttpMethod,
  type RequestOptions,
} from '@fireflyframework/koinon-sdk';
import {
  KoinonFacade,
  KoinonClientContext,
  provideKoinonClient,
} from '@fireflyframework/koinon-angular';
import { KoinonMcpApplicationsState } from './mcp-applications-state';

const row: McpOAuthClient = {
  id: 'registration-one',
  tenant_id: 'tenant-one',
  client_id: 'koinon_org_one',
  name: 'Research desktop',
  client_type: 'confidential',
  enabled: true,
  revision: 3,
  redirect_uris: ['https://desktop.example.test/callback'],
  scopes: ['catalog:read'],
  created_at: '2026-10-29T10:00:00Z',
  updated_at: '2026-10-29T11:00:00Z',
  created_by: 'issuer|admin',
  updated_by: 'issuer|admin',
};
const ready: McpOAuthClientReadiness = {
  ready: true,
  endpoint_enabled: true,
  oauth_enabled: true,
  encryption_configured: true,
  missing_configuration: [],
  static_clients_read_only: true,
};
const input: McpOAuthClientInput = {
  name: row.name,
  redirect_uris: row.redirect_uris,
  scopes: row.scopes,
  client_type: 'confidential',
};
function page(items: McpOAuthClient[] = [row], current = 1) {
  return { items, page: current, page_size: 25, pages: 2, total: 26 };
}
function deferred<T>() {
  let resolve!: (value: T) => void;
  let reject!: (reason: unknown) => void;
  const promise = new Promise<T>((yes, no) => {
    resolve = yes;
    reject = no;
  });
  return { promise, resolve, reject };
}
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
      KoinonMcpApplicationsState,
      ...provideKoinonClient(new KoinonClient({ transport }), transport),
    ],
  });
  const facade = TestBed.inject(KoinonFacade);
  facade.context.set({
    subject: 'issuer|admin',
    tenants: [
      { id: 'tenant-one', name: 'Research', roles: ['admin'], permissions: ['identity:manage'] },
    ],
    memberships: [],
    workspaces: [],
  });
  facade.tenantId.set('tenant-one');
  const state = TestBed.inject(KoinonMcpApplicationsState);
  TestBed.tick();
  return { state, facade };
}
function response<T>(path: string): T {
  return (
    path.endsWith('/readiness') ? ready : path.endsWith('/registration-one') ? row : page()
  ) as T;
}
async function loaded(request?: KoinonTransport['request']) {
  const values = setup(
    request ?? (async <T>(_method: HttpMethod, path: string) => response<T>(path)),
  );
  await values.state.reload();
  await values.state.open(row.id);
  return values;
}

describe('organization OAuth application state', () => {
  it('retains a one-time secret without filter, reload or write requests until explicit dismissal', async () => {
    let calls = 0;
    const { state } = await loaded(async <T>(method: HttpMethod, path: string) => {
      calls++;
      return method === 'POST'
        ? ({ client: row, client_secret: 'owned-synthetic-secret' } as T)
        : response<T>(path);
    });
    await state.create(input, state.identity());
    const credential = state.secret(),
      before = calls;
    expect(await state.load({ q: 'Changed filter' })).toBeNull();
    expect(await state.reload()).toBe(false);
    expect(await state.create(input, state.identity())).toBeNull();
    expect(state.secret()).toBe(credential);
    expect(calls).toBe(before);
    state.dismissSecret();
    expect(await state.load()).not.toBeNull();
    expect(calls).toBe(before + 1);
  });
  it('uses identity administration authority rather than unrelated settings access', async () => {
    let calls = 0;
    const { state, facade } = setup(async <T>(_method: HttpMethod, path: string) => {
      calls++;
      return response<T>(path);
    });
    expect(state.allowed()).toBe(true);
    facade.context.set({
      ...facade.context()!,
      tenants: [{ ...facade.context()!.tenants[0], permissions: ['settings:write'] }],
    });
    await state.reload();
    expect(state.allowed()).toBe(false);
    expect(calls).toBe(0);
  });
  it('rejects obsolete captured revisions without silently rebasing an edit', async () => {
    let writes = 0;
    const { state } = await loaded(async <T>(method: HttpMethod, path: string) => {
      if (method !== 'GET') writes++;
      return response<T>(path);
    });
    expect(
      await state.update(row.id, { expected_revision: 2, name: 'Old form' }, state.identity()),
    ).toBeNull();
    expect(await state.disable(row.id, state.identity(), 2)).toBeNull();
    expect(await state.rotateSecret(row.id, state.identity(), 2)).toBeNull();
    expect(writes).toBe(0);
  });
  it('rejects a successful response for a different registration without exposing its secret', async () => {
    const { state } = await loaded(async <T>(method: HttpMethod, path: string) =>
      method === 'POST'
        ? ({
            client: { ...row, id: 'different-registration' },
            client_secret: 'owned-synthetic-secret',
          } as T)
        : response<T>(path),
    );
    expect(await state.rotateSecret(row.id, state.identity(), 3)).toBeNull();
    expect(state.secret()).toBeNull();
    expect(state.stale()).toBe(true);
    expect(state.notice()).toBe('');
  });
  it('keeps one mutation in flight and does not load over its pending response', async () => {
    const pending = deferred<unknown>();
    let writes = 0;
    const { state } = await loaded(<T>(method: HttpMethod, path: string) => {
      if (method === 'POST') {
        writes++;
        return pending.promise as Promise<T>;
      }
      return Promise.resolve(response<T>(path));
    });
    const writing = state.create(input, state.identity());
    expect(await state.create(input, state.identity())).toBeNull();
    expect(await state.load()).toBeNull();
    pending.resolve({ client: row, client_secret: 'owned-synthetic-secret' });
    await writing;
    expect(writes).toBe(1);
    expect(state.secret()?.client_secret).toBe('owned-synthetic-secret');
  });
  it('clears an issued secret when the component is destroyed and ignores subsequent work', async () => {
    const { state } = await loaded(async <T>(method: HttpMethod, path: string) =>
      method === 'POST'
        ? ({ client: row, client_secret: 'owned-synthetic-secret' } as T)
        : response<T>(path),
    );
    await state.create(input, state.identity());
    expect(state.secret()).not.toBeNull();
    state.ngOnDestroy();
    expect(state.secret()).toBeNull();
    expect(state.canWrite()).toBe(false);
    expect(await state.create(input, state.identity())).toBeNull();
  });
  it('uses server pagination and supported filters without inventing totals', async () => {
    const requests: RequestOptions[] = [];
    const { state } = setup(
      async <T>(_method: HttpMethod, path: string, options?: RequestOptions) => {
        if (!path.endsWith('/readiness')) requests.push(options ?? {});
        return (path.endsWith('/readiness') ? ready : page([row], 2)) as T;
      },
    );
    await state.load({ q: ' Research ', page: 2, status: 'enabled' });
    expect(requests[0].query).toMatchObject({
      q: 'Research',
      page: 2,
      page_size: 25,
      status: 'enabled',
    });
    expect(state.page().total).toBe(26);
    expect(state.page().page).toBe(2);
  });
  it('aborts and discards an older list when filters change', async () => {
    const first = deferred<ReturnType<typeof page>>(),
      second = deferred<ReturnType<typeof page>>();
    const signals: (AbortSignal | undefined)[] = [];
    const { state } = setup(<T>(_method: HttpMethod, _path: string, options?: RequestOptions) => {
      signals.push(options?.signal);
      return (signals.length === 1 ? first.promise : second.promise) as Promise<T>;
    });
    const old = state.load({ q: 'old' }),
      latest = state.load({ q: 'new' });
    expect(signals[0]?.aborted).toBe(true);
    second.resolve(page([{ ...row, name: 'Current application' }]));
    await latest;
    first.resolve(page());
    await old;
    expect(state.page().items[0].name).toBe('Current application');
  });
  it('discards old readiness after a tenant switch even before an effect flush', async () => {
    const pending = deferred<McpOAuthClientReadiness>();
    const { state, facade } = setup(<T>() => pending.promise as Promise<T>);
    const loading = state.loadReadiness();
    facade.tenantId.set('tenant-two');
    pending.resolve(ready);
    await loading;
    TestBed.tick();
    expect(state.readiness()).toBeNull();
    expect(state.canWrite()).toBe(false);
  });
  it('discards a detail from the previous bound client', async () => {
    const pending = deferred<McpOAuthClient>();
    const { state } = setup(<T>(_method: HttpMethod, path: string) =>
      path.endsWith('/registration-one')
        ? (pending.promise as Promise<T>)
        : Promise.resolve(response<T>(path)),
    );
    await state.reload();
    const opening = state.open(row.id);
    TestBed.inject(KoinonClientContext).bind(
      new KoinonClient({
        transport: {
          request: async <T>() => page([]) as T,
          stream: () => {
            throw new Error('Unexpected stream');
          },
        },
      }),
    );
    pending.resolve(row);
    await opening;
    TestBed.tick();
    expect(state.detail()).toBeNull();
    expect(state.error()).toBe('');
  });
  it('requires the form identity captured before tenant or subject changes', async () => {
    let writes = 0;
    const { state, facade } = await loaded(async <T>(method: HttpMethod, path: string) => {
      if (method !== 'GET') writes++;
      return response<T>(path);
    });
    const identity = state.identity();
    facade.context.set({ ...facade.context()!, subject: 'issuer|different' });
    expect(await state.create(input, identity)).toBeNull();
    expect(
      await state.update(row.id, { name: 'Changed', expected_revision: 3 }, identity),
    ).toBeNull();
    expect(await state.disable(row.id, identity, 3)).toBeNull();
    expect(await state.rotateSecret(row.id, identity, 3)).toBeNull();
    expect(writes).toBe(0);
  });
  it('uses only the current detail revision when editing and disabling', async () => {
    const bodies: unknown[] = [];
    const { state } = await loaded(
      async <T>(method: HttpMethod, path: string, options?: RequestOptions) => {
        if (method === 'PATCH') {
          bodies.push(options?.body);
          return { ...row, revision: 4, enabled: false } as T;
        }
        return response<T>(path);
      },
    );
    expect(
      await state.update('other', { name: 'Changed', expected_revision: 3 }, state.identity()),
    ).toBeNull();
    expect(await state.disable(row.id, state.identity(), 3)).toMatchObject({
      enabled: false,
      revision: 4,
    });
    expect(bodies).toEqual([{ enabled: false, expected_revision: 3 }]);
    expect(state.notice()).toContain('Existing connections');
  });
  it('keeps a newly generated secret only in memory until explicitly dismissed', async () => {
    const { state } = await loaded(async <T>(method: HttpMethod, path: string) =>
      method === 'POST'
        ? ({ client: { ...row, revision: 4 }, client_secret: 'owned-synthetic-secret' } as T)
        : response<T>(path),
    );
    expect(await state.rotateSecret(row.id, state.identity(), 3)).toMatchObject({ revision: 4 });
    expect(state.secret()?.client_secret).toBe('owned-synthetic-secret');
    expect(state.secret()?.client.revision).toBe(4);
    expect(state.page().items).toEqual([]);
    state.dismissSecret();
    expect(state.secret()).toBeNull();
  });
  it('clears a secret on tenant change and destroy', async () => {
    const { state, facade } = await loaded(async <T>(method: HttpMethod, path: string) =>
      method === 'POST'
        ? ({ client: row, client_secret: 'owned-synthetic-secret' } as T)
        : response<T>(path),
    );
    await state.create(input, state.identity());
    expect(state.secret()).not.toBeNull();
    facade.tenantId.set('tenant-two');
    TestBed.tick();
    expect(state.secret()).toBeNull();
    state.ngOnDestroy();
    expect(state.secret()).toBeNull();
  });
  it('cannot reveal a late credential response to a different identity', async () => {
    const pending = deferred<unknown>();
    const { state, facade } = await loaded(<T>(method: HttpMethod, path: string) =>
      method === 'POST' ? (pending.promise as Promise<T>) : Promise.resolve(response<T>(path)),
    );
    const writing = state.create(input, state.identity());
    facade.tenantId.set('tenant-two');
    pending.resolve({ client: row, client_secret: 'owned-synthetic-secret' });
    expect(await writing).toBeNull();
    TestBed.tick();
    expect(state.secret()).toBeNull();
    expect(state.notice()).toBe('');
  });
  it('fences an uncertain creation and never automatically retries the write', async () => {
    let writes = 0;
    const { state } = await loaded(async <T>(method: HttpMethod, path: string) => {
      if (method === 'POST') {
        writes++;
        throw new TypeError('Synthetic lost response');
      }
      return response<T>(path);
    });
    expect(await state.create(input, state.identity())).toBeNull();
    expect(state.stale()).toBe(true);
    expect(state.canWrite()).toBe(false);
    expect(state.notice()).toBe('');
    expect(state.error()).toContain('Reload');
    expect(await state.create(input, state.identity())).toBeNull();
    expect(writes).toBe(1);
    await state.reload();
    expect(state.stale()).toBe(false);
    expect(state.canWrite()).toBe(true);
  });
  it('marks a revision conflict for reload and clears the obsolete record', async () => {
    const { state } = await loaded(async <T>(method: HttpMethod, path: string) => {
      if (method === 'PATCH') throw new KoinonError(409, 'REVISION_CONFLICT', 'Changed');
      return response<T>(path);
    });
    expect(
      await state.update(row.id, { name: 'Changed', expected_revision: 3 }, state.identity()),
    ).toBeNull();
    expect(state.stale()).toBe(true);
    expect(state.detail()).toBeNull();
    expect(state.error()).toContain('Reload');
    expect(state.notice()).toBe('');
  });
  it('requires sign-in on a current unauthorized response and never announces success', async () => {
    const { state, facade } = setup(async () => {
      throw new KoinonError(401, 'AUTH_REQUIRED', 'Sign in');
    });
    await state.loadReadiness();
    expect(facade.authRequired()).toBe(true);
    expect(state.notice()).toBe('');
  });
  it('allows preconfiguration before activation but still requires current identity authority', async () => {
    let writes = 0;
    const { state, facade } = await loaded(async <T>(method: HttpMethod, path: string) => {
      if (method !== 'GET') {
        writes++;
        return { client: row, client_secret: null } as T;
      }
      return (
        path.endsWith('/readiness')
          ? { ...ready, ready: false, missing_configuration: ['oauth_encryption_key'] }
          : response<T>(path)
      ) as T;
    });
    expect(await state.create(input, state.identity())).toEqual(row);
    facade.context.set({ ...facade.context()!, tenants: [] });
    expect(await state.rotateSecret(row.id, state.identity(), 3)).toBeNull();
    expect(writes).toBe(1);
  });
});
