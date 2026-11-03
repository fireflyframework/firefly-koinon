// Copyright 2026 Firefly Software Foundation
// SPDX-License-Identifier: Apache-2.0
import { createCommunicationsApi } from '@fireflyframework/koinon-sdk/communications';
import { KoinonError } from '@fireflyframework/koinon-sdk';
import { CommunicationsObservation } from '../../../../communications/admin/communications-observation';
const filter = { page: 2, page_size: 25, status: '', kind: '', from: '', to: '' } as const;
function fixture() {
  let scope = { key: 'one', tenantId: 'north', allowed: true };
  let status = 'queued';
  let fail = 0;
  let wait: Promise<void> | null = null;
  const denied: number[] = [];
  const calls: { method: string; path: string; signal?: AbortSignal }[] = [];
  const api = createCommunicationsApi({
    stream: () => {
      throw Error('Unexpected stream');
    },
    request: async <T>(method: string, path: string, options: { signal?: AbortSignal } = {}) => {
      calls.push({ method, path, signal: options.signal });
      if (wait) await wait;
      if (fail) throw new KoinonError(fail, 'FIXTURE', 'Private provider detail');
      if (path.endsWith('/capabilities')) return { state: 'ready', issues: [] } as T;
      if (path.endsWith('/policy')) return { revision: 1, rules: [] } as T;
      if (path.includes('/deliveries/'))
        return { id: 'mail', status, recipient_display: 'Alex' } as T;
      return { items: [{ id: 'mail', status }], page: 2, page_size: 25, total: 1, pages: 2 } as T;
    },
  });
  return {
    state: new CommunicationsObservation({
      scope: () => scope,
      api: () => api,
      denied: (s) => denied.push(s),
    }),
    calls,
    denied,
    scope: (change: Partial<typeof scope>) => {
      scope = { ...scope, ...change };
    },
    fail: (value: number) => {
      fail = value;
    },
    status: (value: string) => {
      status = value;
    },
    wait: (value: Promise<void> | null) => {
      wait = value;
    },
  };
}
it('reads only the applied page and selected delivery without sends or probes', async () => {
  const f = fixture();
  await f.state.load('history', filter, 'mail');
  expect(f.state.view().deliveries?.page).toBe(2);
  expect(f.calls).toHaveLength(2);
  expect(f.calls.every((call) => call.method === 'GET')).toBe(true);
  f.status('delivered');
  await f.state.load('history', filter, 'mail', false, true);
  expect(f.state.view().selected?.status).toBe('delivered');
  expect(f.calls.some((call) => /recovery|observations/.test(call.path))).toBe(false);
});
it('preserves policy while background observations change', async () => {
  const f = fixture();
  await f.state.load('service', filter, null, true);
  const policy = f.state.view().policy;
  await f.state.load('service', filter, null, false, true);
  expect(f.state.view().policy).toBe(policy);
  expect(f.calls.filter((call) => call.path.endsWith('/policy'))).toHaveLength(1);
});
it('retains stale during slow retries and prevents overlapping reads', async () => {
  const f = fixture();
  await f.state.load('history', filter, 'mail');
  f.fail(503);
  await f.state.load('history', filter, 'mail', false, true);
  expect(f.state.view().stale).toBe(true);
  f.fail(0);
  let release!: () => void;
  f.wait(
    new Promise<void>((resolve) => {
      release = resolve;
    }),
  );
  f.status('delivered');
  const pending = f.state.load('history', filter, 'mail', false, true);
  expect(f.state.view().stale).toBe(true);
  expect(f.state.view().selected?.status).toBe('queued');
  const count = f.calls.length;
  await f.state.load('history', filter, 'mail', false, true);
  expect(f.calls).toHaveLength(count);
  release();
  await pending;
  expect(f.state.view().stale).toBe(false);
  expect(f.state.view().selected?.status).toBe('delivered');
});
for (const status of [401, 403])
  it(`clears private rows and latches ${status} until authority changes`, async () => {
    const f = fixture();
    await f.state.load('history', filter, 'mail');
    f.fail(status);
    await f.state.load('history', filter, 'mail', false, true);
    expect(f.state.view().deliveries).toBeNull();
    expect(f.state.view().selected).toBeNull();
    expect(f.denied).toEqual([status]);
    const count = f.calls.length;
    f.fail(0);
    await f.state.load('history', filter, 'mail');
    expect(f.calls).toHaveLength(count);
    f.scope({ key: 'renewed' });
    await f.state.load('history', filter, 'mail');
    expect(f.state.view().selected?.id).toBe('mail');
  });
it('clears on expiry and never reveals an old scope after a late response', async () => {
  const f = fixture();
  await f.state.load('history', filter, 'mail');
  let release!: () => void;
  f.wait(
    new Promise<void>((resolve) => {
      release = resolve;
    }),
  );
  const pending = f.state.load('history', filter, 'mail', false, true);
  f.scope({ key: 'two', tenantId: 'south' });
  expect(f.state.view().selected).toBeNull();
  f.state.sync();
  expect(f.calls.at(-1)?.signal?.aborted).toBe(true);
  release();
  await pending;
  expect(f.state.view().selected).toBeNull();
  f.wait(null);
  await f.state.load('history', filter, 'mail');
  f.scope({ allowed: false });
  f.state.sync();
  expect(f.state.view().deliveries).toBeNull();
  f.state.dispose();
});
