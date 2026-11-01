// Copyright 2026 Firefly Software Foundation
// SPDX-License-Identifier: Apache-2.0
import {
  KoinonClient,
  type Configuration,
  type HttpMethod,
  type KnowledgeConnection,
  type KnowledgeIndexView,
  type KoinonTransport,
  type RequestOptions,
} from '@fireflyframework/koinon-sdk';
import { IndexManagementState } from './index-management-state';
import { IndexActionJournal } from './index-management-journal';
import type { IndexManagementScope } from './index-management-contract';
function setup() {
  let scope: IndexManagementScope = {
    owner: {},
    subject: 'issuer|alex',
    tenantId: 'north',
    workspaceId: 'space',
    domain: 'documents',
    clientRevision: 0,
    read: true,
    manage: true,
  };
  let target = {
    id: 'target',
    tenant_id: 'north',
    workspace_id: 'space',
    domain: 'documents',
    native_id: 'native',
    space_id: 'new-space',
    provider_kind: 'openai',
    provider_id: 'provider',
    model_id: 'embedding',
    dimensions: 1536,
    storage_dimensions: 1536,
    status: 'ready',
    active: false,
    revision: 2,
    chunk_count: 3,
    vector_count: 3,
    indexed: true,
    qualification: 'coverage_and_ann_passed',
  } as KnowledgeIndexView;
  let connection = {
    id: 'connection',
    tenant_id: 'north',
    workspace_id: null,
    domain: 'documents',
    role: 'documents.embedding',
    revision: 4,
    enabled: true,
  } as KnowledgeConnection;
  let active = 'previous';
  const configuration = {
    providers: [
      {
        id: 'provider',
        name: 'Embeddings',
        kind: 'openai',
        enabled: true,
        revision: 1,
        model_ids: ['embedding'],
      },
    ],
  } as Configuration;
  const calls: { method: HttpMethod; path: string; options?: RequestOptions }[] = [];
  let override:
    | ((method: HttpMethod, path: string, options?: RequestOptions) => Promise<unknown> | undefined)
    | undefined;
  const transport: KoinonTransport = {
    stream: () => {
      throw Error('Unexpected stream');
    },
    request: async <T>(method: HttpMethod, path: string, options?: RequestOptions) => {
      calls.push({ method, path, options });
      const intercepted = override?.(method, path, options);
      if (intercepted) return (await intercepted) as T;
      if (path.endsWith('/configuration')) return configuration as T;
      if (path.endsWith('/knowledge-connections'))
        return { items: options?.query?.['workspace_id'] ? [] : [connection] } as T;
      if (path.endsWith('/knowledge-index-choices'))
        return {
          items: active ? [{ ...target, id: active, active: true }] : [],
          total: active ? 1 : 0,
          limit: 100,
          offset: 0,
        } as T;
      if (path.endsWith('/knowledge-indexes/plan'))
        return {
          tenant_id: 'north',
          workspace_id: 'space',
          domain: 'documents',
          provider_id: 'provider',
          provider_kind: 'openai',
          provider_revision: 1,
          model_id: 'embedding',
          dimensions: 1536,
          storage_dimensions: 1536,
          qualification: 'probe_passed',
          expected_connection_revision: 4,
          active_space_id: 'old-space',
          active_index_id: 'previous',
          chunk_count: 3,
          warnings: [],
        } as T;
      if (path.endsWith('/knowledge-indexes') && method === 'GET')
        return {
          items: [target],
          total: 26,
          offset: options?.query?.['offset'] ?? 0,
          limit: 25,
        } as T;
      if (path.endsWith('/knowledge-indexes') && method === 'POST') {
        target = { ...target, status: 'queued' };
        return { index: target, job_id: 'job' } as T;
      }
      if (path.endsWith('/activate')) {
        target = { ...target, status: 'active', active: true, revision: target.revision + 1 };
        active = 'target';
        return target as T;
      }
      if (path.endsWith('/cancel')) {
        target = { ...target, status: 'cancelled', revision: target.revision + 1 };
        return target as T;
      }
      if (path.endsWith('/resume')) {
        target = { ...target, status: 'queued', revision: target.revision + 1 };
        return { index: target, job_id: 'job-retry' } as T;
      }
      if (path.endsWith('/knowledge-indexes/target')) return target as T;
      throw Error('Unexpected route ' + path);
    },
  };
  const values = new Map<string, string>(),
    storage = {
      getItem: (key: string) => values.get(key) ?? null,
      setItem: (key: string, value: string) => {
        values.set(key, value);
      },
      removeItem: (key: string) => {
        values.delete(key);
      },
    };
  const client = new KoinonClient({ transport });
  const make = () =>
    new IndexManagementState({
      scope: () => scope,
      client: () => client,
      journal: new IndexActionJournal(storage),
    });
  const state = make();
  return {
    state,
    make,
    calls,
    scope: () => scope,
    setScope: (next: Partial<IndexManagementScope>) => {
      scope = { ...scope, ...next };
    },
    target: () => target,
    setTarget: (next: Partial<KnowledgeIndexView>) => {
      target = { ...target, ...next };
    },
    setConnection: (revision: number) => {
      connection = { ...connection, revision };
    },
    intercept: (fn: typeof override) => {
      override = fn;
    },
  };
}
const input = {
  workspace_id: 'space',
  domain: 'documents' as const,
  provider_id: 'provider',
  model_id: 'embedding',
};
it('reads scoped paged indexes and never probes a model while refreshing', async () => {
  const s = setup();
  await s.state.load(2);
  expect(s.state.view().page).toBe(2);
  const list = s.calls.find((call) => call.path.endsWith('/knowledge-indexes'))!;
  expect(list.options?.query).toEqual({
    workspace_id: 'space',
    domain: 'documents',
    limit: 25,
    offset: 25,
  });
  expect(
    s.calls.every((call) => call.method === 'GET' && call.options?.signal instanceof AbortSignal),
  ).toBe(true);
  expect(s.state.view().active?.id).toBe('previous');
});
it('discards a late previous-owner response and aborts its read', async () => {
  const s = setup();
  let resolve!: (value: unknown) => void;
  const pending = new Promise<unknown>((yes) => {
    resolve = yes;
  });
  s.intercept((method, path) =>
    method === 'GET' && path.endsWith('/knowledge-indexes') ? pending : undefined,
  );
  const loaded = s.state.load();
  s.setScope({ owner: {}, subject: 'issuer|sam' });
  s.state.syncScope();
  resolve({ items: [s.target()], total: 1, offset: 0, limit: 25 });
  await loaded;
  expect(s.state.view().rows).toEqual([]);
  expect(s.calls[0].options?.signal?.aborted).toBe(true);
});
it('requires an explicit plan then uses its revisions and one stable keyed build', async () => {
  const s = setup();
  await s.state.load();
  await s.state.plan(input);
  await Promise.all([s.state.build(), s.state.build()]);
  const writes = s.calls.filter(
    (call) => call.method === 'POST' && call.path.endsWith('/knowledge-indexes'),
  );
  expect(writes).toHaveLength(1);
  expect(writes[0].options?.headers?.['Idempotency-Key']).toBeTruthy();
  expect(writes[0].options?.body).toMatchObject({
    ...input,
    expected_active_id: 'previous',
    expected_connection_revision: 4,
  });
  expect(s.state.view().selected?.status).toBe('queued');
});
it('does not create when the reviewed embedding revision changed', async () => {
  const s = setup();
  await s.state.load();
  await s.state.plan(input);
  s.setConnection(5);
  await s.state.build();
  expect(
    s.calls.filter((call) => call.method === 'POST' && call.path.endsWith('/knowledge-indexes')),
  ).toHaveLength(0);
  expect(s.state.view().error).toContain('changed');
});
it('retains an unknown build across reload and resubmits only explicitly with the exact original key', async () => {
  const s = setup();
  await s.state.load();
  await s.state.plan(input);
  s.intercept((method, path) =>
    method === 'POST' && path.endsWith('/knowledge-indexes')
      ? Promise.reject(new TypeError('network'))
      : undefined,
  );
  await s.state.build();
  const first = s.calls.find(
    (call) => call.method === 'POST' && call.path.endsWith('/knowledge-indexes'),
  )!;
  expect(s.state.view().unknown?.write.operation).toBe('create');
  const restored = s.make();
  await restored.load();
  expect(restored.view().unknown).toEqual(s.state.view().unknown);
  expect(
    s.calls.filter((call) => call.method === 'POST' && call.path.endsWith('/knowledge-indexes')),
  ).toHaveLength(1);
  s.intercept(undefined);
  await restored.repeatSaved();
  const writes = s.calls.filter(
    (call) => call.method === 'POST' && call.path.endsWith('/knowledge-indexes'),
  );
  expect(writes).toHaveLength(2);
  expect(writes[1].options?.headers).toEqual(first.options?.headers);
  expect(writes[1].options?.body).toEqual(first.options?.body);
});
it('requires review and refuses activation when the target changes before confirmation', async () => {
  const s = setup();
  await s.state.load();
  await s.state.select('target');
  await s.state.reviewAction('activate');
  s.setTarget({ revision: 3 });
  await s.state.confirmAction();
  expect(s.calls.some((call) => call.path.endsWith('/activate'))).toBe(false);
  expect(s.state.view().error).toContain('changed');
});
it('does not request plans or mutations without current workspace management rights', async () => {
  const s = setup();
  s.setScope({ manage: false });
  await s.state.load();
  await s.state.plan(input);
  await s.state.build();
  expect(s.calls.every((call) => call.method === 'GET')).toBe(true);
  expect(
    s.calls.some(
      (call) =>
        call.path.endsWith('/knowledge-connections') || call.path.endsWith('/configuration'),
    ),
  ).toBe(false);
});
it('keeps an uncertain activation inspectable and requires fresh explicit recovery', async () => {
  const s = setup();
  await s.state.load();
  await s.state.select('target');
  await s.state.reviewAction('activate');
  s.intercept((method, path) => {
    if (method === 'POST' && path.endsWith('/activate')) {
      s.setTarget({ status: 'activating', revision: 3, recovery_required: true });
      return Promise.reject(new TypeError('lost acknowledgement'));
    }
    return undefined;
  });
  await s.state.confirmAction();
  expect(s.state.view().unknown?.write.operation).toBe('activate');
  s.intercept(undefined);
  await s.state.inspectSaved();
  await s.state.reviewAction('finish');
  await s.state.confirmAction();
  const writes = s.calls.filter((call) => call.path.endsWith('/activate'));
  expect(writes).toHaveLength(2);
  expect(writes[1].options?.body).toMatchObject({ expected_revision: 3, recovery: 'finish' });
  expect(s.state.view().unknown).toBeNull();
});
it('resolves an uncertain cancellation from its recorded target without repeating the write', async () => {
  const s = setup();
  s.setTarget({ status: 'building', indexed: false });
  await s.state.load();
  await s.state.select('target');
  await s.state.reviewAction('cancel');
  s.intercept((method, path) => {
    if (method === 'POST' && path.endsWith('/cancel')) {
      s.setTarget({ status: 'cancelled', revision: 3 });
      return Promise.reject(new TypeError('lost acknowledgement'));
    }
    return undefined;
  });
  await s.state.confirmAction();
  s.intercept(undefined);
  await s.state.inspectSaved();
  expect(s.calls.filter((call) => call.path.endsWith('/cancel'))).toHaveLength(1);
  expect(s.state.view().unknown).toBeNull();
  expect(s.state.view().notice).toContain('observed');
});
it('does not dispatch a saved mutation after current management authority is lost', async () => {
  const s = setup();
  await s.state.load();
  await s.state.plan(input);
  s.intercept((method, path) =>
    method === 'POST' && path.endsWith('/knowledge-indexes')
      ? Promise.reject(new TypeError('network'))
      : undefined,
  );
  await s.state.build();
  const count = s.calls.length;
  s.setScope({ manage: false });
  await s.state.repeatSaved();
  expect(s.calls).toHaveLength(count);
});
it('refreshes selected details from their current record even off the displayed page', async () => {
  const s = setup();
  await s.state.load();
  await s.state.select('target');
  s.setTarget({ status: 'building', revision: 3, vector_count: 1 });
  await s.state.load(2);
  expect(s.state.view().selected).toMatchObject({
    status: 'building',
    revision: 3,
    vector_count: 1,
  });
});

it('does not plan from an incomplete or conflicting active inventory', async () => {
  const s = setup();
  s.intercept((method, path) =>
    method === 'GET' && path.endsWith('/knowledge-index-choices')
      ? Promise.resolve({ items: [], total: 1, offset: 0, limit: 100 })
      : undefined,
  );
  await s.state.load();
  expect(s.state.view().activeKnown).toBe(false);
  expect(s.state.view().error).toContain('could not be verified');
  await s.state.plan(input);
  await s.state.build();
  expect(s.calls.some((call) => call.method === 'POST' && pathIsCreate(call.path))).toBe(false);
});
function pathIsCreate(path: string) {
  return path.endsWith('/knowledge-indexes');
}
it('does not dispatch a reviewed activation after the preflight loses authority', async () => {
  const s = setup();
  await s.state.load();
  await s.state.select('target');
  await s.state.reviewAction('activate');
  s.intercept((method, path) => {
    if (method === 'GET' && path.endsWith('/knowledge-index-choices')) {
      s.setScope({ manage: false });
      return Promise.resolve({ items: [], total: 0, offset: 0, limit: 100 });
    }
    return undefined;
  });
  await s.state.confirmAction();
  expect(s.calls.some((call) => call.method === 'POST')).toBe(false);
});
