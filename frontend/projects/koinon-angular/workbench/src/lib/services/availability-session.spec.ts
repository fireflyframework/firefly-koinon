// Copyright 2026 Firefly Software Foundation
// SPDX-License-Identifier: Apache-2.0
import { signal } from '@angular/core';
import { describe, expect, it, vi } from 'vitest';
import type { KoinonTransport, RequestOptions } from '@fireflyframework/koinon-sdk';
import type { AssetAvailability } from '@fireflyframework/koinon-sdk/availability';
import type { KoinonFacade } from '../koinon-facade';
import type { KoinonClientContext } from './client-context';
import { AvailabilitySession } from './availability-session';
const value: AssetAvailability = {
  phase: 'complete',
  revision: { source_version_id: 'v1' },
  read: { state: 'ready', reason: 'CURRENT_TEXT_RECORDED' },
  search: { state: 'pending', reason: 'ACTIVE_INDEX_INCOMPLETE' },
  query: { state: 'not_applicable', reason: 'DOCUMENT' },
};
function fixture(transport: KoinonTransport) {
  const pair = signal<KoinonTransport | null>(transport);
  const revision = signal(0);
  const context = signal({ subject: 'actor-a' });
  const scope = {
    context,
    tenantId: signal('tenant'),
    workspaceId: signal('workspace'),
    projectId: signal('project'),
    parentId: signal('folder'),
  };
  const client = { revision, getTransport: () => pair() };
  return {
    scope,
    pair,
    revision,
    state: new AvailabilitySession(
      scope as unknown as KoinonFacade,
      client as unknown as KoinonClientContext,
    ),
  };
}
describe('bounded current-actor availability', () => {
  it('batches visible rows and never equates text availability with search readiness', async () => {
    const request = vi.fn<
      (method: string, path: string, options: RequestOptions) => Promise<unknown>
    >(async () => ({
      observed_at: '2026-11-01T00:00:00Z',
      items: { one: value, two: value },
    }));
    const { state } = fixture({ request } as unknown as KoinonTransport);
    state.sync();
    const one = state.watch('one');
    const two = state.watch('two');
    await vi.waitFor(() => expect(request).toHaveBeenCalledOnce());
    expect(request.mock.calls[0]![2].body).toEqual({
      asset_ids: ['one', 'two'],
      workspace_id: 'workspace',
    });
    await vi.waitFor(() => expect(state.get('one')?.search?.state).toBe('pending'));
    one();
    two();
    expect(state.get('one')).toBeUndefined();
  });
  it('discards actor A after B is bound without a paired transport, then accepts only B', async () => {
    let finish!: (value: unknown) => void;
    const request = vi.fn<
      (method: string, path: string, options: RequestOptions) => Promise<unknown>
    >(
      () =>
        new Promise((resolve) => {
          finish = resolve;
        }),
    );
    const { state, pair, revision, scope } = fixture({ request } as unknown as KoinonTransport);
    state.sync();
    const stop = state.watch('one');
    await vi.waitFor(() => expect(request).toHaveBeenCalledOnce());
    const signal = request.mock.calls[0]![2].signal!;
    scope.context.set({ subject: 'actor-b' });
    pair.set(null);
    revision.update((x) => x + 1);
    expect(state.get('one')).toBeUndefined();
    state.sync();
    expect(signal.aborted).toBe(true);
    finish({ observed_at: '2026-11-01T00:00:00Z', items: { one: value } });
    await Promise.resolve();
    expect(state.get('one')).toBeUndefined();
    expect(request).toHaveBeenCalledOnce();
    const b = vi.fn<(method: string, path: string, options: RequestOptions) => Promise<unknown>>(
      async () => ({
        observed_at: '2026-11-01T01:00:00Z',
        items: { one: { ...value, revision: { source_version_id: 'b' } } },
      }),
    );
    pair.set({ request: b } as unknown as KoinonTransport);
    revision.update((x) => x + 1);
    state.sync();
    await vi.waitFor(() => expect(state.get('one')?.revision?.source_version_id).toBe('b'));
    stop();
  });
  it('clears an observation when current authority context is replaced even for the same subject', async () => {
    const request = vi.fn<
      (method: string, path: string, options: RequestOptions) => Promise<unknown>
    >(async () => ({
      observed_at: '2026-11-01T00:00:00Z',
      items: { one: value },
    }));
    const { state, scope } = fixture({ request } as unknown as KoinonTransport);
    state.sync();
    const stop = state.watch('one');
    await vi.waitFor(() => expect(state.get('one')).toBeDefined());
    scope.context.set({ subject: 'actor-a' });
    expect(state.get('one')).toBeUndefined();
    stop();
  });
});
