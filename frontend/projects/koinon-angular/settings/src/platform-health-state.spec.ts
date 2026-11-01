// Copyright 2026 Firefly Software Foundation
// SPDX-License-Identifier: Apache-2.0
import { TestBed } from '@angular/core/testing';
import {
  KoinonFacade,
  KoinonClientContext,
  provideKoinonClient,
} from '@fireflyframework/koinon-angular';
import {
  KoinonClient,
  KoinonError,
  type KoinonTransport,
  type HttpMethod,
  type RequestOptions,
} from '@fireflyframework/koinon-sdk';
import type {
  PlatformHealth,
  SystemInformation,
} from '@fireflyframework/koinon-sdk/platform-health';
import { KoinonPlatformHealthState } from './platform-health-state';

const health: PlatformHealth = {
  tenant_id: 'north',
  checked_at: '2026-11-01T09:00:00Z',
  components: [],
};
const information: SystemInformation = {
  tenant_id: 'north',
  checked_at: health.checked_at,
  components: [],
  serving_role: 'api',
  capabilities: {
    knowledge_enabled: true,
    mcp_enabled: true,
    communications_enabled: false,
    scheduled_consumers_enabled: false,
  },
  limits: [],
  artifacts: [],
};
function deferred<T>() {
  let resolve!: (value: T) => void;
  const promise = new Promise<T>((yes) => {
    resolve = yes;
  });
  return { promise, resolve };
}
function setup(request?: KoinonTransport['request']) {
  const calls: { method: HttpMethod; path: string; options?: RequestOptions }[] = [];
  const transport: KoinonTransport = {
    request:
      request ??
      (async <T>(method: HttpMethod, path: string, options?: RequestOptions) => {
        calls.push({ method, path, options });
        return (path.endsWith('/health') ? health : information) as T;
      }),
    stream: () => {
      throw new Error('Unexpected stream');
    },
  };
  TestBed.configureTestingModule({
    providers: [
      KoinonFacade,
      KoinonPlatformHealthState,
      ...provideKoinonClient(new KoinonClient({ transport }), transport),
    ],
  });
  const facade = TestBed.inject(KoinonFacade);
  facade.tenantId.set('north');
  facade.context.set({
    subject: 'alex',
    tenants: [
      { id: 'north', name: 'North', roles: ['admin'], permissions: ['catalog:read', 'audit:read'] },
      { id: 'south', name: 'South', roles: ['admin'], permissions: ['catalog:read', 'audit:read'] },
    ],
    memberships: ['north', 'south'].map((tenant_id) => ({
      id: tenant_id,
      subject: 'alex',
      tenant_id,
      workspace_id: null,
      role: 'admin',
      active: true,
    })),
    workspaces: [],
  });
  const state = TestBed.inject(KoinonPlatformHealthState);
  TestBed.tick();
  return { state, facade, calls, clients: TestBed.inject(KoinonClientContext), transport };
}
it('reads only passive health and system-information routes with abortable requests', async () => {
  const { state, calls } = setup();
  await state.loadHealth();
  await state.loadInformation();
  expect(calls.map((c) => [c.method, c.path])).toEqual([
    ['GET', '/tenants/north/platform/health'],
    ['GET', '/tenants/north/platform/system-information'],
  ]);
  expect(calls.every((c) => c.options?.signal instanceof AbortSignal)).toBe(true);
  expect(state.health()).toEqual(health);
  expect(state.information()).toEqual(information);
});
it('does not request reports for a viewer with an audit permission', async () => {
  const { state, facade, calls } = setup();
  facade.context.update((value) => ({
    ...value!,
    memberships: value!.memberships.map((grant) => ({ ...grant, role: 'viewer' })),
  }));
  await state.loadHealth();
  await state.loadInformation();
  expect(calls).toHaveLength(0);
  expect(state.allowed()).toBe(false);
});
it('masks data immediately when the organization administrator grant is revoked', async () => {
  const { state, facade } = setup();
  await state.loadHealth();
  await state.loadInformation();
  facade.context.update((value) => ({ ...value!, memberships: [] }));
  expect(state.health()).toBeNull();
  expect(state.information()).toBeNull();
  expect(state.allowed()).toBe(false);
});
it('aborts and discards a previous organization response', async () => {
  const pending = deferred<PlatformHealth>();
  let signal: AbortSignal | undefined;
  const { state, facade } = setup(
    <T>(_method: HttpMethod, _path: string, options?: RequestOptions) => {
      signal = options?.signal;
      return pending.promise as Promise<T>;
    },
  );
  const first = state.loadHealth();
  facade.tenantId.set('south');
  TestBed.tick();
  expect(signal?.aborted).toBe(true);
  pending.resolve(health);
  await first;
  expect(state.health()).toBeNull();
  expect(state.healthError()).toBe('');
});
it('rejects a report bound to another organization', async () => {
  const { state } = setup(async <T>() => ({ ...health, tenant_id: 'another-organization' }) as T);
  await state.loadHealth();
  expect(state.health()).toBeNull();
  expect(state.healthError()).toBe('Platform health could not be loaded.');
});
it('does not let an older same-organization read replace the newest result', async () => {
  const old = deferred<PlatformHealth>();
  let calls = 0;
  let aborted: AbortSignal | undefined;
  const { state } = setup(<T>(_method: HttpMethod, _path: string, options?: RequestOptions) => {
    if (++calls === 1) {
      aborted = options?.signal;
      return old.promise as Promise<T>;
    }
    return Promise.resolve({ ...health, checked_at: '2026-11-01T10:00:00Z' } as T);
  });
  const first = state.loadHealth();
  await state.loadHealth();
  old.resolve(health);
  await first;
  expect(aborted?.aborted).toBe(true);
  expect(state.health()?.checked_at).toBe('2026-11-01T10:00:00Z');
});
it('invalidates a report when the host replaces the SDK client', async () => {
  const { state, clients, transport } = setup();
  await state.loadHealth();
  clients.bind(new KoinonClient({ transport }), transport);
  expect(state.health()).toBeNull();
});
it('clears both reports on a server access denial without rendering its raw error', async () => {
  let denied = false;
  const { state, facade } = setup(async <T>(_method: HttpMethod, path: string) => {
    if (denied)
      throw new KoinonError(403, 'DENIED', 'postgresql://secret@internal.example/private');
    return (path.endsWith('/health') ? health : information) as T;
  });
  await state.loadHealth();
  await state.loadInformation();
  denied = true;
  await state.loadHealth();
  expect(state.health()).toBeNull();
  expect(state.information()).toBeNull();
  expect(state.allowed()).toBe(false);
  expect(facade.authRequired()).toBe(false);
  expect(state.accessError()).toBe('Current organization administrator access is required.');
});
it('sends only an unauthorized session to the sign-in flow', async () => {
  const { state, facade } = setup(async () => {
    throw new KoinonError(401, 'UNAUTHENTICATED', 'private raw message');
  });
  await state.loadInformation();
  expect(facade.authRequired()).toBe(true);
  expect(state.information()).toBeNull();
});
it('aborts pending reads and removes results when the section is destroyed', async () => {
  const pending = deferred<PlatformHealth>();
  let aborted: AbortSignal | undefined;
  const { state } = setup(<T>(_method: HttpMethod, _path: string, options?: RequestOptions) => {
    aborted = options?.signal;
    return pending.promise as Promise<T>;
  });
  const first = state.loadHealth();
  state.ngOnDestroy();
  pending.resolve(health);
  await first;
  expect(aborted?.aborted).toBe(true);
  expect(state.health()).toBeNull();
});
it('does not start another request after the section has been destroyed', async () => {
  const { state, calls } = setup();
  state.ngOnDestroy();
  await state.loadHealth();
  await state.loadInformation();
  expect(calls).toHaveLength(0);
  expect(state.allowed()).toBe(false);
});
it('expires administrator access while an open report remains on screen', async () => {
  vi.useFakeTimers();
  try {
    const { state, facade } = setup();
    facade.context.update((value) => ({
      ...value!,
      memberships: value!.memberships.map((grant) => ({
        ...grant,
        expires_at: new Date(Date.now() + 500).toISOString(),
      })),
    }));
    await state.loadHealth();
    TestBed.tick();
    expect(state.health()).not.toBeNull();
    vi.advanceTimersByTime(501);
    TestBed.tick();
    expect(state.allowed()).toBe(false);
    expect(state.health()).toBeNull();
  } finally {
    vi.useRealTimers();
  }
});
it('updates the observation clock when evidence expires without making another request', async () => {
  vi.useFakeTimers();
  try {
    const expires = Date.now() + 500;
    const { state } = setup(
      async <T>() =>
        ({
          ...health,
          components: [
            {
              id: 'database-primary',
              configured: true,
              status: 'passed',
              basis: 'observed',
              freshness: 'current',
              observed_at: new Date(Date.now() - 1000).toISOString(),
              expires_at: new Date(expires).toISOString(),
              reason: 'DATABASE_OK',
              remediation: 'none',
              coverage: 'complete',
            },
          ],
        }) as T,
    );
    await state.loadHealth();
    TestBed.tick();
    expect(state.now()).toBeLessThan(expires);
    vi.advanceTimersByTime(501);
    TestBed.tick();
    expect(state.now()).toBeGreaterThanOrEqual(expires);
    expect(state.health()).not.toBeNull();
  } finally {
    vi.useRealTimers();
  }
});
