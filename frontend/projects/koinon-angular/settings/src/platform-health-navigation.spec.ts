// Copyright 2026 Firefly Software Foundation
// SPDX-License-Identifier: Apache-2.0
import { TestBed } from '@angular/core/testing';
import { KoinonFacade, provideKoinonClient } from '@fireflyframework/koinon-angular';
import { KoinonClient, type KoinonTransport, type Membership } from '@fireflyframework/koinon-sdk';
import { KoinonSettingsPage } from './settings-page';

function setup(permissions = ['catalog:read', 'audit:read'], changes: Partial<Membership> = {}) {
  const requests: string[] = [];
  const transport: KoinonTransport = {
    request: async <T>(_method: unknown, path: string) => {
      requests.push(path);
      return {} as T;
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
    tenants: [{ id: 'north', name: 'North', roles: ['admin'], permissions }],
    workspaces: [],
    memberships: [
      {
        id: 'grant',
        subject: 'alex',
        tenant_id: 'north',
        workspace_id: null,
        role: 'admin',
        active: true,
        ...changes,
      },
    ],
  });
  return { f, requests, page: TestBed.createComponent(KoinonSettingsPage).componentInstance };
}

it('places Platform health in Operations for a current organization administrator', () => {
  const { page } = setup();
  expect(
    page.tabsFor(page.groups.find((item) => item.id === 'operations')!).map((item) => item.id),
  ).toContain('health');
});
for (const [name, permissions, changes] of [
  ['workspace administrator', ['catalog:read', 'audit:read'], { workspace_id: 'workspace' }],
  ['an empty workspace scope', ['catalog:read', 'audit:read'], { workspace_id: '' }],
  ['a malformed expiry', ['catalog:read', 'audit:read'], { expires_at: '' }],
  ['inactive administrator', ['catalog:read', 'audit:read'], { active: false }],
  ['expired administrator', ['catalog:read', 'audit:read'], { expires_at: '2020-01-01T00:00:00Z' }],
  ['different subject', ['catalog:read', 'audit:read'], { subject: 'another-person' }],
  ['different organization', ['catalog:read', 'audit:read'], { tenant_id: 'south' }],
  ['viewer', ['catalog:read', 'audit:read'], { role: 'viewer' }],
  ['missing audit permission', ['catalog:read'], {}],
  ['missing catalog permission', ['audit:read'], {}],
] as [string, string[], Partial<Membership>][]) {
  it(`does not expose Platform health to ${name}`, () => {
    const { page } = setup(permissions, changes);
    expect(
      page.tabsFor(page.groups.find((item) => item.id === 'operations')!).map((item) => item.id),
    ).not.toContain('health');
  });
}
it('removes Platform health immediately when the current administrator grant is revoked', () => {
  const { f, page } = setup();
  const group = page.groups.find((item) => item.id === 'operations')!;
  expect(page.tabsFor(group).some((item) => item.id === 'health')).toBe(true);
  f.context.update((value) => ({ ...value!, memberships: [] }));
  expect(page.tabsFor(group).some((item) => item.id === 'health')).toBe(false);
});
it('opens a requested health section without loading legacy provider observations', async () => {
  const { page, requests } = setup(['catalog:read', 'audit:read', 'providers:write']);
  page.actions = { section: () => 'health', chat: () => undefined };
  page.ngOnInit();
  await Promise.resolve();
  expect(page.section()).toBe('health');
  expect(requests.some((path) => path.endsWith('/configuration'))).toBe(false);
});
it('loads provider configuration when leaving an initially passive health section', async () => {
  const { page, requests } = setup(['catalog:read', 'audit:read', 'providers:write']);
  page.actions = { section: () => 'health', chat: () => undefined };
  page.ngOnInit();
  await Promise.resolve();
  await page.openSection('providers');
  expect(requests.filter((path) => path.endsWith('/configuration'))).toHaveLength(1);
});
