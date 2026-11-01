// Copyright 2026 Firefly Software Foundation SPDX-License-Identifier: Apache-2.0
import { signal } from '@angular/core';
import { TestBed } from '@angular/core/testing';
import {
  KoinonClient,
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
