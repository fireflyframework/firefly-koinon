// Copyright 2026 Firefly Software Foundation SPDX-License-Identifier: Apache-2.0
import { signal } from '@angular/core';
import { TestBed } from '@angular/core/testing';
import {
  KoinonClient,
  type KoinonTransport,
  type HttpMethod,
  type RequestOptions,
} from '@fireflyframework/koinon-sdk';
import {
  KoinonClientContext,
  KoinonFacade,
  provideKoinonClient,
} from '@fireflyframework/koinon-angular';
import { KoinonNotificationCenter } from '../../../../communications/inbox/notification-center';
import { KoinonNotificationCenterTrigger } from '../../../../communications/runtime/notification-center-trigger';
function transport(owner: string, calls: string[]): KoinonTransport {
  return {
    request: async <T>(_method: HttpMethod, path: string) => {
      calls.push(path);
      return (
        path.endsWith('/unread-count')
          ? { unread: owner === 'Alice' ? 7 : 2 }
          : path.endsWith('/preferences')
            ? {
                revision: 1,
                rules: [],
                digest: 'off',
                allowed_digests: ['off'],
                locale: 'en-US',
                time_zone: 'UTC',
                notification_locale: null,
                effective_locale: 'en-US',
                locale_origin: 'default',
                schedule: { local_time: '09:00', weekday: 0, day_of_month: 1 },
              }
            : {
                items: [
                  {
                    id: owner,
                    kind: 'access_removed',
                    title: owner + ' private notice',
                    body: 'Access changed',
                    created_at: '2026-10-31T00:00:00Z',
                    read_at: null,
                    tenant_id: 'same',
                    organization_name: 'Team',
                    target: { kind: 'none', id: null },
                  },
                ],
                page: 1,
                page_size: 25,
                pages: 1,
                total: 1,
              }
      ) as T;
    },
    stream: async function* () {
      yield* [];
    },
  };
}
it('refreshes the shared unread badge and the filtered page after a confirmed read', async () => {
  let unread = 1;
  const calls: string[] = [];
  const base = transport('Alice', calls);
  const api: KoinonTransport = {
    ...base,
    request: async <T>(method: HttpMethod, path: string, options?: RequestOptions) => {
      if (method === 'POST') {
        unread = 0;
        return { id: 'Alice', read_at: '2026-11-01T12:00:00Z' } as T;
      }
      if (path.endsWith('/unread-count')) return { unread } as T;
      if (!unread && path.endsWith('/notifications'))
        return { items: [], page: 1, page_size: 25, pages: 0, total: 0 } as T;
      return base.request<T>(method, path, options);
    },
  };
  TestBed.configureTestingModule({
    providers: [
      ...provideKoinonClient(new KoinonClient({ transport: api }), api),
      KoinonClientContext,
      {
        provide: KoinonFacade,
        useValue: {
          context: signal({ subject: 'Alice' }),
          tenantId: signal('same'),
          workspaceId: signal(''),
          authRequired: signal(false),
        },
      },
    ],
  });
  const center = TestBed.createComponent(KoinonNotificationCenter);
  const bell = TestBed.createComponent(KoinonNotificationCenterTrigger);
  center.detectChanges();
  bell.detectChanges();
  await center.whenStable();
  await bell.whenStable();
  await center.componentInstance.load({ page: 1, page_size: 25, read: 'unread', kind: '' });
  expect(bell.componentInstance.unread()).toBe(1);
  await center.componentInstance.markRead('Alice');
  TestBed.tick();
  await center.whenStable();
  await bell.whenStable();
  expect(bell.componentInstance.unread()).toBe(0);
  expect(center.componentInstance.page()?.items).toEqual([]);
});
it('shows an unavailable count when the server fails instead of reporting no unread notifications', async () => {
  const api: KoinonTransport = {
    request: async () => {
      throw new Error('Unavailable');
    },
    stream: async function* () {
      yield* [];
    },
  };
  TestBed.configureTestingModule({
    providers: [
      ...provideKoinonClient(new KoinonClient({ transport: api }), api),
      KoinonClientContext,
      {
        provide: KoinonFacade,
        useValue: {
          context: signal({ subject: 'Alice' }),
          tenantId: signal('same'),
          workspaceId: signal(''),
          authRequired: signal(false),
        },
      },
    ],
  });
  const bell = TestBed.createComponent(KoinonNotificationCenterTrigger);
  bell.detectChanges();
  await bell.whenStable();
  bell.detectChanges();
  expect(bell.componentInstance.unread()).toBeNull();
  expect(bell.nativeElement.querySelector('button').getAttribute('aria-label')).toContain(
    'Unread count unavailable',
  );
});
it('clears own inbox, preferences and unread badge for a client-only switch and resumes only with the explicit matching pair', async () => {
  const aCalls: string[] = [],
    bCalls: string[] = [],
    a = transport('Alice', aCalls),
    b = transport('Bob', bCalls),
    clientA = new KoinonClient({ transport: a }),
    clientB = new KoinonClient({ transport: b });
  const facade = {
    context: signal({ subject: 'Alice' }),
    tenantId: signal('same'),
    workspaceId: signal(''),
    authRequired: signal(false),
  };
  TestBed.configureTestingModule({
    providers: [
      ...provideKoinonClient(clientA, a),
      KoinonClientContext,
      { provide: KoinonFacade, useValue: facade },
    ],
  });
  const context = TestBed.inject(KoinonClientContext),
    center = TestBed.createComponent(KoinonNotificationCenter),
    bell = TestBed.createComponent(KoinonNotificationCenterTrigger);
  center.detectChanges();
  bell.detectChanges();
  await center.whenStable();
  await bell.whenStable();
  await center.componentInstance.loadPreferences();
  expect(center.componentInstance.page()?.items[0]?.title).toBe('Alice private notice');
  expect(center.componentInstance.preferences()).not.toBeNull();
  expect(bell.componentInstance.unread()).toBe(7);
  const before = aCalls.length;
  context.bind(clientB);
  facade.context.set({ subject: 'Bob' });
  expect(context.getTransport()).toBeNull();
  expect(center.componentInstance.page()).toBeNull();
  expect(center.componentInstance.preferences()).toBeNull();
  expect(bell.componentInstance.unread()).toBeNull();
  await center.componentInstance.load({ page: 1, page_size: 25, read: 'all', kind: '' });
  expect(aCalls.length).toBe(before);
  context.bind(clientB, b);
  center.detectChanges();
  bell.detectChanges();
  await center.whenStable();
  await bell.whenStable();
  expect(center.componentInstance.page()?.items[0]?.title).toBe('Bob private notice');
  expect(bell.componentInstance.unread()).toBe(2);
  expect(aCalls.length).toBe(before);
  expect(center.nativeElement.textContent).not.toContain('Alice');
});
it('aborts and discards a prior transport response even when both clients use the same tenant', async () => {
  let finish: (value: unknown) => void = () => {
    throw Error('not registered');
  };
  let started: AbortSignal | undefined;
  const a: KoinonTransport = {
    request: <T>(_method: HttpMethod, _path: string, options?: RequestOptions) =>
      new Promise<T>((resolve) => {
        started = options?.signal;
        finish = (value) => resolve(value as T);
      }),
    stream: async function* () {
      yield* [];
    },
  };
  const b = transport('Bob', []),
    clientA = new KoinonClient({ transport: a }),
    clientB = new KoinonClient({ transport: b });
  TestBed.configureTestingModule({
    providers: [
      ...provideKoinonClient(clientA, a),
      KoinonClientContext,
      {
        provide: KoinonFacade,
        useValue: {
          context: signal({ subject: 'Alice' }),
          tenantId: signal('same'),
          workspaceId: signal(''),
          authRequired: signal(false),
        },
      },
    ],
  });
  const center = TestBed.createComponent(KoinonNotificationCenter);
  center.detectChanges();
  const context = TestBed.inject(KoinonClientContext);
  await vi.waitFor(() => expect(started).toBeInstanceOf(AbortSignal));
  context.bind(clientB);
  TestBed.tick();
  expect(started?.aborted).toBe(true);
  finish({ items: [], page: 1, page_size: 25, pages: 1, total: 0 });
  await center.whenStable();
  expect(center.componentInstance.page()).toBeNull();
});
