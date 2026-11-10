// Copyright 2026 Firefly Software Foundation
// SPDX-License-Identifier: Apache-2.0
import { provideHttpClient } from '@angular/common/http';
import { HttpTestingController, provideHttpClientTesting } from '@angular/common/http/testing';
import { TestBed } from '@angular/core/testing';
import { signal } from '@angular/core';
import type { KoinonWorkbench } from '@fireflyframework/koinon-angular/workbench';
import { SessionMonitor } from './session-monitor';
import { SessionService } from './session.service';

const observed = {
  authenticated: true,
  subject: 'https://identity.example.test|alice',
  authenticated_at: '2026-11-01T09:59:00Z',
  server_time: '2026-11-01T10:00:00Z',
  expires_at: '2026-11-01T10:01:00Z',
};
let monitor: SessionMonitor;
let requests: HttpTestingController;
function setup() {
  TestBed.configureTestingModule({ providers: [provideHttpClient(), provideHttpClientTesting()] });
  const f = {
    context: signal({ subject: observed.subject }),
    authRequired: signal(false),
    revalidateSession: vi.fn(async () => true),
  };
  const workbench = {
    f,
    dialog: signal(null),
    formName: '',
    formDescription: '',
  } as unknown as KoinonWorkbench;
  monitor = new SessionMonitor(
    TestBed.inject(importedHttpClient),
    workbench,
    TestBed.inject(SessionService),
  );
  requests = TestBed.inject(HttpTestingController);
  return { f, workbench };
}
import { HttpClient as importedHttpClient } from '@angular/common/http';
async function flush(value: object = observed) {
  const request = requests.expectOne('/auth/me');
  expect(request.request.method).toBe('GET');
  expect(request.request.withCredentials).toBe(true);
  request.flush(value);
  await vi.waitFor(() => expect(monitor.remaining()).not.toBeUndefined());
  await Promise.resolve();
}
afterEach(() => {
  monitor?.stop();
  requests?.verify();
  vi.restoreAllMocks();
});

it('opens no authentication flow until the user renews, with no opener or credential URL', async () => {
  const { f } = setup();
  const open = vi.spyOn(window, 'open').mockReturnValue(null);
  await flush();
  expect(monitor.remaining()).toBe(60);
  expect(open).not.toHaveBeenCalled();
  await monitor.renew();
  expect(open).toHaveBeenCalledExactlyOnceWith(
    '/oauth2/authorization/koinon',
    '_blank',
    'noopener,noreferrer,popup,width=520,height=760',
  );
  expect(f.revalidateSession).not.toHaveBeenCalled();
});
it('does not mistake OAuth state persistence for completed sign-in, then revalidates a real login', async () => {
  const { f } = setup();
  vi.spyOn(window, 'open').mockReturnValue(null);
  await flush();
  await monitor.renew();
  const check = monitor.read();
  await flush({ ...observed, expires_at: '2026-11-01T10:31:00Z' });
  await check;
  expect(monitor.renewing()).toBe(true);
  expect(f.revalidateSession).not.toHaveBeenCalled();
  const completed = monitor.read();
  await flush({
    ...observed,
    authenticated_at: '2026-11-01T10:00:10Z',
    expires_at: '2026-11-01T10:31:00Z',
  });
  await completed;
  expect(f.revalidateSession).toHaveBeenCalledExactlyOnceWith(observed.subject);
  expect(monitor.renewing()).toBe(false);
  expect(monitor.message()).toContain('No requests were retried');
  expect(requests.match((request) => request.method !== 'GET')).toHaveLength(0);
});
it('discards recovery on principal changes rather than restoring another actor’s draft', async () => {
  const { f } = setup();
  await flush();
  const clear = vi.spyOn(monitor.draft, 'clear');
  const check = monitor.read();
  await flush({ ...observed, subject: 'https://identity.example.test|bob' });
  await check;
  expect(clear).toHaveBeenCalled();
  expect(f.revalidateSession).toHaveBeenCalledWith(observed.subject);
  expect(monitor.message()).toContain('account changed');
});
it('does not fabricate expiry for an old/custom backend, or treat a failed observation as logout', async () => {
  const { f } = setup();
  await flush({ authenticated: true, subject: observed.subject });
  expect(monitor.remaining()).toBe(null);
  expect(monitor.canRenew()).toBe(false);
  const check = monitor.read();
  requests.expectOne('/auth/me').flush({}, { status: 503, statusText: 'Unavailable' });
  await check;
  expect(f.authRequired()).toBe(false);
  expect(monitor.remaining()).toBe(null);
});
it('captures in-memory recovery before authenticated session denial and ignores a response after logout', async () => {
  const { f } = setup();
  await flush();
  const capture = vi.spyOn(monitor.draft, 'capture');
  const check = monitor.read();
  requests.expectOne('/auth/me').flush({}, { status: 401, statusText: 'Unauthorized' });
  await check;
  expect(capture).toHaveBeenCalled();
  expect(f.authRequired()).toBe(true);
  const late = monitor.read();
  const request = requests.expectOne('/auth/me');
  monitor.stop();
  request.flush(observed);
  await late;
  expect(monitor.remaining()).toBe(null);
  expect(monitor.message()).toBe('');
});
