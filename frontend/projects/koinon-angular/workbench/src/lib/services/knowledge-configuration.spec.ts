// Copyright 2026 Firefly Software Foundation SPDX-License-Identifier: Apache-2.0
import { TestBed } from '@angular/core/testing';
import {
  KoinonClient,
  KoinonError,
  type KoinonTransport,
  type KnowledgeConnection,
  type RequestOptions,
} from '@fireflyframework/koinon-sdk';
import { KoinonFacade, provideKoinonClient } from '@fireflyframework/koinon-angular';
import { KoinonKnowledgeConfiguration } from '../../../../settings/src/knowledge-configuration';
const connection = {
  id: 'binding',
  tenant_id: 'tenant',
  workspace_id: 'space',
  domain: 'documents',
  role: 'documents.answer',
  mode: 'provider',
  provider_id: 'provider',
  model_id: 'model',
  model_options: {},
  dimensions: null,
  storage_dimensions: null,
  space_id: null,
  embedding_fingerprint: null,
  enabled: true,
  revision: 7,
  created_by: 'member',
  updated_by: 'member',
  created_at: '2026-10-27T00:00:00Z',
  updated_at: '2026-10-27T00:00:00Z',
} satisfies KnowledgeConnection;
function setup(request: KoinonTransport['request']) {
  const transport: KoinonTransport = {
    request,
    stream: () => {
      throw new Error('Unexpected stream');
    },
  };
  TestBed.configureTestingModule({
    providers: [
      KoinonFacade,
      KoinonKnowledgeConfiguration,
      ...provideKoinonClient(new KoinonClient({ transport }), transport),
    ],
  });
  const facade = TestBed.inject(KoinonFacade);
  facade.tenantId.set('tenant');
  return { service: TestBed.inject(KoinonKnowledgeConfiguration), facade };
}
describe('knowledge model assignment requests', () => {
  it('loads only the selected scope and never reads credentials', async () => {
    const calls: [string, RequestOptions | undefined][] = [];
    const { service } = setup(
      async <T>(_method: unknown, path: string, options?: RequestOptions) => {
        calls.push([path, options]);
        return (
          path.endsWith('knowledge-roles')
            ? { roles: [], model_options_schema: {}, providers: [] }
            : { items: [connection] }
        ) as T;
      },
    );
    await service.load('space');
    expect(calls.map(([path]) => path)).toEqual([
      '/tenants/tenant/knowledge-roles',
      '/tenants/tenant/knowledge-connections',
    ]);
    expect(calls.every(([, options]) => options?.query?.['workspace_id'] === 'space')).toBe(true);
    expect(service.connections()).toEqual([connection]);
  });
  it('sends the observed revision for update and removal', async () => {
    const calls: [unknown, string, RequestOptions | undefined][] = [];
    const { service } = setup(
      async <T>(method: unknown, path: string, options?: RequestOptions) => {
        calls.push([method, path, options]);
        return (
          method === 'PUT'
            ? connection
            : method === 'DELETE'
              ? { deleted: true }
              : path.endsWith('knowledge-roles')
                ? { roles: [], model_options_schema: {} }
                : { items: [connection] }
        ) as T;
      },
    );
    await service.load('space');
    await service.save(
      {
        domain: 'documents',
        role: 'documents.answer',
        workspace_id: 'space',
        mode: 'current_agent',
      },
      connection,
    );
    expect(calls.find(([method]) => method === 'PUT')?.[2]?.body).toEqual({
      domain: 'documents',
      role: 'documents.answer',
      workspace_id: 'space',
      mode: 'current_agent',
      expected_revision: 7,
    });
    await service.remove(connection);
    expect(calls.find(([method]) => method === 'DELETE')?.[2]?.query).toEqual({
      expected_revision: 7,
    });
    expect(service.notice()).toBe('Workspace override removed.');
  });
  it('retains a revision conflict without reporting success', async () => {
    const { service } = setup(async () => {
      throw new KoinonError(409, 'KNOWLEDGE_CONNECTION_CONFLICT', 'Reload the current revision');
    });
    expect(
      await service.save({ domain: 'documents', role: 'documents.answer' }, connection),
    ).toBeNull();
    expect(service.notice()).toBe('');
    expect(service.error()).toMatchObject({ code: 'KNOWLEDGE_CONNECTION_CONFLICT' });
  });
  it('discards an older scope response', async () => {
    let release!: () => void;
    const wait = new Promise<void>((resolve) => {
      release = resolve;
    });
    const { service } = setup(
      async <T>(_method: unknown, path: string, options?: RequestOptions) => {
        if (options?.query?.['workspace_id'] === 'first') await wait;
        return (
          path.endsWith('knowledge-roles')
            ? { roles: [], model_options_schema: {} }
            : { items: options?.query?.['workspace_id'] === 'first' ? [connection] : [] }
        ) as T;
      },
    );
    const first = service.load('first');
    await service.load('second');
    release();
    await first;
    expect(service.scope()).toBe('second');
    expect(service.connections()).toEqual([]);
    expect(service.pending()).toBe(false);
  });
  for (const status of [401, 403])
    it(`handles ${status} without confusing denial with expiry`, async () => {
      const { service, facade } = setup(async () => {
        throw new KoinonError(status, 'DENIED', 'Access was denied');
      });
      await service.load();
      expect(facade.authRequired()).toBe(status === 401);
      expect(service.error()?.message).toBe('Access was denied');
    });
});
