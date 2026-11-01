// Copyright 2026 Firefly Software Foundation SPDX-License-Identifier: Apache-2.0
import { TestBed } from '@angular/core/testing';
import {
  KoinonClient,
  KoinonError,
  type HttpMethod,
  type KoinonTransport,
  type RequestOptions,
} from '@fireflyframework/koinon-sdk';
import { provideKoinonClient } from './client-provider';
import { KoinonWorkbench } from './koinon-angular';
const workspace = {
  id: 'workspace-one',
  tenant_id: 'tenant-one',
  kind: 'workspace',
  name: 'Risk evidence',
  description: 'Reviewed policy and operational data',
  status: 'ready',
  parent_id: null,
  workspace_id: 'workspace-one',
  project_id: null,
  metadata: {},
  created_at: '2026-10-26T00:00:00Z',
};
async function mount(
  handler: (method: HttpMethod, path: string, options?: RequestOptions) => Promise<unknown>,
) {
  const transport: KoinonTransport = {
    stream: () => {
      throw new Error('Unexpected streaming request in a catalog test');
    },
    request: <T>(method: HttpMethod, path: string, options?: RequestOptions) =>
      handler(method, path, options) as Promise<T>,
  };
  await TestBed.configureTestingModule({
    imports: [KoinonWorkbench],
    providers: provideKoinonClient(new KoinonClient({ transport }), transport),
  }).compileComponents();
  const fixture = TestBed.createComponent(KoinonWorkbench);
  await fixture.whenStable();
  return fixture;
}
describe('embedded knowledge workbench', () => {
  it('renders observed catalog resources and withholds editing from viewers', async () => {
    const fixture = await mount(async (_method, path) =>
      path === '/context'
        ? {
            subject: 'reader',
            tenants: [
              {
                id: 'tenant-one',
                name: 'Synthetic tenant',
                roles: ['viewer'],
                permissions: ['catalog:read'],
              },
            ],
            memberships: [],
            workspaces: [workspace],
          }
        : path === '/capabilities'
          ? { providers: [], features: [] }
          : { items: [workspace] },
    );
    const root = (fixture.nativeElement.shadowRoot ?? fixture.nativeElement) as HTMLElement;
    expect(root.textContent).toContain('Risk evidence');
    expect([...root.querySelectorAll('nav button')].map((x) => x.textContent?.trim())).toContain(
      'Library',
    );
    expect(root.querySelector('ffk-inspector')).toBe(null);
    expect(
      [...root.querySelectorAll('button')].some((x) => x.textContent?.trim() === 'Settings'),
    ).toBe(false);
    expect(
      [...root.querySelectorAll('button')].some((button) =>
        button.textContent?.includes('Add knowledge'),
      ),
    ).toBe(false);
  });
  it('shows authentication guidance without redirecting its host', async () => {
    const fixture = await mount(async () => {
      throw new KoinonError(401, 'UNAUTHENTICATED', 'Sign in is required');
    });
    const root = (fixture.nativeElement.shadowRoot ?? fixture.nativeElement) as HTMLElement;
    expect(root.textContent).toContain('Sign in');
    expect(root.querySelector('a[href^="/oauth2"]')).toBe(null);
  });
  it('preserves a service failure instead of displaying an invented empty catalog', async () => {
    const fixture = await mount(async () => {
      throw new KoinonError(503, 'UNAVAILABLE', 'Catalog database is unavailable');
    });
    expect(
      ((fixture.nativeElement.shadowRoot ?? fixture.nativeElement) as HTMLElement).textContent,
    ).toContain('Catalog database is unavailable');
  });
  it.each([
    ['OK', 'ready'],
    ['REFINED_OK', 'ready'],
    ['FAILED', 'attention'],
    ['REJECTED_BY_FIREWALL', 'attention'],
    [null, 'neutral'],
  ] as const)('shows the canonical query status %s with the correct tone', async (status, tone) => {
    const fixture = await mount(async (_method, path) =>
      path === '/context'
        ? {
            subject: 'reader',
            tenants: [
              {
                id: 'tenant-one',
                name: 'Synthetic tenant',
                roles: ['viewer'],
                permissions: ['catalog:read'],
              },
            ],
            memberships: [],
            workspaces: [workspace],
          }
        : path === '/capabilities'
          ? { providers: [], features: [] }
          : { items: [] },
    );
    fixture.componentInstance.f.queryResult.set({
      query_id: 'query-one',
      execution_status: status,
    });
    fixture.componentInstance.showDialog('query');
    fixture.detectChanges();
    await fixture.whenStable();
    const root = (fixture.nativeElement.shadowRoot ?? fixture.nativeElement) as HTMLElement;
    const badge = root.querySelector('.query-result ffk-badge span');
    expect(badge?.classList.contains(tone)).toBe(true);
    fixture.componentInstance.closeDialog();
  });
});

it.each([
  ['admin', ['catalog:read', 'chat:use'], false],
  ['viewer', ['catalog:read', 'providers:write'], false],
  ['admin', ['catalog:read', 'members:write'], true],
  ['operator', ['catalog:read', 'members:write'], false],
] as const)(
  'uses authoritative capabilities for the %s settings navigation',
  async (role, permissions, expected) => {
    const fixture = await mount(async (_method, path) =>
      path === '/context'
        ? {
            subject: 'reviewer',
            tenants: [{ id: 'tenant-one', name: 'Synthetic tenant', roles: [role], permissions }],
            memberships: [],
            workspaces: [workspace],
          }
        : path === '/capabilities'
          ? { providers: [], features: [] }
          : { items: [] },
    );
    expect(fixture.componentInstance.canConfigure()).toBe(expected);
    const root = (fixture.nativeElement.shadowRoot ?? fixture.nativeElement) as HTMLElement;
    root.querySelector<HTMLButtonElement>('.account-avatar')!.click();
    await vi.waitFor(() => { fixture.detectChanges(); expect(root.querySelector('[role=menu]')).not.toBeNull(); });
    expect(
      [...root.querySelectorAll('button')].some(
        (button) => button.textContent?.trim() === 'Settings',
      ),
    ).toBe(expected);
  },
);

it('keeps administrator pages unavailable to non-admin workspace operators', async () => {
  const fixture = await mount(async (_method, path) =>
    path === '/context'
      ? {
          subject: 'reviewer',
          tenants: [
            {
              id: 'tenant-one',
              name: 'Synthetic tenant',
              roles: ['viewer'],
              permissions: ['catalog:read'],
            },
          ],
          memberships: [],
          workspaces: [workspace],
          workspace_permissions: { 'workspace-one': ['catalog:read', 'members:write'] },
        }
      : path === '/capabilities'
        ? { providers: [], features: [] }
        : { items: [] },
  );
  expect(fixture.componentInstance.canConfigure()).toBe(false);
  await fixture.componentInstance.f.setWorkspace('workspace-one');
  fixture.detectChanges();
  expect(fixture.componentInstance.canConfigure()).toBe(false);
  await fixture.componentInstance.navigate('settings');
  expect(fixture.componentInstance.destination()).toBe('chat');
});

it('keeps a controlled account section until the host acknowledges navigation', async () => {
  const fixture = await mount(async (_method, path) =>
    path === '/context'
      ? {
          subject: 'reader',
          tenants: [
            {
              id: 'tenant-one',
              name: 'Synthetic tenant',
              roles: ['viewer'],
              permissions: ['catalog:read'],
            },
          ],
          memberships: [],
          workspaces: [workspace],
        }
      : path === '/profile'
        ? {
            subject: 'reader',
            display_name: 'Reader',
            locale: 'en-US',
            time_zone: 'UTC',
            response_language: 'en',
          }
        : { items: [] },
  );
  fixture.componentRef.setInput('accountSection', 'applications');
  await fixture.whenStable();
  const changed: (string | null)[] = [];
  fixture.componentInstance.accountSectionChange.subscribe((value) => changed.push(value));
  await fixture.componentInstance.navigate('library');
  expect(changed).toEqual([null]);
  expect(fixture.componentInstance.accountScreen()).toBe('applications');
  fixture.componentRef.setInput('accountSection', null);
  await fixture.whenStable();
  expect(fixture.componentInstance.accountScreen()).toBe(null);
});

it('requests Library and account dismissal when changing organizations from a personal screen', async () => {
  const fixture = await mount(async (_method, path) =>
    path === '/context'
      ? {
          subject: 'reader',
          tenants: [
            { id: 'tenant-one', name: 'First', roles: [], permissions: ['catalog:read'] },
            { id: 'tenant-two', name: 'Second', roles: [], permissions: ['catalog:read'] },
          ],
          memberships: [],
          workspaces: [],
        }
      : { items: [] },
  );
  fixture.componentRef.setInput('view', 'chat');
  fixture.componentRef.setInput('accountSection', 'profile');
  await fixture.whenStable();
  const views: string[] = [],
    sections: (string | null)[] = [];
  fixture.componentInstance.viewChange.subscribe((value) => views.push(value));
  fixture.componentInstance.accountSectionChange.subscribe((value) => sections.push(value));
  await fixture.componentInstance.changeTenant('tenant-two');
  expect(views).toEqual(['library']);
  expect(sections).toEqual([null]);
  expect(fixture.componentInstance.f.tenantId()).toBe('tenant-two');
});

it('keeps an organization load failure visible after navigating from Chat', async () => {
  const fixture = await mount(async (_method, path) => {
    if (path === '/context')
      return {
        subject: 'reader',
        tenants: [
          { id: 'tenant-one', name: 'First', roles: [], permissions: ['catalog:read'] },
          { id: 'tenant-two', name: 'Second', roles: [], permissions: ['catalog:read'] },
        ],
        memberships: [],
        workspaces: [],
      };
    if (path === '/tenants/tenant-two/catalog')
      throw new KoinonError(503, 'UNAVAILABLE', 'Organization temporarily unavailable');
    return { items: [] };
  });
  await fixture.componentInstance.navigate('chat');
  await fixture.componentInstance.changeTenant('tenant-two');
  expect(fixture.componentInstance.f.error()).toBe('Organization temporarily unavailable');
});

it('resets organization and navigation immediately without clobbering a later Chat request', async () => {
  let complete!: (value: unknown) => void;
  const fixture = await mount(async (_method, path) => {
    if (path === '/context')
      return {
        subject: 'reader',
        tenants: [
          { id: 'tenant-one', name: 'First', roles: [], permissions: ['catalog:read'] },
          { id: 'tenant-two', name: 'Second', roles: [], permissions: ['catalog:read'] },
        ],
        memberships: [],
        workspaces: [],
      };
    if (path === '/tenants/tenant-two/catalog')
      return new Promise((resolve) => {
        complete = resolve;
      });
    return { items: [] };
  });
  await fixture.componentInstance.navigate('chat');
  const views: string[] = [];
  fixture.componentInstance.viewChange.subscribe((value) => views.push(value));
  const scopes: string[] = [];
  fixture.componentInstance.contextChange.subscribe((scope) => scopes.push(scope.tenantId));
  const changing = fixture.componentInstance.changeTenant('tenant-two');
  expect(scopes).toEqual(['tenant-two']);
  expect(fixture.componentInstance.destination()).toBe('library');
  expect(fixture.componentInstance.f.tenantId()).toBe('tenant-two');
  await fixture.componentInstance.navigate('chat');
  complete({ items: [] });
  await changing;
  expect(fixture.componentInstance.destination()).toBe('chat');
  expect(views).toEqual(['library', 'chat']);
});

it('does not request initial host resources after all organization memberships are removed', async () => {
  const catalogs: string[] = [];
  const fixture = await mount(async (_method, path) => {
    if (path === '/context')
      return { subject: 'reader', tenants: [], memberships: [], workspaces: [] };
    if (path.includes('/catalog')) catalogs.push(path);
    return { items: [] };
  });
  fixture.componentRef.setInput('workspaceId', 'previous-workspace');
  fixture.componentRef.setInput('projectId', 'previous-project');
  fixture.componentRef.setInput('resourceId', 'previous-resource');
  await fixture.whenStable();
  expect(catalogs).toEqual([]);
  expect(fixture.componentInstance.f.workspaceId()).toBe('');
});

it('retries the chosen organization after the initial explicit entry scope has been replaced', async () => {
  const fixture = await mount(async (_method, path) =>
    path === '/context'
      ? {
          subject: 'reader',
          tenants: [
            { id: 'tenant-one', name: 'First', roles: [], permissions: ['catalog:read'] },
            { id: 'tenant-two', name: 'Second', roles: [], permissions: ['catalog:read'] },
          ],
          memberships: [],
          workspaces: [],
        }
      : { items: [] },
  );
  fixture.componentRef.setInput('tenantId', 'tenant-one');
  await fixture.whenStable();
  await fixture.componentInstance.changeTenant('tenant-two');
  fixture.componentInstance.retryConnection();
  await fixture.whenStable();
  expect(fixture.componentInstance.f.tenantId()).toBe('tenant-two');
});
it('does not reveal a personal name when corporate policy supplies an authoritative empty name', async () => {
  const fixture = await mount(async (_method, path) =>
    path === '/context'
      ? {
          subject: 'reader',
          tenants: [
            { id: 'tenant-one', name: 'North', roles: ['viewer'], permissions: ['catalog:read'] },
          ],
          memberships: [],
          workspaces: [workspace],
        }
      : path === '/profile'
        ? {
            subject: 'reader',
            display_name: 'Private personal name',
            locale: 'en-US',
            time_zone: 'UTC',
            response_language: 'en',
          }
        : path.endsWith('/presentation')
          ? {
              tenant_id: 'tenant-one',
              display_name: '',
              name_source: 'organization',
              avatar_source: 'organization',
              allow_personal_overrides: false,
              status: 'unavailable',
            }
          : { items: [] },
  );
  await vi.waitFor(() => expect(fixture.componentInstance.account.organizationName()).toBe(''));
  expect(fixture.componentInstance.displayName()).toBe('Name unavailable');
  expect(fixture.componentInstance.chatActions.displayName()).toBe('Name unavailable');
});

it('guards direct administrator page requests and leaves owner activity APIs untouched', async () => {
  const requests: string[] = [];
  const fixture = await mount(async (_method, path) => {
    requests.push(path);
    return path === '/context' ? {
      subject: 'reader', tenants: [{id:'tenant-one', name:'Read only', roles:['viewer'], permissions:['catalog:read']}],
      memberships:[], workspaces:[workspace],
    } : {items: []};
  });
  for (const view of ['activity', 'settings'] as const) {
    fixture.componentRef.setInput('view', view);
    await fixture.whenStable();
    expect(fixture.componentInstance.destination()).toBe('chat');
  }
  expect(fixture.componentInstance.activityComponent()).toBeNull();
  expect(fixture.componentInstance.settingsComponent()).toBeNull();
  expect(requests.some(path => /\/jobs|\/activity|\/providers/.test(path))).toBe(false);
});
it('dismisses administrator pages when current organization authority is revoked', async () => {
  const fixture = await mount(async (_method, path) => path === '/context' ? {
    subject:'admin',tenants:[{id:'tenant-one',name:'Organization',roles:['admin'],permissions:['catalog:read','members:write']}],
    memberships:[],workspaces:[workspace],
  } : {items:[]});
  await fixture.componentInstance.navigate('settings');
  expect(fixture.componentInstance.destination()).toBe('settings');
  fixture.componentInstance.f.context.update(context => context && ({...context,tenants:context.tenants.map(tenant => ({...tenant,roles:['viewer'],permissions:['catalog:read']}))}));
  await fixture.whenStable();
  expect(fixture.componentInstance.destination()).toBe('chat');
});

it('refuses to submit an archive from a stale dialog for a protected system root', async () => {
  const writes: string[] = [];
  const fixture = await mount(async (method, path) => {
    if (method !== 'GET') writes.push(path);
    return path === '/context' ? {subject:'admin',tenants:[{id:'tenant-one',name:'Team',roles:['admin'],permissions:['catalog:read','catalog:write','members:write']}],memberships:[],workspaces:[workspace]} : {items:[]};
  });
  fixture.componentInstance.f.selected.set({...workspace,kind:'workspace',system_managed:true} as typeof workspace & {kind:'workspace';system_managed:boolean});
  await fixture.componentInstance.archive();
  expect(writes).toEqual([]);
  expect(fixture.componentInstance.dialogError()).toBe('System spaces and folders cannot be archived.');
});

it('preserves an explicit shared receipt during host/default view initialization and dismisses only on user navigation', async () => {
  const fixture = await mount(async (_method,path) => path === '/context' ? {
    subject:'reader',tenants:[{id:'tenant-one',name:'Team',roles:['viewer'],permissions:['catalog:read']}],memberships:[],workspaces:[workspace],
  } : {items:[]});
  fixture.componentInstance.sharedConversationId = 'saved-receipt';
  const dismissed = vi.fn();
  fixture.componentInstance.sharedConversationDismissed.subscribe(dismissed);
  await fixture.componentInstance.navigate('chat', true);
  expect(dismissed).not.toHaveBeenCalled();
  await fixture.componentInstance.navigate('library');
  expect(dismissed).toHaveBeenCalledOnce();
});
