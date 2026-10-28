// Copyright 2026 Firefly Software Foundation
// SPDX-License-Identifier: Apache-2.0
import { DOCUMENT } from '@angular/common';
import { TestBed } from '@angular/core/testing';
import { PendingInvitation } from './pending-invitation';
const token = 'a'.repeat(43);
function environment(fragment = '', saved?: string) {
  const values = new Map<string, string>(saved ? [['koinon.pending-invitation', saved]] : []);
  let address = new URL('https://knowledge.example.test/app/?view=chat' + fragment);
  const window = {
    get location() {
      return address;
    },
    history: {
      state: { retained: true },
      replaceState: (_state: unknown, _unused: string, url: string) => {
        address = new URL(url, address);
      },
    },
    sessionStorage: {
      getItem: (key: string) => values.get(key) ?? null,
      setItem: (key: string, value: string) => {
        values.set(key, value);
      },
      removeItem: (key: string) => values.delete(key),
    },
  };
  TestBed.configureTestingModule({
    providers: [{ provide: DOCUMENT, useValue: { defaultView: window } }],
  });
  return { service: TestBed.inject(PendingInvitation), values, window };
}
it('strips the private fragment before requests while preserving other navigation state', () => {
  const { service, window, values } = environment('#invite=' + token + '&panel=library');
  expect(service.token()).toBe(token);
  expect(window.location.href).toBe('https://knowledge.example.test/app/?view=chat#panel=library');
  expect(JSON.parse(values.get('koinon.pending-invitation')!).token).toBe(token);
  service.clear();
  expect(service.token()).toBe('');
  expect(values.size).toBe(0);
});
it('restores a bounded pending invitation across the login redirect', () => {
  const { service } = environment('', JSON.stringify({ token, expiresAt: Date.now() + 60000 }));
  expect(service.token()).toBe(token);
});
for (const saved of [
  'broken',
  JSON.stringify({ token, expiresAt: 1 }),
  JSON.stringify({ token, expiresAt: Date.now() + 7200000 }),
])
  it('clears invalid or expired retained invitations', () => {
    const { service, values } = environment('', saved);
    expect(service.token()).toBe('');
    expect(values.size).toBe(0);
  });
it('rejects duplicate and malformed fragment tokens and strips them from the address', () => {
  const { service, window } = environment('#invite=' + token + '&invite=other');
  expect(service.token()).toBe('');
  expect(window.location.hash).toBe('');
});
it('clears a retained link when its local login window expires', () => {
  vi.useFakeTimers();
  try {
    const { service, values } = environment('#invite=' + token);
    vi.advanceTimersByTime(60 * 60 * 1000 + 1);
    expect(service.token()).toBe('');
    expect(values.size).toBe(0);
  } finally {
    vi.useRealTimers();
  }
});
