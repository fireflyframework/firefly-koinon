// Copyright 2026 Firefly Software Foundation SPDX-License-Identifier: Apache-2.0
import { TestBed } from '@angular/core/testing';
import {
  KoinonClient,
  KoinonError,
  type CatalogEntry,
  type ContextResponse,
  type KoinonTransport,
  type RequestOptions,
  type HttpMethod,
} from '@fireflyframework/koinon-sdk';
import { KOINON_TENANT_RESOLVER, type KoinonTenantResolver, provideKoinonClient } from './client-provider';
import { KoinonFacade } from './koinon-facade';
const entry = (id: string, tenant = 'tenant-one'): CatalogEntry => ({
  id,
  tenant_id: tenant,
  kind: 'workspace',
  name: 'Evidence workspace',
  description: '',
  status: 'ready',
  parent_id: null,
  workspace_id: id,
  project_id: null,
  metadata: {},
  created_at: '2026-10-26T00:00:00Z',
});
const context: ContextResponse = {
  subject: 'synthetic-user',
  tenants: [
    {
      id: 'tenant-one',
      name: 'Synthetic organization',
      roles: ['editor'],
      permissions: ['catalog:read', 'catalog:write', 'ingest:write'],
    },
    {
      id: 'tenant-two',
      name: 'Second organization',
      roles: ['viewer'],
      permissions: ['catalog:read'],
    },
  ],
  memberships: [],
  workspaces: [],
};
function setup(
  handler: (method: HttpMethod, path: string, options?: RequestOptions) => Promise<unknown>,
  resolver?: KoinonTenantResolver,
) {
  const transport: KoinonTransport = {
    stream: () => {
      throw new Error('Unexpected streaming request in a catalog test');
    },
    request: <T>(method: HttpMethod, path: string, options?: RequestOptions) =>
      handler(method, path, options) as Promise<T>,
  };
  const client = new KoinonClient({ transport });
  TestBed.configureTestingModule({
    providers: [KoinonFacade, ...provideKoinonClient(client, transport),
      ...(resolver ? [{ provide: KOINON_TENANT_RESOLVER, useValue: resolver }] : []),
    ],
  });
  return TestBed.inject(KoinonFacade);
}
describe('scoped knowledge facade', () => {
  it('loads observed catalog data using the selected tenant', async () => {
    const facade = setup(async (_method, path) =>
      path === '/context' ? context : { items: [entry('workspace-one')] },
    );
    await facade.bootstrap();
    expect(facade.entries().map((x) => x.id)).toEqual(['workspace-one']);
  });
  it('reports denied creation without fabricating a saved item', async () => {
    const facade = setup(async (method, path) => {
      if (path === '/context') return context;
      if (method === 'POST') throw new KoinonError(403, 'DENIED', 'Workspace access denied');
      return { items: [] };
    });
    await facade.bootstrap();
    expect(await facade.create({ kind: 'workspace', name: 'New workspace' })).toBe(false);
    expect(facade.entries()).toEqual([]);
    expect(facade.error()).toBe('Workspace access denied');
    expect(facade.pending()).toBe(false);
  });
  it('never shows a stale catalog response after switching tenants', async () => {
    let resolveOld!: (value: unknown) => void;
    const facade = setup(async (_method, path) => {
      if (path === '/context') return context;
      if (path.includes('tenant-one'))
        return new Promise((resolve) => {
          resolveOld = resolve;
        });
      return { items: [entry('workspace-two', 'tenant-two')] };
    });
    const first = facade.bootstrap();
    await new Promise((resolve) => setTimeout(resolve, 0));
    await facade.selectTenant('tenant-two');
    resolveOld({ items: [entry('workspace-one')] });
    await first;
    expect(facade.entries().map((x) => x.tenant_id)).toEqual(['tenant-two']);
    expect(facade.selected()).toBe(null);
  });
});

describe('mutation context changes', () => {
  it('does not report an old-scope mutation as confirmed in the new tenant', async () => {
    let complete!: (value: unknown) => void;
    const facade = setup(async (method, path) => {
      if (path === '/context') return context;
      if (method === 'POST')
        return new Promise((resolve) => {
          complete = resolve;
        });
      return { items: [] };
    });
    await facade.bootstrap();
    const creating = facade.create({ kind: 'workspace', name: 'Old scope' });
    await facade.selectTenant('tenant-two');
    complete(entry('old-scope'));
    expect(await creating).toBe(false);
    expect(facade.entries()).toEqual([]);
    expect(facade.notice()).toBe('');
  });
});

describe('host transport errors', () => {
  it('recognizes authentication denial from a separately bundled SDK error', async () => {
    const facade = setup(async () => {
      throw Object.assign(new Error('Sign in is required'), {
        status: 401,
        code: 'UNAUTHENTICATED',
      });
    });
    await facade.bootstrap();
    expect(facade.authRequired()).toBe(true);
    expect(facade.error()).toBe('Sign in is required');
  });
});

describe('host client changes', () => {
  it('resolves the host preference from fresh context before the first catalog request', async () => {
    const events: string[] = [];
    const facade = setup(async (_method, path) => {
      events.push(path);
      return path === '/context' ? context : { items: [] };
    }, (fresh, requested) => {
      expect(fresh.subject).toBe('synthetic-user');
      expect(requested).toBe('tenant-one');
      events.push('resolve');
      return 'tenant-two';
    });
    await facade.bootstrap('tenant-one');
    expect(events).toEqual(['/context', 'resolve', '/tenants/tenant-two/catalog']);
  });
  it('does not request an organization absent from fresh context even when a host resolver returns it', async () => {
    const reads: string[] = [];
    const facade = setup(async (_method, path) => {
      if (path === '/context') return context;
      reads.push(path);
      return { items: [] };
    }, () => 'revoked');
    await facade.bootstrap();
    expect(reads).toEqual(['/tenants/tenant-one/catalog']);
  });
  it('does not carry a previous identity selection into the next identity context', async () => {
    let current = context;
    const facade = setup(async (_method, path) => path === '/context' ? current : { items: [] });
    await facade.bootstrap();
    await facade.selectTenant('tenant-two');
    current = { ...context, subject: 'other-person' };
    await facade.bootstrap();
    expect(facade.tenantId()).toBe('tenant-one');
  });
  it('retains a selected authorized organization when retrying with reordered context', async () => {
    let current = context;
    const reads: string[] = [];
    const facade = setup(async (_method, path) => {
      if (path === '/context') return current;
      reads.push(path);
      return { items: [] };
    });
    await facade.bootstrap();
    await facade.selectTenant('tenant-two');
    current = { ...context, tenants: [...context.tenants] };
    await facade.bootstrap();
    expect(facade.tenantId()).toBe('tenant-two');
    expect(reads.at(-1)).toBe('/tenants/tenant-two/catalog');
  });
  it('clears scoped state without a catalog request when fresh context has no memberships', async () => {
    let current = context;
    const reads: string[] = [];
    const facade = setup(async (_method, path) => {
      if (path === '/context') return current;
      reads.push(path);
      return { items: [entry('old-workspace')] };
    });
    await facade.bootstrap();
    current = { ...context, tenants: [] };
    await facade.bootstrap();
    expect(facade.tenantId()).toBe('');
    expect(facade.entries()).toEqual([]);
    expect(reads).toEqual(['/tenants/tenant-one/catalog']);
  });
  it('discards the previous identity context when a new host client is supplied', async () => {
    let oldContext!: (value: unknown) => void;
    const facade = setup(async (_method, path) =>
      path === '/context'
        ? new Promise((resolve) => {
            oldContext = resolve;
          })
        : { items: [] },
    );
    const old = facade.bootstrap();
    const transport: KoinonTransport = {
      stream: () => {
        throw new Error('Unexpected streaming request in a catalog test');
      },
      request: async <T>(_method: HttpMethod, path: string) =>
        (path === '/context'
          ? { ...context, subject: 'new-subject', tenants: [context.tenants[1]] }
          : { items: [] }) as T,
    };
    facade.bindClient(new KoinonClient({ transport }));
    await facade.bootstrap('tenant-two');
    oldContext(context);
    await old;
    expect(facade.context()?.subject).toBe('new-subject');
    expect(facade.tenantId()).toBe('tenant-two');
  });
});
describe('server-paged Library', () => {
  it('uses the server projection and total without paging cached raw entries', async () => {
    const requests: RequestOptions[] = [];
    const facade = setup(async (_method, path, options) => {
      if (path === '/context') return context;
      requests.push(options ?? {});
      return { items: [entry('observed-page')], total: 51, page: 2, page_size: 25, pages: 3 };
    });
    await facade.bootstrap();
    await facade.loadLibrary({ page: 2, q: 'policy', sort: 'updated_at', order: 'desc' });
    expect(requests.at(-1)?.query).toMatchObject({
      view: 'library',
      page: 2,
      page_size: 25,
      q: 'policy',
      sort: 'updated_at',
      order: 'desc',
    });
    expect(facade.libraryPage().total).toBe(51);
    expect(facade.libraryPage().items.map((x) => x.id)).toEqual(['observed-page']);
  });
  it('discards a stale filtered page in the same tenant', async () => {
    let resolve!: (value: unknown) => void;
    const facade = setup(async (_method, path, options) =>
      path === '/context'
        ? context
        : options?.query?.['q'] === 'old'
          ? new Promise((r) => (resolve = r))
          : { items: [entry('new-page')], total: 1, page: 1, page_size: 25, pages: 1 },
    );
    await facade.bootstrap();
    const old = facade.loadLibrary({ q: 'old' });
    await facade.loadLibrary({ q: 'new' });
    resolve({ items: [entry('old-page')], total: 1, page: 1, page_size: 25, pages: 1 });
    await old;
    expect(facade.libraryPage().items[0].id).toBe('new-page');
  });
});

it('uses server workspace capabilities without granting tenant settings or trusting membership roles', () => {
  const facade = setup(async () => ({ items: [] }));
  const scoped = {
    ...context,
    tenants: [{ ...context.tenants[0], permissions: [] }],
    workspaces: [entry('space')],
    workspace_permissions: { space: ['catalog:read', 'catalog:write', 'members:write'] },
    memberships: [
      {
        id: 'grant',
        tenant_id: 'tenant-one',
        subject: context.subject,
        workspace_id: 'space',
        role: 'admin' as const,
        active: true,
      },
    ],
  };
  facade.context.set(scoped);
  facade.tenantId.set('tenant-one');
  facade.workspaceId.set('space');
  expect(facade.canManageMembers()).toBe(true);
  expect(facade.canWrite()).toBe(true);
  expect(facade.tenantPermissions().has('settings:write')).toBe(false);
  const restricted = { ...scoped, workspace_permissions: { space: ['catalog:read'] } };
  facade.context.set(restricted);
  expect(facade.canManageMembers()).toBe(false);
  expect(facade.canWrite()).toBe(false);
  facade.tenantId.set('tenant-two');
  expect(facade.permissions().size).toBe(0);
});

it('ignores malformed capabilities, archived workspaces and role hints without server capabilities', async () => {
  const data = {
    ...context,
    tenants: [{ ...context.tenants[0], permissions: [] }],
    workspaces: [entry('space')],
    workspace_permissions: { space: ['members:write', 17] },
    memberships: [
      {
        id: 'grant',
        subject: context.subject,
        tenant_id: 'tenant-one',
        workspace_id: 'space',
        role: 'admin',
        active: true,
      },
    ],
  };
  const facade = setup(async (_method, path) => (path === '/context' ? data : { items: [] }));
  await facade.bootstrap();
  facade.workspaceId.set('space');
  expect(facade.canManageMembers()).toBe(false);
  facade.context.set(
    JSON.parse(
      JSON.stringify({
        ...data,
        workspace_permissions: { space: ['members:write'] },
        workspaces: [{ ...entry('space'), status: 'archived' }],
      }),
    ),
  );
  expect(facade.canManageMembers()).toBe(false);
  const legacy = { ...data };
  delete (legacy as { workspace_permissions?: unknown }).workspace_permissions;
  facade.context.set(JSON.parse(JSON.stringify(legacy)));
  expect(facade.canManageMembers()).toBe(false);
});
it('clears collection filters when changing workspace while retaining sort and page size', async () => {
  const calls: RequestOptions[] = [];
  const facade = setup(async (_method, path, options) => {
    if (path === '/context') return context;
    calls.push(options ?? {});
    return { items: [] };
  });
  await facade.bootstrap();
  await facade.loadLibrary({
    q: 'policy',
    kind: 'document',
    status: 'ready',
    tag: 'policy',
    format: 'pdf',
    page: 3,
    page_size: 50,
    sort: 'updated_at',
    order: 'desc',
  });
  await facade.setWorkspace('another-space');
  expect(calls.at(-1)?.query).toMatchObject({
    workspace_id: 'another-space',
    page: 1,
    page_size: 50,
    sort: 'updated_at',
    order: 'desc',
    q: '',
    kind: undefined,
    status: undefined,
    tag: undefined,
    format: undefined,
  });
});

it('requests only server-paginated spaces at the Library home on bootstrap, refresh and tenant changes', async () => {
  const queries: RequestOptions[] = [];
  const facade = setup(async (_method, path, options) => {
    if (path === '/context') return context;
    queries.push(options || {});
    return { items: [entry('workspace')], total: 1, page: 1, page_size: 25, pages: 1 };
  });
  await facade.bootstrap();
  expect(queries[0]?.query).toMatchObject({ view: 'library', kind: 'workspace', page: 1 });
  expect(facade.libraryPage().total).toBe(1);
  await facade.refresh();
  expect(queries.at(-1)?.query?.['kind']).toBe('workspace');
  await facade.selectTenant('tenant-two');
  expect(queries.at(-1)?.query?.['kind']).toBe('workspace');
});
it('preserves child-folder kind filters and keeps global knowledge search separate', async () => {
  const calls: { path: string; options: RequestOptions }[] = [];
  const facade = setup(async (_method, path, options) => {
    if (path === '/context') return context;
    calls.push({ path, options: options || {} });
    return path.endsWith('/search') ? { sources: [], answer: null } : { items: [] };
  });
  await facade.bootstrap();
  facade.workspaceId.set('workspace');
  facade.projectId.set('project');
  facade.parentId.set('folder');
  await facade.loadLibrary({ kind: 'document', page: 2 });
  expect(calls.at(-1)?.options.query).toMatchObject({
    kind: 'document',
    parent_id: 'folder',
    workspace_id: 'workspace',
    page: 2,
  });
  await facade.search('operating policy', false);
  expect(calls.at(-1)?.path).toContain('/search');
  expect(calls.at(-1)?.options.body).not.toHaveProperty('kind');
});
