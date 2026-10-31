// Copyright 2026 Firefly Software Foundation SPDX-License-Identifier: Apache-2.0
import { TestBed } from '@angular/core/testing';
import { KoinonFacade, provideKoinonClient } from '@fireflyframework/koinon-angular';
import {
  KoinonClient,
  type KoinonTransport,
  type HttpMethod,
  type OrganizationPerson,
  type RequestOptions,
} from '@fireflyframework/koinon-sdk';
import { KoinonSettingsPage } from './settings-page';
import { KoinonOrganizationPeople } from './organization-directory';
import { KoinonOrganizationUnitBrowser } from './organization-unit-browser';
function setup(people?: OrganizationPerson[]) {
  const calls: { path: string; options: RequestOptions | undefined }[] = [];
  const access = { denied: false };
  const transport: KoinonTransport = {
    request: async <T>(_method: HttpMethod, path: string, options?: RequestOptions) => {
      calls.push({ path, options });
      if (access.denied) throw Object.assign(new Error('Denied'), { status: 403 });
      return {
        items: people ?? [
          {
            id: 'unit1',
            tenant_id: 'north',
            name: 'Platform',
            kind: 'team',
            revision: 3,
            has_children: false,
          },
        ],
        total: 26,
        pages: 2,
        page: options?.query?.['page'] ?? 1,
        page_size: 25,
      } as T;
    },
    stream: () => {
      throw new Error('Unexpected stream');
    },
  };
  TestBed.configureTestingModule({
    providers: [KoinonFacade, ...provideKoinonClient(new KoinonClient({ transport }), transport)],
  });
  const f = TestBed.inject(KoinonFacade);
  f.tenantId.set('north');
  f.context.set({
    subject: 'alex',
    tenants: [{ id: 'north', name: 'North', roles: ['admin'], permissions: [] }],
    memberships: [],
    workspaces: [
      {
        id: 'workspace1',
        tenant_id: 'north',
        kind: 'workspace',
        name: 'Workspace',
        workspace_id: 'workspace1',
        project_id: null,
        parent_id: null,
        description: '',
        status: 'ready',
        metadata: {},
        created_at: '2026-10-30T00:00:00Z',
      },
    ],
    workspace_permissions: {},
  });
  return { f, calls, access };
}
describe('organization administration separation', () => {
  it('keeps workspace Access available without showing tenant directory or structure editing', () => {
    const { f } = setup();
    f.workspaceId.set('workspace1');
    f.context.update((value) => ({
      ...value!,
      workspace_permissions: { workspace1: ['members:write'] },
    }));
    const page = TestBed.createComponent(KoinonSettingsPage).componentInstance;
    expect(
      page.tabsFor({ sections: ['people', 'structure', 'access'] }).map((tab) => tab.id),
    ).toEqual(['access']);
  });
  it('opens an empty unit branch and requests only that server page', async () => {
    const { f, calls } = setup();
    f.context.update((value) => ({
      ...value!,
      tenants: [{ id: 'north', name: 'North', roles: ['admin'], permissions: ['members:write'] }],
    }));
    const fixture = TestBed.createComponent(KoinonOrganizationUnitBrowser);
    fixture.detectChanges();
    await fixture.whenStable();
    await fixture.componentInstance.enter({
      id: 'unit1',
      tenant_id: 'north',
      name: 'Platform',
      kind: 'team',
      revision: 3,
      has_children: false,
    });
    await fixture.componentInstance.load(2);
    expect(calls.at(-1)?.options?.query).toMatchObject({
      parent_id: 'unit1',
      page: 2,
      page_size: 25,
    });
    expect(fixture.componentInstance.path().map((unit) => unit.name)).toEqual(['Platform']);
    f.tenantId.set('south');
    fixture.detectChanges();
    await fixture.whenStable();
    expect(fixture.componentInstance.path()).toEqual([]);
  });
});

it('shows a human label and explains why an unprofiled member cannot receive a position yet', async () => {
  const { f } = setup([{ id: null, profile_id: null, display_name: '', revision: 0 }]);
  f.context.update((value) => ({
    ...value!,
    tenants: [{ id: 'north', name: 'North', roles: ['admin'], permissions: ['members:write'] }],
  }));
  const fixture = TestBed.createComponent(KoinonOrganizationPeople);
  fixture.detectChanges();
  await fixture.whenStable();
  fixture.detectChanges();
  expect(fixture.nativeElement.textContent).toContain('Name unavailable');
  const action = fixture.nativeElement.querySelector(
    'button[aria-label="Edit position"]',
  ) as HTMLButtonElement;
  expect(action).not.toBeNull();
  expect(action.disabled).toBe(true);
  const description = action.getAttribute('aria-describedby');
  expect(description).not.toBeNull();
  expect(fixture.nativeElement.querySelector('#' + description)?.textContent).toContain(
    'Ask this person to complete their profile.',
  );
});

it('removes local unit paths and forms after server denial without automatically retrying', async () => {
  const { f, calls, access } = setup();
  f.context.update((value) => ({
    ...value!,
    tenants: [{ id: 'north', name: 'North', roles: ['admin'], permissions: ['members:write'] }],
  }));
  const fixture = TestBed.createComponent(KoinonOrganizationUnitBrowser);
  fixture.detectChanges();
  await fixture.whenStable();
  const unit = {
    id: 'unit1',
    tenant_id: 'north',
    name: 'Platform',
    kind: 'team' as const,
    revision: 3,
  };
  await fixture.componentInstance.enter(unit);
  fixture.componentInstance.begin(unit);
  fixture.detectChanges();
  access.denied = true;
  await fixture.componentInstance.load();
  fixture.detectChanges();
  await fixture.whenStable();
  fixture.detectChanges();
  expect(fixture.componentInstance.path()).toEqual([]);
  expect(fixture.componentInstance.editing()).toBeUndefined();
  expect(fixture.nativeElement.textContent).not.toContain('Platform');
  expect(calls).toHaveLength(3);
});
it('keeps the title with the person and shows a department only once when it is also the assigned unit', async () => {
  const { f } = setup([
    {
      id: 'person1',
      profile_id: 'profile1',
      display_name: 'Alex Rivera',
      job_title: 'Knowledge Operations Lead',
      department: { id: 'unit1', name: 'Engineering', kind: 'department' },
      unit: { id: 'unit1', name: 'Engineering', kind: 'department' },
      revision: 1,
    },
  ]);
  f.context.update((value) => ({
    ...value!,
    tenants: [{ id: 'north', name: 'North', roles: ['admin'], permissions: ['members:write'] }],
  }));
  const fixture = TestBed.createComponent(KoinonOrganizationPeople);
  fixture.detectChanges();
  await fixture.whenStable();
  fixture.detectChanges();
  const row = fixture.nativeElement.querySelector('tbody tr') as HTMLElement;
  expect(row.querySelector('.person-cell')?.textContent).toContain('Knowledge Operations Lead');
  expect(row.textContent?.match(/Engineering/g)).toHaveLength(1);
  expect(row.querySelector('.organization-cell')?.textContent).toContain('Engineering');
  expect(row.textContent).not.toContain('Not provided');
  expect(row.querySelectorAll('td')).toHaveLength(4);
});
it('keeps filter disclosure and draft changes separate from explicit server filtering', async () => {
  const { f, calls } = setup([]);
  f.context.update((value) => ({
    ...value!,
    tenants: [{ id: 'north', name: 'North', roles: ['admin'], permissions: ['members:write'] }],
  }));
  const fixture = TestBed.createComponent(KoinonOrganizationPeople);
  fixture.detectChanges();
  await fixture.whenStable();
  fixture.detectChanges();
  const toggle = fixture.nativeElement.querySelector(
    '.people-filter-toggle button',
  ) as HTMLButtonElement;
  expect(toggle).not.toBeNull();
  expect(toggle.getAttribute('aria-expanded')).toBe('false');
  const form = fixture.nativeElement.querySelector(
    '#organization-people-filters',
  ) as HTMLFormElement;
  expect(toggle.getAttribute('aria-controls')).toBe(form.id);
  toggle.click();
  fixture.detectChanges();
  expect(toggle.getAttribute('aria-expanded')).toBe('true');
  const input = form.querySelector('input[name="person-search"]') as HTMLInputElement;
  input.value = 'Alex';
  input.dispatchEvent(new Event('input', { bubbles: true }));
  fixture.detectChanges();
  await fixture.whenStable();
  expect(calls).toHaveLength(1);
  form.dispatchEvent(new Event('submit', { bubbles: true, cancelable: true }));
  fixture.detectChanges();
  await vi.waitFor(() => expect(calls.at(-1)?.options?.query?.['q']).toBe('Alex'));
  fixture.detectChanges();
  expect(toggle.getAttribute('aria-expanded')).toBe('false');
  const description = toggle.getAttribute('aria-describedby');
  expect(description).not.toBeNull();
  expect(fixture.nativeElement.querySelector('#' + description)?.textContent).toContain(
    '1 filter applied',
  );
  toggle.click();
  fixture.detectChanges();
  input.value = 'Draft';
  input.dispatchEvent(new Event('input', { bubbles: true }));
  fixture.detectChanges();
  form.dispatchEvent(
    new KeyboardEvent('keydown', { key: 'Escape', bubbles: true, cancelable: true }),
  );
  fixture.detectChanges();
  expect(toggle.getAttribute('aria-expanded')).toBe('false');
  expect(calls).toHaveLength(2);
});
