// Copyright 2026 Firefly Software Foundation
// SPDX-License-Identifier: Apache-2.0
import { TestBed } from '@angular/core/testing';
import { signal } from '@angular/core';
import { vi } from 'vitest';
import { KoinonFacade, KoinonClientContext } from '@fireflyframework/koinon-angular';
import {
  KoinonError,
  type KoinonTransport,
  type RequestOptions,
} from '@fireflyframework/koinon-sdk';
import { KoinonCommunicationsSettings } from '../../../../communications/admin/communications-settings';
function fixture() {
  const context = signal({
    subject: 'actor',
    tenants: [{ id: 'tenant', permissions: ['members:write'] }],
    memberships: [
      {
        subject: 'actor',
        tenant_id: 'tenant',
        workspace_id: null,
        role: 'admin',
        active: true,
        expires_at: null as string | null,
      },
    ],
  });
  const row = {
    id: 'mail',
    kind: 'welcome',
    recipient_display: 'Alex',
    scope_name: 'Workspace',
    status: 'queued',
    created_at: '2026-11-03T00:00:00Z',
    attempt_count: 1,
    can_retry: false,
  };
  const request = vi.fn(async (_method: string, path: string, options: RequestOptions) => {
    if (path.endsWith('/capabilities')) return { state: 'ready', issues: [] };
    if (path.endsWith('/policy')) return { revision: 1, rules: [], can_update: true };
    if (path.endsWith('/mail')) return row;
    return {
      items: [row],
      page: Number(options.query?.['page'] ?? 1),
      page_size: 25,
      total: 1,
      pages: 2,
    };
  });
  const authRequired = signal(false);
  TestBed.configureTestingModule({
    providers: [
      {
        provide: KoinonFacade,
        useValue: { context, tenantId: signal('tenant'), workspaceId: signal(''), authRequired },
      },
      {
        provide: KoinonClientContext,
        useValue: {
          revision: signal(0),
          getTransport: () => ({ request }) as unknown as KoinonTransport,
        },
      },
    ],
  });
  TestBed.overrideComponent(KoinonCommunicationsSettings, { set: { template: '' } });
  const host = TestBed.createComponent(KoinonCommunicationsSettings);
  host.detectChanges();
  return { host, request, context, row, authRequired };
}
it('closing a delivery aborts the in-flight observation and cannot reopen it on late completion', async () => {
  const f = fixture();
  await f.host.whenStable();
  const c = f.host.componentInstance;
  c.section('history');
  await f.host.whenStable();
  await c.detail('mail');
  expect(c.view().selected?.id).toBe('mail');
  let release!: () => void;
  const waiting = new Promise<void>((resolve) => {
    release = resolve;
  });
  const original = f.request.getMockImplementation()!;
  f.request.mockImplementation(async (...args) => {
    await waiting;
    return original(...args);
  });
  const pending = c.refresh(true);
  c.close();
  const aborted = f.request.mock.calls.at(-1)?.[2].signal?.aborted;
  release();
  await pending;
  expect(c.view().selected).toBeNull();
  expect(aborted).toBe(true);
  f.host.destroy();
});
it('entering policy cancels an observation already in flight without replacing a draft', async () => {
  const f = fixture();
  await f.host.whenStable();
  const c = f.host.componentInstance;
  await vi.waitFor(() => expect(c.view().policy).not.toBeNull());
  const policy = c.view().policy;
  let release!: () => void;
  const waiting = new Promise<void>((resolve) => {
    release = resolve;
  });
  const original = f.request.getMockImplementation()!;
  f.request.mockImplementation(async (...args) => {
    await waiting;
    return original(...args);
  });
  const pending = c.refresh(true);
  c.section('policy');
  expect(f.request.mock.calls.at(-1)?.[2].signal?.aborted).toBe(true);
  release();
  await pending;
  expect(c.view().policy).toBe(policy);
  f.host.destroy();
});
it('updates pending deliveries automatically while retaining the applied page and policy', async () => {
  const f = fixture();
  await f.host.whenStable();
  const c = f.host.componentInstance;
  c.section('history');
  await f.host.whenStable();
  await c.history({ page: 2, page_size: 25, kind: '', status: '', from: '', to: '' });
  const policy = c.view().policy;
  vi.useFakeTimers();
  try {
    window.dispatchEvent(new Event('focus'));
    f.host.detectChanges();
    const before = f.request.mock.calls.length;
    await vi.advanceTimersByTimeAsync(5100);
    f.host.detectChanges();
    expect(f.request.mock.calls.length).toBeGreaterThan(before);
    expect(f.request.mock.calls.at(-1)?.[2].query?.['page']).toBe(2);
    expect(c.view().policy).toBe(policy);
    expect(f.request.mock.calls.every(([method]) => method === 'GET')).toBe(true);
    c.section('policy');
    f.host.detectChanges();
    const paused = f.request.mock.calls.length;
    await vi.advanceTimersByTimeAsync(65000);
    expect(f.request.mock.calls).toHaveLength(paused);
    f.host.destroy();
  } finally {
    vi.useRealTimers();
  }
});
it('pauses automatic reads during action review without losing the selected section', async () => {
  const f = fixture();
  await f.host.whenStable();
  const c = f.host.componentInstance;
  c.section('history');
  await f.host.whenStable();
  vi.useFakeTimers();
  try {
    c.paused.set(true);
    f.host.detectChanges();
    const before = f.request.mock.calls.length;
    await vi.advanceTimersByTimeAsync(65000);
    expect(f.request.mock.calls).toHaveLength(before);
    c.paused.set(false);
    f.host.detectChanges();
    await vi.advanceTimersByTimeAsync(5100);
    expect(f.request.mock.calls.length).toBeGreaterThan(before);
    f.host.destroy();
  } finally {
    vi.useRealTimers();
  }
});
for (const status of [401, 403])
  it(`clears rows and stops timers on ${status}`, async () => {
    const f = fixture();
    await f.host.whenStable();
    const c = f.host.componentInstance;
    c.section('history');
    await f.host.whenStable();
    vi.useFakeTimers();
    try {
      f.request.mockRejectedValue(new KoinonError(status, 'DENIED', 'private'));
      window.dispatchEvent(new Event('focus'));
      f.host.detectChanges();
      await vi.advanceTimersByTimeAsync(5100);
      f.host.detectChanges();
      expect(c.view().deliveries).toBeNull();
      expect(f.authRequired()).toBe(status === 401);
      const before = f.request.mock.calls.length;
      await vi.advanceTimersByTimeAsync(120000);
      expect(f.request.mock.calls).toHaveLength(before);
      f.host.destroy();
    } finally {
      vi.useRealTimers();
    }
  });
it('expires membership without retaining private delivery rows', async () => {
  const f = fixture();
  await f.host.whenStable();
  const c = f.host.componentInstance;
  c.section('history');
  await f.host.whenStable();
  vi.useFakeTimers();
  try {
    f.context.update((value) => ({
      ...value,
      memberships: value.memberships.map((m) => ({
        ...m,
        expires_at: new Date(Date.now() + 1000).toISOString(),
      })),
    }));
    f.host.detectChanges();
    await vi.advanceTimersByTimeAsync(1100);
    f.host.detectChanges();
    expect(c.view().deliveries).toBeNull();
    const before = f.request.mock.calls.length;
    await vi.advanceTimersByTimeAsync(65000);
    expect(f.request.mock.calls).toHaveLength(before);
    f.host.destroy();
  } finally {
    vi.useRealTimers();
  }
});
