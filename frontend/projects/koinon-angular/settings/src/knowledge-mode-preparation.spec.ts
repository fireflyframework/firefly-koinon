// Copyright 2026 Firefly Software Foundation
// SPDX-License-Identifier: Apache-2.0
import { TestBed } from '@angular/core/testing';
import {
  KoinonClient,
  type KoinonTransport,
  type HttpMethod,
  type RequestOptions,
  type KnowledgeModeTransitionView,
  type OrganizationKnowledgeSettingsInput,
  type KnowledgeModeTargetView,
  type KnowledgeModeRecoveryReceipt,
} from '@fireflyframework/koinon-sdk';
import { KoinonFacade, provideKoinonClient } from '@fireflyframework/koinon-angular';
import { KnowledgeModePreparation } from './knowledge-mode-preparation';

const input = {
  expected_revision: 3,
  documents: { answer_mode: 'rlm' },
  structured: {},
} as OrganizationKnowledgeSettingsInput;
function receipt(changes: Partial<KnowledgeModeTransitionView> = {}): KnowledgeModeTransitionView {
  return {
    id: 'mode',
    tenant_id: 'north',
    job_id: 'job',
    revision: 2,
    base_revision: 3,
    base_digest: 'a'.repeat(64),
    active_mode: 'rag',
    requested_mode: 'rlm',
    requested_settings: input,
    status: 'failed',
    stage: 'verify',
    counters: {},
    stage_milliseconds: {},
    pending_index_recoveries: 0,
    error_code: null,
    error: null,
    created_at: '2026-11-03T00:00:00Z',
    updated_at: '2026-11-03T00:00:00Z',
    ...changes,
  };
}
function mount(
  request: KoinonTransport['request'],
  permissions = ['settings:write', 'indexes:manage'],
) {
  const transport: KoinonTransport = {
    request,
    stream: () => {
      throw new Error('No stream');
    },
  };
  TestBed.configureTestingModule({
    providers: [
      KoinonFacade,
      KnowledgeModePreparation,
      ...provideKoinonClient(new KoinonClient({ transport }), transport),
    ],
  });
  const facade = TestBed.inject(KoinonFacade);
  facade.tenantId.set('north');
  facade.context.set({
    subject: 'admin',
    tenants: ['north', 'south'].map((id) => ({ id, name: id, roles: ['admin'], permissions })),
    memberships: [],
    workspaces: [],
  });
  const state = TestBed.inject(KnowledgeModePreparation);
  TestBed.tick();
  return { state, facade };
}

it('rechecks an unknown submission with the same key and exact payload', async () => {
  const keys: string[] = [],
    bodies: unknown[] = [];
  const { state } = mount(async <T>(method: HttpMethod, path: string, options?: RequestOptions) => {
    if (method === 'POST') {
      keys.push(String(options?.headers?.['Idempotency-Key']));
      bodies.push(options?.body);
      if (keys.length === 1) throw new Error('Controlled network interruption');
      return receipt() as T;
    }
    return { transition: null } as T;
  });
  expect(await state.create(input)).toBe(false);
  expect(state.unknown()).toBe(true);
  await state.load();
  expect(state.unknown()).toBe(true);
  await state.repeatRequest();
  expect(keys).toHaveLength(2);
  expect(keys[0]).toBe(keys[1]);
  expect(bodies).toEqual([input, input]);
  expect(state.value()?.id).toBe('mode');
});
it('does not expose late preparation receipts after an organization change', async () => {
  let release!: (value: unknown) => void;
  const { state, facade } = mount(
    async <T>() =>
      await new Promise<T>((resolve) => {
        release = resolve as typeof release;
      }),
  );
  const pending = state.load();
  facade.tenantId.set('south');
  TestBed.tick();
  release({ transition: receipt() });
  await pending;
  expect(state.value()).toBeNull();
  expect(state.targets()).toEqual([]);
});
it('requires explicit retry review and sends the current transition revision', async () => {
  const writes: unknown[] = [];
  const { state } = mount(async <T>(method: HttpMethod, path: string, options?: RequestOptions) => {
    if (method === 'POST') {
      writes.push(options?.body);
      return receipt({ revision: 3, status: 'cancelled' }) as T;
    }
    return (
      path.endsWith('/current') ? { transition: receipt() } : { items: [], next_cursor: null }
    ) as T;
  });
  await state.load();
  await state.act('retry');
  expect(writes).toEqual([]);
  state.reviewRetry.set(true);
  await state.act('retry');
  expect(writes).toEqual([{ expected_revision: 2 }]);
  expect(state.value()?.revision).toBe(3);
});
it('follows target cursors and preserves a cancelled parent during explicit index recovery', async () => {
  const calls: { path: string; body: unknown; query: unknown }[] = [];
  const target: KnowledgeModeTargetView = {
    id: 'target',
    kind: 'workspace',
    catalog_id: 'workspace',
    workspace_id: 'workspace',
    status: 'waiting',
    index_id: 'index',
    index_recovery: {
      index_id: 'index',
      job_id: null,
      state: 'required',
      activation_job_id: 'activation',
      activation_lease_until: null,
      index_status: 'activating',
      native_pointer_state: 'target',
      expected_revision: 7,
      expected_active_id: 'previous',
      expected_connection_revision: 4,
      actions: ['finish'],
      message: 'The native pointer is already applied.',
    },
  };
  const recovery: KnowledgeModeRecoveryReceipt = {
    ...target.index_recovery!,
    receipt_id: 'receipt',
    attempt_revision: 4,
    resolution_revision: 1,
    resolution: 'pending',
    workspace_id: 'workspace',
    native_workspace_id: 'native-workspace',
    native_index_id: 'set',
    provider_id: 'provider',
    model_id: 'embedding',
  };
  const { state } = mount(async <T>(method: HttpMethod, path: string, options?: RequestOptions) => {
    calls.push({ path, body: options?.body, query: options?.query });
    if (path.endsWith('/current'))
      return { transition: receipt({ status: 'cancelled', pending_index_recoveries: 1 }) } as T;
    if (path.endsWith('/recoveries')) return { items: [recovery], next_cursor: null } as T;
    if (path.endsWith('/targets'))
      return { items: [target], next_cursor: options?.query?.['after'] ? null : 'cursor-50' } as T;
    return {} as T;
  });
  await state.load();
  await state.more();
  expect(calls.at(-1)?.query).toEqual({ after: 'cursor-50', limit: 50 });
  state.reviewRecovery.set({ receipt: recovery, action: 'finish' });
  await state.recover();
  expect(
    calls.find((call) => call.path.endsWith('/knowledge-indexes/index/activate'))?.body,
  ).toEqual({
    expected_revision: 7,
    expected_active_id: 'previous',
    expected_connection_revision: 4,
    recovery: 'finish',
  });
  expect(state.value()?.status).toBe('cancelled');
  expect(calls.some((call) => call.path.endsWith('/retry'))).toBe(false);
});
it('does not enumerate preparation for a caller without organization settings authority', async () => {
  let count = 0;
  const { state } = mount(async <T>() => {
    ++count;
    return {} as T;
  }, ['knowledge:search']);
  await state.load();
  expect(count).toBe(0);
});
