// Copyright 2026 Firefly Software Foundation SPDX-License-Identifier: Apache-2.0
import { TestBed } from '@angular/core/testing';
import {
  KoinonClient,
  type HttpMethod,
  type RequestOptions,
  type KoinonTransport,
} from '@fireflyframework/koinon-sdk';
import { KoinonFacade, provideKoinonClient } from '@fireflyframework/koinon-angular/workbench/core';
import { KoinonSourceAccounts } from './source-accounts';

const connection = {
  id: 'one',
  provider: 'google_drive' as const,
  status: 'connected' as const,
  revision: 2,
  account: { provider: 'google_drive' as const, subject: 'private-subject', tenant_id: null },
  synchronization_available: false as const,
};
const selection = {
  provider: 'google_drive' as const,
  external_tenant: null,
  connection_id: 'one',
};
function setup(
  handler: (method: HttpMethod, path: string, options?: RequestOptions) => Promise<unknown>,
) {
  const transport: KoinonTransport = {
    request: <T>(method: HttpMethod, path: string, options?: RequestOptions) =>
      handler(method, path, options) as Promise<T>,
    stream: () => {
      throw Error('Unexpected stream');
    },
  };
  TestBed.configureTestingModule({
    providers: [
      KoinonFacade,
      KoinonSourceAccounts,
      ...provideKoinonClient(new KoinonClient({ transport }), transport),
    ],
  });
  const facade = TestBed.inject(KoinonFacade);
  facade.tenantId.set('tenant');
  facade.context.set({ subject: 'reader', tenants: [], workspaces: [], memberships: [] });
  return { state: TestBed.inject(KoinonSourceAccounts), facade };
}
describe('personal source account selection', () => {
  it('keeps an empty authorized page continuable without inventing totals', async () => {
    const cursors: unknown[] = [];
    const { state } = setup(async (_method, _path, options) => {
      cursors.push(options?.query?.['cursor']);
      return cursors.length === 1
        ? { items: [], next_cursor: 'next', synchronization_available: false }
        : { items: [connection], next_cursor: null, synchronization_available: false };
    });
    await state.load();
    expect(state.page().items).toEqual([]);
    expect(state.page().next_cursor).toBe('next');
    await state.load(true);
    expect(state.page().items.map((x) => x.id)).toEqual(['one']);
    expect(cursors).toEqual([undefined, 'next']);
  });
  it('applies saved, explicit replacement and local-only modes distinctly', async () => {
    const { state } = setup(async () => ({
      items: [connection],
      next_cursor: null,
      synchronization_available: false,
    }));
    await state.load();
    expect(state.apply('saved', [])).toBeNull();
    expect(state.apply('explicit', ['one'])).toEqual([selection]);
    expect(state.apply('local', ['one'])).toEqual([]);
    expect(() => state.apply('explicit', ['foreign'])).toThrow();
  });
  it('rejects two accounts for the same provider and external organization', async () => {
    const { state } = setup(async () => ({
      items: [connection, { ...connection, id: 'two' }],
      next_cursor: null,
      synchronization_available: false,
    }));
    await state.load();
    expect(() => state.apply('explicit', ['one', 'two'])).toThrow();
  });
  it('clears account names immediately and rejects late pages after organization or session change', async () => {
    let finish!: (value: unknown) => void;
    const { state, facade } = setup(
      () =>
        new Promise((resolve) => {
          finish = resolve;
        }),
    );
    const pending = state.load();
    facade.tenantId.set('other');
    expect(state.page().items).toEqual([]);
    finish({
      items: [connection],
      next_cursor: 'private-cursor',
      synchronization_available: false,
    });
    await pending;
    expect(state.page().items).toEqual([]);
    expect(state.page().next_cursor).toBeNull();
    expect(state.loading()).toBe(false);
  });
  it('saves the reviewed preference revision and reports a concurrent change without overwriting', async () => {
    const writes: unknown[] = [];
    const { state } = setup(async (method, path, options) => {
      if (method === 'PUT') {
        writes.push(options?.body);
        throw Object.assign(Error('private detail'), { status: 409 });
      }
      return path.endsWith('reader-selection')
        ? { revision: 7, connections: [selection] }
        : { items: [connection], next_cursor: null, synchronization_available: false };
    });
    await state.load();
    await state.loadPreference();
    expect(await state.save([])).toBe(false);
    expect(writes[0]).toMatchObject({ expected_revision: 7, connections: [] });
    expect(state.error()).toBe(
      'Your source account preference changed elsewhere. Reload it before saving.',
    );
    expect(state.preference()?.connections).toEqual([selection]);
    expect(await state.save([])).toBe(false);
    expect(writes).toHaveLength(1);
  });
});
