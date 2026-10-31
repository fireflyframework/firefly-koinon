// Copyright 2026 Firefly Software Foundation SPDX-License-Identifier: Apache-2.0
import { TestBed } from '@angular/core/testing';
import { signal } from '@angular/core';
import {
  KoinonClient,
  type HttpMethod,
  type KoinonTransport,
  type OrganizationPresentation,
  type RequestOptions,
} from '@fireflyframework/koinon-sdk';
import { KoinonClientContext } from './client-context';
import { KoinonFacade } from '../koinon-facade';
import { KoinonOrganizationDirectory } from './organization-directory';
import { KoinonCorporatePresentation } from './corporate-presentation';
const presentation: OrganizationPresentation = {
  tenant_id: 'north',
  profile_id: 'profile1',
  revision: 3,
  name_mode: 'organization',
  avatar_mode: 'organization',
  name_source: 'organization',
  avatar_source: 'organization',
  allow_personal_overrides: true,
  display_name: 'Alex North',
  provider_name: 'North identity',
  status: 'current',
};
function setup(request: KoinonTransport['request']) {
  const tenant = signal('north'),
    subject = signal({ subject: 'alex' }),
    revision = signal(0);
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
      KoinonCorporatePresentation,
      { provide: KoinonClientContext, useValue: { get: () => client, revision } },
      {
        provide: KoinonFacade,
        useValue: {
          tenantId: tenant,
          workspaceId: signal('workspace1'),
          tenantPermissions: signal(new Set<string>()),
          permissions: signal(new Set(['catalog:read', 'profile:write'])),
          context: subject,
          authRequired: signal(false),
        },
      },
    ],
  });
  return {
    s: TestBed.inject(KoinonCorporatePresentation),
    directory: TestBed.inject(KoinonOrganizationDirectory),
    tenant,
    subject,
    revision,
  };
}
it('keeps personal preference writes tenant-scoped and revisioned', async () => {
  let sent: RequestOptions | undefined;
  const { s } = setup(async <T>(method: HttpMethod, _path: string, options?: RequestOptions) => {
    if (method === 'PATCH') sent = options;
    return presentation as T;
  });
  await s.load();
  expect(await s.save('personal', 'organization')).toBe(true);
  expect(sent?.body).toEqual({
    expected_revision: 3,
    name_mode: 'personal',
    avatar_mode: 'organization',
  });
  expect(sent?.query).toEqual({ workspace_id: 'workspace1' });
  expect(sent?.signal).toBeInstanceOf(AbortSignal);
});
it('does not submit personal overrides disabled by organization policy', async () => {
  let writes = 0;
  const { s } = setup(async <T>(method: HttpMethod) => {
    if (method === 'PATCH') writes++;
    return { ...presentation, allow_personal_overrides: false } as T;
  });
  await s.load();
  expect(await s.save('personal', 'personal')).toBe(false);
  expect(writes).toBe(0);
});
it.each([401, 403])(
  'clears effective presentation after server denial %i and ignores concurrent old reads',
  async (status) => {
    let fail = false;
    let finish: ((value: unknown) => void) | undefined;
    const { s, directory } = setup(<T>(_method: HttpMethod, path: string) => {
      if (path.endsWith('profile-refresh'))
        return Promise.reject(Object.assign(new Error('denied'), { status }));
      if (fail)
        return new Promise<T>((resolve) => {
          finish = resolve as (value: unknown) => void;
        });
      return Promise.resolve(presentation as T);
    });
    await s.load();
    expect(s.presentation()?.display_name).toBe('Alex North');
    fail = true;
    const old = s.load();
    await vi.waitFor(() => expect(finish).toBeDefined());
    await s.refresh();
    expect(directory.denied()).toBe(true);
    expect(s.presentation()).toBeNull();
    finish!(presentation);
    await old;
    expect(s.presentation()).toBeNull();
  },
);
it('blocks same-stack tenant and client changes before preference writes', async () => {
  let writes = 0;
  const { s, tenant, revision } = setup(async <T>(method: HttpMethod) => {
    if (method === 'PATCH') writes++;
    return presentation as T;
  });
  await s.load();
  tenant.set('south');
  revision.set(1);
  expect(await s.save('personal', 'personal')).toBe(false);
  expect(writes).toBe(0);
  expect(s.presentation()).toBeNull();
});
it('retains last effective values on revision conflict without claiming a save', async () => {
  const { s, directory } = setup(async <T>(method: HttpMethod) => {
    if (method === 'PATCH') throw Object.assign(new Error('conflict'), { status: 409 });
    return presentation as T;
  });
  await s.load();
  expect(await s.save('personal', 'personal')).toBe(false);
  expect(s.presentation()?.display_name).toBe('Alex North');
  expect(directory.error()).toContain('changed');
});
it('reports an accepted refresh as queued and never as a completed sync', async () => {
  const { s } = setup(
    async <T>(_method: HttpMethod, path: string) =>
      (path.endsWith('profile-refresh')
        ? { tenant_id: 'north', profile_id: 'profile1', status: 'queued' }
        : presentation) as T,
  );
  await s.load();
  expect(await s.refresh()).toBe(true);
  expect(s.presentation()?.status).toBe('queued');
  expect(s.notice()).toBe('Profile refresh queued. Check the status shortly.');
});
it('rejects a presentation response for a different tenant', async () => {
  const { s } = setup(async <T>() => ({ ...presentation, tenant_id: 'south' }) as T);
  await s.load();
  expect(s.presentation()).toBeNull();
});
it('does not retain presentation when its panel is destroyed during a read', async () => {
  let finish: ((value: unknown) => void) | undefined;
  const { s } = setup(
    <T>() =>
      new Promise<T>((resolve) => {
        finish = resolve as (value: unknown) => void;
      }),
  );
  const pending = s.load();
  await vi.waitFor(() => expect(finish).toBeDefined());
  s.ngOnDestroy();
  finish!(presentation);
  await pending;
  expect(s.presentation()).toBeNull();
});
it('revokes the scoped private photo on tenant change and never uses an upstream URL', async () => {
  const revoked: string[] = [];
  const NativeURL = URL;
  vi.stubGlobal(
    'URL',
    class extends NativeURL {
      static override createObjectURL() {
        return 'blob:private-corporate';
      }
      static override revokeObjectURL(value: string) {
        revoked.push(value);
      }
    },
  );
  try {
    const paths: string[] = [];
    const { s, tenant } = setup(async <T>(_method: HttpMethod, path: string) => {
      paths.push(path);
      return (
        path.endsWith('/avatar')
          ? { blob: new Blob(['photo']), not_modified: false }
          : {
              ...presentation,
              avatar_version: 'v1',
              avatar_url: 'https://untrusted.example/private',
            }
      ) as T;
    });
    await s.load();
    expect(s.avatar()).toBe('blob:private-corporate');
    expect(paths.every((path) => path.startsWith('/tenants/north/'))).toBe(true);
    tenant.set('south');
    expect(s.avatar()).toBe('');
    TestBed.tick();
    expect(revoked).toContain('blob:private-corporate');
  } finally {
    vi.unstubAllGlobals();
  }
});
it('clears presentation after a quiet private-photo denial', async () => {
  const { s, directory } = setup(async <T>(_method: HttpMethod, path: string) => {
    if (path.endsWith('/avatar')) throw Object.assign(new Error('denied'), { status: 403 });
    return { ...presentation, avatar_version: 'v1' } as T;
  });
  await s.load();
  expect(directory.denied()).toBe(true);
  expect(s.presentation()).toBeNull();
  expect(s.avatar()).toBe('');
});
it('does not let an older presentation read overwrite a newer saved preference', async () => {
  let defer = false;
  let finish: ((value: unknown) => void) | undefined;
  const { s } = setup(<T>(method: HttpMethod) =>
    method === 'PATCH'
      ? Promise.resolve({ ...presentation, revision: 4, name_mode: 'personal' } as T)
      : defer
        ? new Promise<T>((resolve) => {
            finish = resolve as (value: unknown) => void;
          })
        : Promise.resolve(presentation as T),
  );
  await s.load();
  defer = true;
  const old = s.load();
  await vi.waitFor(() => expect(finish).toBeDefined());
  await s.save('personal', 'organization');
  expect(s.presentation()?.revision).toBe(4);
  finish!(presentation);
  await old;
  expect(s.presentation()?.revision).toBe(4);
  expect(s.presentation()?.name_mode).toBe('personal');
});
it('does not retry a source binding conflict through profile refresh', async () => {
  let writes = 0;
  const { s } = setup(async <T>(method: HttpMethod) => {
    if (method === 'POST') writes++;
    return { ...presentation, status: 'conflict' } as T;
  });
  await s.load();
  expect(await s.refresh()).toBe(false);
  expect(writes).toBe(0);
});
