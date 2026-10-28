// Copyright 2026 Firefly Software Foundation
// SPDX-License-Identifier: Apache-2.0
import { DOCUMENT } from '@angular/common';
import { TestBed } from '@angular/core/testing';
import { PendingShare } from './pending-share';
function environment(fragment = '', saved?: string) {
  const values = new Map(saved ? [['koinon.pending-share', saved]] : []);
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
  return { service: TestBed.inject(PendingShare), window, values };
}
it('retains only the share reference across sign-in and preserves unrelated address state', () => {
  const { service, window, values } = environment(
    '#share=share-one&tenant=tenant-one&panel=library',
  );
  expect(service.shareId()).toBe('share-one');
  expect(service.tenantId()).toBe('tenant-one');
  expect(window.location.href).toBe('https://knowledge.example.test/app/?view=chat#panel=library');
  expect(JSON.parse(values.get('koinon.pending-share')!).shareId).toBe('share-one');
  service.clear();
  expect(values.size).toBe(0);
});
it('restores a valid reference after the authentication redirect', () => {
  const { service } = environment(
    '',
    JSON.stringify({ shareId: 'share-one', tenantId: 'tenant-one', expiresAt: Date.now() + 60000 }),
  );
  expect(service.shareId()).toBe('share-one');
});
for (const fragment of [
  '#share=one&share=two&tenant=north',
  '#share=one',
  '#share=../secret&tenant=north',
])
  it('rejects ambiguous or invalid links without retaining an authority-bearing URL', () => {
    const { service, values, window } = environment(fragment);
    expect(service.shareId()).toBe('');
    expect(values.size).toBe(0);
    expect(window.location.hash).toBe('');
  });
it('expires a locally retained reference and removes it from session storage', () => {
  vi.useFakeTimers();
  try {
    const { service, values } = environment('#share=one&tenant=north');
    vi.advanceTimersByTime(60 * 60 * 1000 + 1);
    expect(service.shareId()).toBe('');
    expect(values.size).toBe(0);
  } finally {
    vi.useRealTimers();
  }
});
