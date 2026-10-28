// Copyright 2026 Firefly Software Foundation SPDX-License-Identifier: Apache-2.0
import { TestBed } from '@angular/core/testing';
import { KoinonClient, type KoinonTransport } from '@fireflyframework/koinon-sdk';
import { KoinonFacade, provideKoinonClient } from '@fireflyframework/koinon-angular';
import { KoinonSettingsPage } from '../../../../settings/src/settings-page';

it('offers scoped people administration while keeping organization configuration denied', () => {
  const transport: KoinonTransport = {
    request: async <T>() => ({ items: [] }) as T,
    stream: () => {
      throw new Error('Unexpected stream');
    },
  };
  TestBed.configureTestingModule({
    imports: [KoinonSettingsPage],
    providers: [KoinonFacade, ...provideKoinonClient(new KoinonClient({ transport }), transport)],
  });
  const facade = TestBed.inject(KoinonFacade);
  const context = {
    subject: 'issuer|scoped',
    tenants: [{ id: 'north', name: 'North', roles: ['admin'], permissions: [] }],
    memberships: [],
    workspaces: [
      {
        id: 'space',
        tenant_id: 'north',
        kind: 'workspace' as const,
        name: 'Scoped workspace',
        workspace_id: 'space',
        project_id: null,
        parent_id: null,
        description: '',
        status: 'ready',
        metadata: {},
        created_at: '2026-10-27T00:00:00Z',
      },
    ],
    workspace_permissions: {
      space: ['catalog:read', 'members:write', 'providers:write', 'identity:manage'],
    },
  };
  facade.context.set(context);
  facade.tenantId.set('north');
  facade.workspaceId.set('space');
  const component = TestBed.createComponent(KoinonSettingsPage).componentInstance;
  expect(component.allowed('members:write')).toBe(true);
  expect(component.allowed('providers:write')).toBe(false);
  expect(component.allowed('identity:manage')).toBe(false);
  expect(
    component.tabsFor({ sections: ['providers', 'models', 'agents', 'storage', 'sources'] }),
  ).toEqual([]);
});
