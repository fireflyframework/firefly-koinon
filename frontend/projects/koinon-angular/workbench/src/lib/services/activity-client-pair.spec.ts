// Copyright 2026 Firefly Software Foundation SPDX-License-Identifier: Apache-2.0
import { signal } from '@angular/core';
import { TestBed } from '@angular/core/testing';
import {
  KoinonClient,
  KoinonError,
  type KoinonTransport,
  type HttpMethod,
  type RequestOptions,
  type ActivitySummary,
  type Membership,
} from '@fireflyframework/koinon-sdk';
import {
  KoinonClientContext,
  KoinonFacade,
  provideKoinonClient,
} from '@fireflyframework/koinon-angular';
import { KoinonActivityPanel } from '../../../../activity/activity-panel';
function summary(count: number): ActivitySummary {
  const observed = { value: count, status: 'observed' as const };
  return {
    tenant_id: 'same',
    audience: 'personal',
    window: { start_at: '2026-10-01T00:00:00Z', end_at: '2026-10-02T00:00:00Z', time_zone: 'UTC' },
    coverage: { observed_since: null, complete_window: true },
    knowledge: { created: observed, updated: observed, consulted: observed },
    mcp: {
      requests: observed,
      tool_calls: observed,
      succeeded: observed,
      failed: observed,
      rejected: observed,
      average_duration_ms: observed,
      p95_duration_ms: observed,
    },
    models: {
      input_tokens: observed,
      output_tokens: observed,
      embedding_tokens: observed,
      cost: { amount: null, status: 'unavailable' },
    },
  };
}
function setup(a: KoinonTransport) {
  const facade = {
    context: signal<{ subject: string; memberships: Membership[] }>({
      subject: 'Alice',
      memberships: [],
    }),
    tenantId: signal('same'),
    workspaceId: signal(''),
    tenant: signal({ roles: ['viewer'] }),
    tenantPermissions: signal(new Set<string>()),
    authRequired: signal(false),
    entries: () => [],
  };
  const client = new KoinonClient({ transport: a });
  TestBed.configureTestingModule({
    providers: [
      ...provideKoinonClient(client, a),
      KoinonClientContext,
      { provide: KoinonFacade, useValue: facade },
    ],
  });
  return {
    fixture: TestBed.createComponent(KoinonActivityPanel),
    context: TestBed.inject(KoinonClientContext),
    facade,
  };
}
it('immediately hides activity on client-only actor switch and resumes only with the explicit matching transport pair', async () => {
  const calls: string[] = [];
  const transport = (owner: string): KoinonTransport => ({
    request: async <T>(_method: HttpMethod, path: string) => {
      calls.push(owner + path);
      return summary(owner === 'A' ? 9 : 2) as T;
    },
    stream: async function* () {
      yield* [];
    },
  });
  const a = transport('A'),
    b = transport('B'),
    { fixture, context, facade } = setup(a);
  fixture.detectChanges();
  await fixture.whenStable();
  expect(fixture.componentInstance.summary()?.knowledge.created.value).toBe(9);
  const before = calls.length;
  const clientB = new KoinonClient({ transport: b });
  context.bind(clientB);
  facade.context.set({ subject: 'Bob', memberships: [] });
  expect(fixture.componentInstance.summary()).toBeNull();
  fixture.detectChanges();
  await fixture.whenStable();
  expect(calls).toHaveLength(before);
  expect(fixture.componentInstance.error()).toContain('not connected');
  context.bind(clientB, b);
  fixture.detectChanges();
  await fixture.whenStable();
  expect(fixture.componentInstance.summary()?.knowledge.created.value).toBe(2);
  expect(calls.slice(before).every((value) => value.startsWith('B'))).toBe(true);
});
it('aborts and discards a previous actor response and rejects an invalid window without using the default', async () => {
  let resolve: (value: ActivitySummary) => void = () => {
    throw Error('not registered');
  };
  let signal: AbortSignal | undefined;
  let calls = 0;
  const a: KoinonTransport = {
    request: <T>(_method: HttpMethod, _path: string, options?: RequestOptions) => {
      calls++;
      signal = options?.signal;
      return new Promise<T>((done) => (resolve = (value) => done(value as T)));
    },
    stream: async function* () {
      yield* [];
    },
  };
  const { fixture, context } = setup(a);
  fixture.detectChanges();
  await vi.waitFor(() => expect(signal).toBeInstanceOf(AbortSignal));
  const b: KoinonTransport = {
    request: async <T>() => summary(2) as T,
    stream: async function* () {
      yield* [];
    },
  };
  context.bind(new KoinonClient({ transport: b }));
  TestBed.tick();
  expect(signal?.aborted).toBe(true);
  resolve(summary(9));
  await fixture.whenStable();
  expect(fixture.componentInstance.summary()).toBeNull();
  context.bind(new KoinonClient({ transport: a }), a);
  fixture.componentInstance.window = null;
  await fixture.componentInstance.load();
  expect(calls).toBe(1);
});

it('offers the organization audience only for a current organization administrator with both required permissions', () => {
  const a: KoinonTransport = {
    request: async <T>() => summary(1) as T,
    stream: async function* () {
      yield* [];
    },
  };
  const { fixture, facade } = setup(a);
  facade.tenant.set({ roles: ['admin'] });
  facade.tenantPermissions.set(new Set(['audit:read', 'activity:read']));
  facade.context.set({
    subject: 'Alice',
    memberships: [
      {
        id: 'm',
        tenant_id: 'same',
        subject: 'Alice',
        role: 'admin',
        active: true,
        workspace_id: 'workspace',
      },
    ],
  });
  expect(fixture.componentInstance.canAdmin()).toBe(false);
  facade.context.set({
    subject: 'Alice',
    memberships: [
      {
        id: 'm',
        tenant_id: 'same',
        subject: 'Alice',
        role: 'admin',
        active: true,
        workspace_id: null,
      },
    ],
  });
  expect(fixture.componentInstance.canAdmin()).toBe(true);
  facade.tenantPermissions.set(new Set(['audit:read']));
  expect(fixture.componentInstance.canAdmin()).toBe(false);
});

it('locks a personal view to the owner audience even for administrators with job permissions', async () => {
  const paths: string[] = [];
  const transport: KoinonTransport = {
    request: async <T>(_method: HttpMethod, path: string) => {
      paths.push(path);
      return summary(3) as T;
    },
    stream: async function* () {
      yield* [];
    },
  };
  const { fixture, facade } = setup(transport);
  facade.tenantPermissions.set(new Set(['jobs:manage', 'audit:read', 'activity:read']));
  facade.context.set({
    subject: 'Alice',
    memberships: [
      {
        id: 'admin',
        tenant_id: 'same',
        subject: 'Alice',
        role: 'admin',
        active: true,
        workspace_id: null,
      },
    ],
  });
  fixture.componentRef.setInput('personalOnly', true);
  fixture.detectChanges();
  await fixture.whenStable();
  expect(fixture.componentInstance.canAdmin()).toBe(false);
  expect(fixture.nativeElement.querySelector('select[name=activity-audience]')).toBeNull();
  expect(fixture.nativeElement.textContent).not.toContain('Processing jobs');
  fixture.componentInstance.audience = 'administrative';
  await fixture.componentInstance.load();
  expect(paths.length).toBeGreaterThan(0);
  expect(paths.every((path) => path.endsWith('/activity/personal'))).toBe(true);
});

it('aborts the administrative response when switching to a personal-only view', async () => {
  let finish: ((value: ActivitySummary) => void) | undefined, signal: AbortSignal | undefined;
  const transport: KoinonTransport = {
    request: async <T>(_method: HttpMethod, path: string, options?: RequestOptions) => {
      if (path.endsWith('/administration')) {
        signal = options?.signal;
        return await new Promise<T>((resolve) => (finish = (value) => resolve(value as T)));
      }
      return summary(2) as T;
    },
    stream: async function* () {
      yield* [];
    },
  };
  const { fixture, facade } = setup(transport);
  facade.tenantPermissions.set(new Set(['audit:read', 'activity:read']));
  facade.context.set({
    subject: 'Alice',
    memberships: [
      {
        id: 'admin',
        tenant_id: 'same',
        subject: 'Alice',
        role: 'admin',
        active: true,
        workspace_id: null,
      },
    ],
  });
  fixture.detectChanges();
  await fixture.whenStable();
  fixture.componentInstance.audience = 'administrative';
  const pending = fixture.componentInstance.load();
  await vi.waitFor(() => expect(finish).toBeTypeOf('function'));
  fixture.componentRef.setInput('personalOnly', true);
  fixture.detectChanges();
  await fixture.whenStable();
  expect(signal?.aborted).toBe(true);
  finish!({ ...summary(99), audience: 'organization_administrators' });
  await pending;
  expect(fixture.componentInstance.summary()?.knowledge.created.value).toBe(2);
});

it('invalidates personal summaries immediately when workspace access or tenant selection changes', async () => {
  const transport: KoinonTransport = {
    request: async <T>(_method: HttpMethod, path: string) =>
      ({ ...summary(2), tenant_id: path.split('/')[2] }) as T,
    stream: async function* () {
      yield* [];
    },
  };
  const { fixture, facade } = setup(transport);
  fixture.componentRef.setInput('personalOnly', true);
  fixture.detectChanges();
  await fixture.whenStable();
  expect(fixture.componentInstance.summary()?.tenant_id).toBe('same');
  facade.workspaceId.set('new-scope');
  expect(fixture.componentInstance.summary()).toBeNull();
  fixture.detectChanges();
  await fixture.whenStable();
  facade.tenantId.set('second');
  expect(fixture.componentInstance.summary()).toBeNull();
  fixture.detectChanges();
  await fixture.whenStable();
  expect(fixture.componentInstance.summary()?.tenant_id).toBe('second');
});

for (const mismatch of ['tenant', 'audience'] as const)
  it(`rejects a personal summary with a mismatched ${mismatch}`, async () => {
    const transport: KoinonTransport = {
      request: async <T>() =>
        ({
          ...summary(3),
          ...(mismatch === 'tenant'
            ? { tenant_id: 'other' }
            : { audience: 'organization_administrators' as const }),
        }) as T,
      stream: async function* () {
        yield* [];
      },
    };
    const { fixture } = setup(transport);
    fixture.componentRef.setInput('personalOnly', true);
    fixture.detectChanges();
    await fixture.whenStable();
    expect(fixture.componentInstance.summary()).toBeNull();
    expect(fixture.componentInstance.error()).toBe('Activity could not be loaded. Try again.');
  });

it('automatically refreshes the current activity summary without overlapping a slow read', async () => {
  let reads = 0;
  let release: (() => void) | undefined;
  const transport: KoinonTransport = {
    request: async <T>() => {
      reads++;
      if (reads > 1)
        await new Promise<void>((resolve) => {
          release = resolve;
        });
      return summary(reads) as T;
    },
    stream: async function* () {
      yield* [];
    },
  };
  const { fixture } = setup(transport);
  fixture.detectChanges();
  await fixture.whenStable();
  vi.useFakeTimers();
  try {
    window.dispatchEvent(new Event('focus'));
    await vi.advanceTimersByTimeAsync(65000);
    expect(reads).toBe(2);
    expect(fixture.componentInstance.summary()?.knowledge.created.value).toBe(1);
    release?.();
    await vi.advanceTimersByTimeAsync(1);
    expect(fixture.componentInstance.summary()?.knowledge.created.value).toBe(2);
    fixture.destroy();
    await vi.advanceTimersByTimeAsync(65000);
    expect(reads).toBe(2);
  } finally {
    vi.useRealTimers();
  }
});

it('clears denied activity and stops automatic retries until authority changes', async () => {
  let deny = false,
    calls = 0;
  const transport: KoinonTransport = {
    request: async <T>() => {
      calls++;
      if (deny) throw new KoinonError(403, 'DENIED', 'revoked');
      return summary(calls) as T;
    },
    stream: async function* () {
      yield* [];
    },
  };
  const { fixture, facade } = setup(transport);
  fixture.detectChanges();
  await fixture.whenStable();
  vi.useFakeTimers();
  try {
    deny = true;
    window.dispatchEvent(new Event('focus'));
    await vi.advanceTimersByTimeAsync(31000);
    expect(fixture.componentInstance.summary()).toBeNull();
    const deniedCalls = calls;
    await vi.advanceTimersByTimeAsync(120000);
    expect(calls).toBe(deniedCalls);
    deny = false;
    facade.context.set({ subject: 'Alice', memberships: [] });
    fixture.detectChanges();
    await vi.advanceTimersByTimeAsync(1);
    expect(fixture.componentInstance.summary()).not.toBeNull();
    fixture.destroy();
  } finally {
    vi.useRealTimers();
  }
});
it('does not automatically apply an edited reporting window', async () => {
  let calls = 0;
  const transport: KoinonTransport = {
    request: async <T>() => {
      calls++;
      return summary(calls) as T;
    },
    stream: async function* () {
      yield* [];
    },
  };
  const { fixture } = setup(transport);
  fixture.detectChanges();
  await fixture.whenStable();
  vi.useFakeTimers();
  try {
    fixture.componentInstance.window = {
      start_at: '2026-10-01T00:00:00Z',
      end_at: '2026-10-02T00:00:00Z',
      time_zone: 'UTC',
    };
    window.dispatchEvent(new Event('focus'));
    await vi.advanceTimersByTimeAsync(65000);
    expect(calls).toBe(1);
    fixture.destroy();
  } finally {
    vi.useRealTimers();
  }
});

it('observes jobs with their own request and clears them when administrator membership expires', async () => {
  const calls: string[] = [];
  const transport: KoinonTransport = {
    request: async <T>(_method: HttpMethod, path: string) => {
      calls.push(path);
      if (path.endsWith('/jobs'))
        return {
          items: [
            {
              id: 'job',
              tenant_id: 'same',
              resource_id: 'resource',
              kind: 'index',
              status: 'running',
              progress: 10,
              error: null,
            },
          ],
        } as T;
      if (path.endsWith('/knowledge-processing'))
        return { items: [], observed_at: new Date().toISOString(), next_page: null } as T;
      return summary(calls.length) as T;
    },
    stream: async function* () {
      yield* [];
    },
  };
  const { fixture, facade } = setup(transport);
  fixture.detectChanges();
  await fixture.whenStable();
  vi.useFakeTimers();
  try {
    facade.tenantPermissions.set(new Set(['jobs:manage', 'audit:read', 'activity:read']));
    facade.context.set({
      subject: 'Alice',
      memberships: [
        {
          id: 'admin',
          subject: 'Alice',
          tenant_id: 'same',
          workspace_id: null,
          role: 'admin',
          active: true,
          expires_at: new Date(Date.now() + 12000).toISOString(),
        },
      ],
    });
    fixture.detectChanges();
    await vi.advanceTimersByTimeAsync(1);
    fixture.detectChanges();
    expect(fixture.componentInstance.jobs()).toHaveLength(1);
    window.dispatchEvent(new Event('focus'));
    await vi.advanceTimersByTimeAsync(10000);
    expect(calls.filter((path) => path.endsWith('/jobs')).length).toBeGreaterThan(1);
    await vi.advanceTimersByTimeAsync(3000);
    fixture.detectChanges();
    expect(fixture.componentInstance.jobs()).toHaveLength(0);
    expect(fixture.componentInstance.canManageJobs()).toBe(false);
    const stopped = calls.filter((path) => path.endsWith('/jobs')).length;
    await vi.advanceTimersByTimeAsync(65000);
    expect(calls.filter((path) => path.endsWith('/jobs'))).toHaveLength(stopped);
    fixture.destroy();
  } finally {
    vi.useRealTimers();
  }
});
