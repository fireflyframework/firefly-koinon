// Copyright 2026 Firefly Software Foundation SPDX-License-Identifier: Apache-2.0
import { DOCUMENT } from '@angular/common';
import { TestBed } from '@angular/core/testing';
import { AccountNavigation } from './account-navigation';

function environment(
  path = '/app/account/applications?retained=one#panel=two',
  saved?: string,
  denied = false,
) {
  let address = new URL(path, 'https://knowledge.example.test');
  const values = new Map<string, string>(
    saved ? [['koinon.pending-account-navigation', saved]] : [],
  );
  const replacements: string[] = [];
  const entries: string[] = [],
    listeners = new Map<string, EventListener>();
  const window = {
    get location() {
      return address;
    },
    sessionStorage: {
      getItem: (key: string) => {
        if (denied) throw new Error('Storage denied');
        return values.get(key) ?? null;
      },
      setItem: (key: string, value: string) => {
        if (denied) throw new Error('Storage denied');
        values.set(key, value);
      },
      removeItem: (key: string) => {
        if (denied) throw new Error('Storage denied');
        values.delete(key);
      },
    },
    history: {
      state: { retained: true },
      replaceState: (_state: unknown, _unused: string, url: string) => {
        replacements.push(url);
        address = new URL(url, address);
      },
      pushState: (_state: unknown, _unused: string, url: string) => {
        entries.push(url);
        address = new URL(url, address);
      },
    },
    addEventListener: (name: string, handler: EventListener) => listeners.set(name, handler),
    removeEventListener: (name: string) => listeners.delete(name),
  };
  TestBed.configureTestingModule({
    providers: [
      {
        provide: DOCUMENT,
        useValue: {
          baseURI: 'https://knowledge.example.test/app/',
          defaultView: window,
        },
      },
    ],
  });
  return {
    service: TestBed.inject(AccountNavigation),
    window,
    entries,
    replacements,
    values,
    listeners,
    pop(path: string) {
      address = new URL(path, address);
      listeners.get('popstate')?.(new Event('popstate'));
    },
  };
}
it('opens an account deep link without rewriting unrelated address state', () => {
  const { service, entries } = environment();
  expect(service.section()).toBe('applications');
  expect(service.view()).toBe('library');
  expect(entries).toEqual([]);
});
it('records section navigation within the deployment base and preserves query/fragment', () => {
  const { service, entries, window } = environment();
  service.open('tokens');
  expect(window.location.href).toBe(
    'https://knowledge.example.test/app/account/tokens?retained=one#panel=two',
  );
  service.open('tokens');
  expect(entries).toHaveLength(1);
  service.navigate('library');
  expect(service.section()).toBe(null);
  expect(window.location.pathname).toBe('/app/');
});
it('restores account sections on browser back and forward without adding history', () => {
  const { service, pop, entries } = environment();
  pop('/app/account/profile');
  expect(service.section()).toBe('profile');
  pop('/app/account/applications');
  expect(service.section()).toBe('applications');
  pop('/app/');
  expect(service.section()).toBe(null);
  expect(entries).toEqual([]);
});
it('keeps unknown account paths out of the application section and removes its listener', () => {
  const { service, listeners } = environment('/app/account/not-a-section');
  expect(service.section()).toBe(null);
  service.ngOnDestroy();
  expect(listeners.has('popstate')).toBe(false);
});

it('retains only public route enums for sign-in and restores a root return with replaceState', () => {
  const first = environment();
  first.service.retainForSignIn();
  const saved = first.values.get('koinon.pending-account-navigation')!;
  expect(JSON.parse(saved)).toEqual({ view: 'library', accountSection: 'applications' });
  first.service.ngOnDestroy();
  TestBed.resetTestingModule();
  const returned = environment('/app/?retained=one#panel=two', saved);
  expect(returned.service.section()).toBe('applications');
  expect(returned.window.location.href).toBe(
    'https://knowledge.example.test/app/account/applications?retained=one#panel=two',
  );
  expect(returned.entries).toEqual([]);
  expect(returned.replacements).toHaveLength(1);
  expect(returned.values.size).toBe(0);
});
for (const path of [
  '/app/account/tokens',
  '/app/chat',
  '/app/#share=reference&tenant=tenant-one',
  '/app/#invite=reference',
])
  it('lets an explicit URL win over a retained account route: ' + path, () => {
    const { service, replacements, window, values } = environment(
      path,
      JSON.stringify({ view: 'library', accountSection: 'applications' }),
    );
    expect(window.location.pathname + window.location.hash).toBe(path.replace('/app/', '/app/'));
    expect(service.section()).not.toBe('applications');
    expect(replacements).toEqual([]);
    expect(values.size).toBe(0);
  });
for (const saved of [
  'not-json',
  'null',
  '[]',
  JSON.stringify({ view: 'library', accountSection: 'unknown' }),
  JSON.stringify({ view: 'https://evil.example', accountSection: null }),
  JSON.stringify({ view: 'library', accountSection: 'applications', token: 'untrusted' }),
])
  it('ignores unknown or authority-bearing stored navigation: ' + saved, () => {
    const { service, replacements, values } = environment('/app/', saved);
    expect(service.section()).toBe(null);
    expect(service.view()).toBe('library');
    expect(replacements).toEqual([]);
    expect(values.size).toBe(0);
  });
it('clears pending navigation and remains usable when tab storage is denied', () => {
  const allowed = environment();
  allowed.service.retainForSignIn();
  allowed.service.clearPending();
  expect(allowed.values.size).toBe(0);
  allowed.service.ngOnDestroy();
  TestBed.resetTestingModule();
  const denied = environment('/app/account/applications', undefined, true);
  expect(() => denied.service.retainForSignIn()).not.toThrow();
  expect(() => denied.service.clearPending()).not.toThrow();
  expect(denied.service.section()).toBe('applications');
});
