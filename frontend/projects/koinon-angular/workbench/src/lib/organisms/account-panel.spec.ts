// Copyright 2026 Firefly Software Foundation
// SPDX-License-Identifier: Apache-2.0
import { TestBed } from '@angular/core/testing';
import { signal } from '@angular/core';
import { KoinonAccountPanel } from './account-panel';
import { KoinonAccount } from '../services/account';
import { KoinonFacade } from '../koinon-facade';

describe('token issuance context', () => {
  function setup() {
    const workspace = signal('workspace-a');
    const selected = signal<{ id: string; kind: string; name: string } | null>({
      id: 'asset-a',
      kind: 'document',
      name: 'Policy',
    });
    const tenant = signal('north');
    const organizationPermissions = signal(new Set(['catalog:read', 'members:write']));
    const createToken = vi.fn(async () => null);
    const items = [
      { id: 'catalog:read', name: 'Browse', dependencies: [] },
      { id: 'members:write', name: 'People', dependencies: [] },
    ];
    TestBed.configureTestingModule({
      providers: [
        {
          provide: KoinonAccount,
          useValue: { tokenScopes: signal({ items, max_lifetime_days: 90 }), createToken },
        },
        {
          provide: KoinonFacade,
          useValue: {
            workspaceId: workspace,
            selected,
            tenantId: tenant,
            tenantPermissions: organizationPermissions,
            permissions: organizationPermissions,
            context: signal({ subject: 'person-a' }),
          },
        },
      ],
    });
    const panel = TestBed.runInInjectionContext(() => new KoinonAccountPanel());
    panel.beginToken();
    panel.tokenName = 'Integration';
    panel.scopeIds = ['catalog:read'];
    return { panel, workspace, selected, tenant, organizationPermissions, createToken };
  }
  it('never removes a checked workspace bound when the target disappears', async () => {
    const { panel, workspace, createToken } = setup();
    workspace.set('');
    await panel.createToken();
    expect(createToken).not.toHaveBeenCalled();
    expect(panel.formError()).toContain('workspace');
  });
  it('never removes a checked asset bound when the target disappears', async () => {
    const { panel, selected, createToken } = setup();
    panel.assetBound = true;
    selected.set(null);
    await panel.createToken();
    expect(createToken).not.toHaveBeenCalled();
    expect(panel.formError()).toContain('file');
  });
  it('does not silently switch a checked destination to another workspace', async () => {
    const { panel, workspace, createToken } = setup();
    workspace.set('workspace-b');
    await panel.createToken();
    expect(createToken).not.toHaveBeenCalled();
    expect(panel.formError()).toContain('workspace');
  });
  it('requires a new review after the organization changes', async () => {
    const { panel, tenant, createToken } = setup();
    tenant.set('south');
    await panel.createToken();
    expect(createToken).not.toHaveBeenCalled();
    expect(panel.formError()).toContain('access context');
  });
  it('does not submit an invisible management permission after role loss', async () => {
    const { panel, organizationPermissions, createToken } = setup();
    panel.preset('organization');
    organizationPermissions.set(new Set(['catalog:read']));
    await panel.createToken();
    expect(createToken).not.toHaveBeenCalled();
    expect(panel.scopeIds).toEqual(['catalog:read']);
    expect(panel.formError()).toContain('permissions changed');
  });
  it('preserves explicitly reviewed workspace and asset limits on a valid request', async () => {
    const { panel, createToken } = setup();
    panel.assetBound = true;
    await panel.createToken();
    expect(createToken).toHaveBeenCalledWith(
      expect.objectContaining({
        tenant_id: 'north',
        workspace_ids: ['workspace-a'],
        asset_ids: ['asset-a'],
      }),
    );
  });
});
