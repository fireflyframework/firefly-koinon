// Copyright 2026 Firefly Software Foundation SPDX-License-Identifier: Apache-2.0
import { TestBed } from '@angular/core/testing';
import { signal } from '@angular/core';
import {
  KoinonClient,
  type HttpMethod,
  type RequestOptions,
  type OrganizationPerson,
  type KoinonTransport,
} from '@fireflyframework/koinon-sdk';
import { KoinonClientContext } from './client-context';
import { KoinonFacade } from '../koinon-facade';
import { KoinonOrganizationDirectory } from './organization-directory';
const person: OrganizationPerson = {
  id: 'p1',
  profile_id: 'profile1',
  display_name: 'Alex',
  revision: 2,
  source: 'manual',
  managed_fields: [],
  observation_status: 'not_observed',
};
function setup(request: KoinonTransport['request']) {
  const tenant = signal('north');
  const permissions = signal(new Set(['members:write']));
  const client = new KoinonClient({
    transport: {
      request,
      stream: () => {
        throw new Error('Unexpected stream');
      },
    },
  });
  TestBed.configureTestingModule({
    providers: [
      KoinonOrganizationDirectory,
      { provide: KoinonClientContext, useValue: { get: () => client, revision: signal(0) } },
      {
        provide: KoinonFacade,
        useValue: {
          tenantId: tenant,
          workspaceId: signal('workspace1'),
          tenantPermissions: permissions,
          permissions,
          context: signal({ subject: 'alex' }),
          authRequired: signal(false),
        },
      },
    ],
  });
  return { service: TestBed.inject(KoinonOrganizationDirectory), tenant, permissions };
}
describe('tenant organization directory', () => {
  it('clears and aborts organization reads immediately after tenant changes', async () => {
    let finish!: (value: unknown) => void;
    let signal: AbortSignal | undefined;
    const { service, tenant } = setup(
      <T>(_method: HttpMethod, _path: string, options?: RequestOptions) => {
        signal = options?.signal;
        return new Promise<T>((resolve) => (finish = resolve as (value: unknown) => void));
      },
    );
    const pending = service.loadSelf();
    await vi.waitFor(() => expect(signal).toBeDefined());
    tenant.set('south');
    TestBed.tick();
    expect(signal?.aborted).toBe(true);
    expect(service.self()).toBeNull();
    finish(person);
    await pending;
    expect(service.self()).toBeNull();
  });
  it('retains only the newest applied search and sends bounded server pagination', async () => {
    const pending: ((value: unknown) => void)[] = [];
    const queries: unknown[] = [];
    const { service } = setup(<T>(_method: HttpMethod, _path: string, options?: RequestOptions) => {
      queries.push(options?.query);
      return new Promise<T>((resolve) => pending.push(resolve as (value: unknown) => void));
    });
    const first = service.loadPeople({ q: 'old', page: 1, page_size: 25 });
    const second = service.loadPeople({ q: 'Alex', page: 2, page_size: 25 });
    await vi.waitFor(() => expect(pending).toHaveLength(2));
    pending[1]!({ items: [person], page: 2, page_size: 25, total: 26, pages: 2 });
    await second;
    pending[0]!({ items: [], page: 1, page_size: 25, total: 0, pages: 0 });
    await first;
    expect(service.people()?.items[0]?.display_name).toBe('Alex');
    expect(queries[1]).toMatchObject({ q: 'Alex', page: 2, page_size: 25 });
  });
  it('preserves position data and exposes a recoverable revision conflict', async () => {
    const { service } = setup(async <T>(method: HttpMethod) => {
      if (method === 'PATCH') throw Object.assign(new Error('Conflict'), { status: 409 });
      return person as T;
    });
    await service.selectPerson(person);
    expect(
      await service.savePerson(person, { job_title: 'Engineer', unit_id: null, manager_id: null }),
    ).toBe(false);
    expect(service.selected()).toEqual(person);
    expect(service.error()).toContain('changed');
  });
});
it('reattaches only an explicitly selected source without overwriting organization values', async () => {
  let body: unknown;
  const { service, permissions } = setup(
    async <T>(method: HttpMethod, _path: string, options?: RequestOptions) => {
      if (method === 'PATCH') body = options?.body;
      return (
        method === 'GET' ? { items: [], page: 1, page_size: 25, total: 0, pages: 0 } : person
      ) as T;
    },
  );
  permissions.set(new Set(['members:write', 'identity:manage']));
  await service.savePerson(person, {}, false, 'provider1');
  expect(body).toEqual({ expected_revision: 2, managed_provider_id: 'provider1' });
});
it('clears directory rows and selected organization data when effective access is revoked', async () => {
  const { service, permissions } = setup(
    async <T>() => ({ items: [person], page: 1, page_size: 25, total: 1, pages: 1 }) as T,
  );
  await service.loadPeople();
  await service.selectPerson(person);
  expect(service.people()?.items).toHaveLength(1);
  permissions.set(new Set());
  TestBed.tick();
  expect(service.people()).toBeNull();
  expect(service.selected()).toBeNull();
});
it('does not submit an organization assignment for a member who has no profile', async () => {
  let requests = 0;
  const { service } = setup(async <T>() => {
    requests++;
    return { items: [], page: 1, page_size: 25, total: 0, pages: 0 } as T;
  });
  expect(
    await service.savePerson(
      { display_name: '', id: null, profile_id: null, revision: 0 },
      { job_title: 'Engineer' },
    ),
  ).toBe(false);
  expect(requests).toBe(0);
  expect(service.error()).toContain('profile');
});
it.each([401, 403])(
  'clears private organization caches and photo URLs after server denial %i even when context is unchanged',
  async (status) => {
    const revoked: string[] = [];
    const NativeURL = URL;
    let denied = false;
    vi.stubGlobal(
      'URL',
      class extends NativeURL {
        static override createObjectURL() {
          return 'blob:private-directory';
        }
        static override revokeObjectURL(url: string) {
          revoked.push(url);
        }
      },
    );
    try {
      const row = { ...person, avatar_version: 'v1' };
      const { service } = setup(async <T>(_method: HttpMethod, path: string) => {
        if (denied) throw Object.assign(new Error('Denied'), { status });
        return (
          path.endsWith('/avatar')
            ? { blob: new Blob(['private']), not_modified: false }
            : path.endsWith('/me')
              ? row
              : { items: [row], page: 1, page_size: 25, total: 1, pages: 1 }
        ) as T;
      });
      await service.loadSelf();
      await service.loadPeople();
      await service.selectPerson(row);
      await vi.waitFor(() => expect(service.avatars()['p1']).toBe('blob:private-directory'));
      denied = true;
      await service.loadUnits();
      expect(service.people()).toBeNull();
      expect(service.selected()).toBeNull();
      expect(service.self()).toBeNull();
      expect(service.avatars()).toEqual({});
      expect(revoked).toContain('blob:private-directory');
    } finally {
      vi.unstubAllGlobals();
    }
  },
);
it('does not apply a completed mapping write to a different provider selected while it was pending', async () => {
  let finish!: (value: unknown) => void;
  const { service, permissions } = setup(<T>(method: HttpMethod, path: string) => {
    if (method === 'PUT')
      return new Promise<T>((resolve) => (finish = resolve as (value: unknown) => void));
    const id = path.split('/').at(-1);
    return Promise.resolve({
      tenant_id: 'north',
      provider_id: id,
      revision: id === 'providerB' ? 7 : 1,
      enabled: false,
      fields: {},
    } as T);
  });
  permissions.set(new Set(['members:write', 'identity:manage']));
  await service.loadMapping('providerA');
  const saving = service.saveMapping('providerA', {
    expected_revision: 1,
    enabled: true,
    fields: { job_title: 'title' },
  });
  await vi.waitFor(() => expect(finish).toBeDefined());
  await service.loadMapping('providerB');
  finish({
    tenant_id: 'north',
    provider_id: 'providerA',
    revision: 2,
    enabled: true,
    fields: { job_title: 'title' },
  });
  await saving;
  expect(service.mapping()?.provider_id).toBe('providerB');
  expect(service.mapping()?.revision).toBe(7);
});
it('prevents a late read from restoring organization data after a different request is denied', async () => {
  let finish!: (value: unknown) => void;
  const { service } = setup(<T>(_method: HttpMethod, path: string) =>
    path.endsWith('/people')
      ? new Promise<T>((resolve) => (finish = resolve as (value: unknown) => void))
      : Promise.reject(Object.assign(new Error('Denied'), { status: 403 })),
  );
  const reading = service.loadPeople();
  await vi.waitFor(() => expect(finish).toBeDefined());
  await service.loadUnits();
  finish({ items: [person], page: 1, page_size: 25, total: 1, pages: 1 });
  await reading;
  expect(service.people()).toBeNull();
});
it('treats a background avatar403 as access revocation rather than a quiet image error', async () => {
  let rejectAvatar!: (reason: unknown) => void;
  const { service } = setup(<T>(_method: HttpMethod, path: string) =>
    path.endsWith('/avatar')
      ? new Promise<T>((_resolve, reject) => (rejectAvatar = reject))
      : Promise.resolve({
          items: [{ ...person, avatar_version: 'v1' }],
          page: 1,
          page_size: 25,
          total: 1,
          pages: 1,
        } as T),
  );
  await service.loadPeople();
  await vi.waitFor(() => expect(rejectAvatar).toBeDefined());
  rejectAvatar(Object.assign(new Error('Denied'), { status: 403 }));
  await vi.waitFor(() => expect(service.people()).toBeNull());
});
it('requires both tenant administration permissions before refreshing another person', async () => {
  let writes = 0;
  const { service } = setup(async <T>() => {
    writes++;
    return { tenant_id: 'north', status: 'queued' } as T;
  });
  await service.selectPerson(person);
  expect(await service.refreshPerson(person)).toBe(false);
  expect(writes).toBe(0);
});
it('queues a scoped person refresh without reporting completion or changing access', async () => {
  let path = '';
  let body: unknown;
  const { service, permissions } = setup(
    async <T>(_method: HttpMethod, p: string, options?: RequestOptions) => {
      path = p;
      body = options?.body;
      return { tenant_id: 'north', status: 'queued' } as T;
    },
  );
  permissions.set(new Set(['members:write', 'identity:manage']));
  TestBed.tick();
  await service.selectPerson(person);
  await service.refreshPerson(person);
  expect(path).toBe('/tenants/north/organization/people/p1/profile-refresh');
  expect(body).toEqual({});
  expect(service.notice()).toBe('Profile refresh queued. Check the status shortly.');
});
it('retains the last successful sync timestamp while a refresh is only queued', async () => {
  const { service, permissions } = setup(
    async <T>() => ({ tenant_id: 'north', status: 'queued' }) as T,
  );
  permissions.set(new Set(['members:write', 'identity:manage']));
  TestBed.tick();
  await service.selectPerson({
    ...person,
    presentation: { status: 'current', last_synced_at: '2026-10-30T09:00:00Z' },
  });
  await service.refreshPerson(person);
  expect(service.selected()?.presentation?.last_synced_at).toBe('2026-10-30T09:00:00Z');
  expect(service.selected()?.presentation?.status).toBe('queued');
});
it('does not refresh another person whose corporate source has a conflict', async () => {
  let calls = 0;
  const { service, permissions } = setup(async <T>() => {
    calls++;
    return { tenant_id: 'north', status: 'queued' } as T;
  });
  permissions.set(new Set(['members:write', 'identity:manage']));
  TestBed.tick();
  const conflict = { ...person, presentation: { status: 'conflict' as const } };
  await service.selectPerson(conflict);
  expect(await service.refreshPerson(conflict)).toBe(false);
  expect(calls).toBe(0);
});
