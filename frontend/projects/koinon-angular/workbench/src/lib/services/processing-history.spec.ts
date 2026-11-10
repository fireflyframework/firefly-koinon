// Copyright 2026 Firefly Software Foundation
// SPDX-License-Identifier: Apache-2.0
import { TestBed } from '@angular/core/testing';
import { signal } from '@angular/core';
import { describe, expect, it, vi } from 'vitest';
import { KoinonFacade, KoinonClientContext } from '@fireflyframework/koinon-angular';
import {
  KoinonError,
  type KoinonTransport,
  type RequestOptions,
} from '@fireflyframework/koinon-sdk';
import { KoinonProcessingHistory } from '../../../../activity/processing-history';
function setup() {
  const request = vi.fn(async (_method: string, _path: string, options: RequestOptions) => ({
    observed_at: '2026-11-01T00:00:00Z',
    next_page: options.body && (options.body as { page: number }).page === 1 ? 2 : null,
    items: [
      {
        id: 'attempt',
        resource_id: 'document',
        operation: 'document.replace',
        state: 'failed',
        updated_at: '2026-11-01T00:00:00Z',
        availability: {
          read: { state: 'ready' },
          search: { state: 'pending' },
          revision: { source_version_id: 'serving-old' },
        },
      },
    ],
  }));
  const transport = signal<KoinonTransport | null>({ request } as unknown as KoinonTransport);
  const revision = signal(0);
  const context = signal({
    subject: 'actor-a',
    memberships: [
      {
        subject: 'actor-a',
        tenant_id: 'tenant',
        workspace_id: null,
        role: 'admin',
        active: true,
        expires_at: null as string | null,
      },
    ],
  });
  const facade = {
    context,
    tenantId: signal('tenant'),
    workspaceId: signal('space'),
    tenantPermissions: () => new Set(['jobs:manage']),
    entries: () => [{ id: 'document', name: 'Controlled document' }],
  };
  TestBed.configureTestingModule({
    providers: [
      { provide: KoinonFacade, useValue: facade },
      { provide: KoinonClientContext, useValue: { revision, getTransport: () => transport() } },
    ],
  });
  const fixture = TestBed.createComponent(KoinonProcessingHistory);
  fixture.detectChanges();
  return { fixture, request, transport, revision, context };
}
describe('current administrator processing observations', () => {
  it('uses bounded scoped paging and displays serving availability separately from failed attempts', async () => {
    const { fixture, request } = setup();
    await vi.waitFor(() => {
      fixture.detectChanges();
      expect(fixture.nativeElement.textContent).toContain('Controlled document');
    });
    expect(fixture.nativeElement.textContent).toContain('Processing failed');
    expect(fixture.nativeElement.textContent).toContain(
      'Text remains available from the observed version',
    );
    expect(request.mock.calls[0]![2].body).toEqual({
      page: 1,
      page_size: 25,
      workspace_id: 'space',
    });
    await fixture.componentInstance.load(2);
    expect(request.mock.calls[1]![2].body).toEqual({
      page: 2,
      page_size: 25,
      workspace_id: 'space',
    });
    fixture.destroy();
  });
  it('removes old-actor observations immediately when the matching transport is missing', async () => {
    const { fixture, request, transport, revision, context } = setup();
    await vi.waitFor(() => expect(fixture.componentInstance.current()?.items.length).toBe(1));
    context.set({ subject: 'actor-b', memberships: [] });
    transport.set(null);
    revision.update((x) => x + 1);
    expect(fixture.componentInstance.current()).toBeNull();
    fixture.detectChanges();
    expect(fixture.nativeElement.textContent).not.toContain('Controlled document');
    expect(request).toHaveBeenCalledOnce();
    fixture.destroy();
  });
});

it('keeps processing observations current without replacing the selected page', async () => {
  const { fixture, request } = setup();
  await fixture.whenStable();
  await fixture.componentInstance.load(2);
  vi.useFakeTimers();
  try {
    window.dispatchEvent(new Event('focus'));
    await vi.advanceTimersByTimeAsync(65000);
    expect(request.mock.calls.length).toBeGreaterThan(3);
    expect(fixture.componentInstance.page()).toBe(2);
    expect((request.mock.calls.at(-1)![2].body as { page: number }).page).toBe(2);
    fixture.destroy();
  } finally {
    vi.useRealTimers();
  }
});

it('clears revoked processing observations and stops automatic reads', async () => {
  const { fixture, request } = setup();
  await fixture.whenStable();
  vi.useFakeTimers();
  try {
    request.mockRejectedValue(new KoinonError(403, 'DENIED', 'revoked'));
    window.dispatchEvent(new Event('focus'));
    await vi.advanceTimersByTimeAsync(31000);
    expect(fixture.componentInstance.current()).toBeNull();
    const calls = request.mock.calls.length;
    await vi.advanceTimersByTimeAsync(120000);
    expect(request).toHaveBeenCalledTimes(calls);
    fixture.destroy();
  } finally {
    vi.useRealTimers();
  }
});

it('hides processing data and stops reads at membership expiry even when embedded alone', async () => {
  const { fixture, request, context } = setup();
  await fixture.whenStable();
  vi.useFakeTimers();
  try {
    context.update((value) => ({
      ...value,
      memberships: value.memberships.map((grant) => ({
        ...grant,
        expires_at: new Date(Date.now() + 1000).toISOString(),
      })),
    }));
    fixture.detectChanges();
    await vi.advanceTimersByTimeAsync(1);
    expect(fixture.componentInstance.current()).not.toBeNull();
    await vi.advanceTimersByTimeAsync(1100);
    fixture.detectChanges();
    expect(fixture.componentInstance.current()).toBeNull();
    const calls = request.mock.calls.length;
    await vi.advanceTimersByTimeAsync(65000);
    expect(request).toHaveBeenCalledTimes(calls);
    fixture.destroy();
  } finally {
    vi.useRealTimers();
  }
});

it('observes pending native indexing at five seconds after processing has completed', async () => {
  const { fixture, request } = setup();
  await fixture.whenStable();
  const response = await request.mock.results[0]!.value;
  response.items[0]!.state = 'complete';
  request.mockResolvedValue(response);
  await fixture.componentInstance.load(1);
  const count = request.mock.calls.length;
  vi.useFakeTimers();
  try {
    window.dispatchEvent(new Event('focus'));
    await vi.advanceTimersByTimeAsync(5100);
    expect(request.mock.calls.length).toBeGreaterThan(count);
    fixture.destroy();
  } finally {
    vi.useRealTimers();
  }
});
