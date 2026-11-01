// Copyright 2026 Firefly Software Foundation SPDX-License-Identifier: Apache-2.0
import { TestBed } from '@angular/core/testing';
import {
  KoinonClient,
  KoinonError,
  type CatalogEntry,
  type KoinonTransport,
} from '@fireflyframework/koinon-sdk';
import { provideKoinonClient } from '../client-provider';
import { KoinonFacade } from '../koinon-facade';
import { KoinonClientContext } from '../services/client-context';
import { KoinonMoveFolder, canMoveFolderTo } from './move-folder';
const folder: CatalogEntry = {
  id: 'folder',
  tenant_id: 'tenant',
  kind: 'collection',
  name: 'Evidence',
  description: '',
  status: 'ready',
  workspace_id: 'workspace',
  project_id: 'project',
  parent_id: 'project',
  created_at: '2026-11-01T00:00:00Z',
  updated_at: '2026-11-01T01:00:00Z',
  metadata: {},
};
const destination: CatalogEntry = {
  ...folder,
  id: 'destination',
  name: 'Reviewed',
  parent_id: 'project',
};
it('restricts moves to fresh same-project folders and excludes descendants and protected roots', () => {
  const child = { ...folder, id: 'child', parent_id: 'folder' };
  expect(canMoveFolderTo(folder, destination, [folder, destination])).toBe(true);
  expect(canMoveFolderTo(folder, child, [folder, child])).toBe(false);
  expect(canMoveFolderTo(folder, folder, [folder])).toBe(false);
  expect(canMoveFolderTo(folder, { ...destination, workspace_id: 'other' }, [])).toBe(false);
  expect(canMoveFolderTo(folder, { ...destination, project_id: 'other' }, [])).toBe(false);
  expect(canMoveFolderTo(folder, { ...destination, status: 'archived' }, [])).toBe(false);
  expect(canMoveFolderTo({ ...folder, system_managed: true }, destination, [])).toBe(false);
});
async function setup(handler: KoinonTransport['request']) {
  const transport: KoinonTransport = {
    request: handler,
    stream: () => {
      throw new Error('No streaming in a move');
    },
  };
  TestBed.configureTestingModule({
    imports: [KoinonMoveFolder],
    providers: [
      KoinonFacade,
      KoinonClientContext,
      provideKoinonClient(new KoinonClient({ transport }), transport),
    ],
  });
  const facade = TestBed.inject(KoinonFacade);
  facade.context.set({
    subject: 'owner',
    tenants: [
      {
        id: 'tenant',
        name: 'Team',
        roles: ['admin'],
        permissions: ['catalog:read', 'catalog:write'],
      },
    ],
    memberships: [],
    workspaces: [],
  });
  facade.tenantId.set('tenant');
  facade.entries.set([folder, destination]);
  const fixture = TestBed.createComponent(KoinonMoveFolder);
  fixture.componentRef.setInput('source', folder);
  fixture.detectChanges();
  await fixture.whenStable();
  return { fixture, facade };
}
it('uses the observed server parent and timestamp, preserves stale-conflict feedback and never retries', async () => {
  const writes: unknown[] = [];
  const fresh = { ...folder, updated_at: '2026-11-01T02:00:00Z' };
  const { fixture } = await setup(
    async <T>(method: string, path: string, options?: { body?: unknown }) => {
      if (method === 'POST') {
        writes.push(options?.body);
        throw new KoinonError(409, 'CONFLICT', 'Folder changed. Refresh before moving.');
      }
      return (path.endsWith('/folder') ? fresh : { items: [] }) as T;
    },
  );
  fixture.componentInstance.choose('destination');
  await fixture.componentInstance.move();
  expect(writes).toEqual([
    {
      parent_id: 'destination',
      expected_parent_id: 'project',
      expected_updated_at: fresh.updated_at,
    },
  ]);
  expect(fixture.componentInstance.error()).toBe('Folder changed. Refresh before moving.');
  expect(fixture.componentInstance.pending()).toBe(false);
});
it('discards an in-flight result and clears selected names when the actor changes', async () => {
  let release!: (value: CatalogEntry) => void;
  const response = new Promise<CatalogEntry>((resolve) => {
    release = resolve;
  });
  const { fixture, facade } = await setup(
    async <T>(method: string, path: string) =>
      (method === 'POST' ? response : path.endsWith('/folder') ? folder : { items: [] }) as T,
  );
  fixture.componentInstance.choose('destination');
  const moved = vi.fn();
  fixture.componentInstance.closed.subscribe(moved);
  const pending = fixture.componentInstance.move();
  facade.context.update((value) => value && { ...value, subject: 'other-owner' });
  fixture.detectChanges();
  release({ ...folder, parent_id: 'destination' });
  await pending;
  await fixture.whenStable();
  expect(moved).not.toHaveBeenCalled();
  expect(facade.selected()).toBeNull();
  expect(fixture.componentInstance.fresh()).toBeNull();
  expect(fixture.componentInstance.destination()).toBeNull();
});
