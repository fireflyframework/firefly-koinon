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
  ['viewer', ['catalog:read', 'providers:write'], true],
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
    expect(
      [...root.querySelectorAll('button')].some(
        (button) => button.textContent?.trim() === 'Settings',
      ),
    ).toBe(expected);
  },
);

it('offers scoped people settings only inside the currently authorized workspace', async () => {
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
  expect(fixture.componentInstance.canConfigure()).toBe(true);
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
