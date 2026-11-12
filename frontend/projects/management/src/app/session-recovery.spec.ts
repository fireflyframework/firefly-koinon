// Copyright 2026 Firefly Software Foundation
// SPDX-License-Identifier: Apache-2.0
import { signal } from '@angular/core';
import type { CatalogEntry } from '@fireflyframework/koinon-sdk';
import type { KoinonWorkbench } from '@fireflyframework/koinon-angular/workbench';
import { LibrarySessionDraft } from './session-recovery';

function setup() {
  const f = {
    context: signal({ subject: 'alice' }),
    authRequired: signal(false),
    tenantId: signal('tenant'),
    parentId: signal(''),
    workspaceId: signal(''),
    projectId: signal(''),
    selected: signal<CatalogEntry | null>(null),
    canWrite: signal(true),
    loadResource: vi.fn(async () => false),
  };
  const w = {
    f,
    dialog: signal<'create' | null>('create'),
    formKind: 'workspace',
    formName: 'Private unsaved name',
    formDescription: 'Unsaved text',
    showDialog: vi.fn(),
    openFolder: vi.fn(),
  } as unknown as KoinonWorkbench;
  const recovery = new LibrarySessionDraft(w);
  recovery.track();
  recovery.capture();
  return { f, w, recovery };
}
it('restores bounded draft text only after the same actor and fresh write authority, without submitting', async () => {
  const { w, recovery } = setup();
  w.formName = '';
  expect(await recovery.restore()).toBe(true);
  expect(w.formName).toBe('Private unsaved name');
  expect(w.showDialog).toHaveBeenCalledWith('create');
  expect(await recovery.restore()).toBe(false);
});
it.each(['subject', 'tenant', 'permission', 'logout'])(
  'discards a draft after %s changes',
  async (mode) => {
    const { f, w, recovery } = setup();
    if (mode === 'subject') f.context.set({ subject: 'bob' });
    if (mode === 'tenant') f.tenantId.set('other');
    if (mode === 'permission') f.canWrite.set(false);
    if (mode === 'logout') recovery.clear();
    expect(await recovery.restore()).toBe(false);
    expect(w.showDialog).not.toHaveBeenCalled();
  },
);

it.each(
  ['load', 'folder'].flatMap((boundary) =>
    ['subject', 'clear', 'tenant', 'permission', 'auth'].map((change) => [boundary, change]),
  ),
)('invalidates a captured draft during %s after %s changes', async (boundary, change) => {
  const { f, w, recovery } = setup();
  f.parentId.set('parent');
  f.workspaceId.set('space');
  f.projectId.set('project');
  f.selected.set({
    id: 'parent',
    kind: 'collection',
    workspace_id: 'space',
    project_id: 'project',
    status: 'active',
    tenant_id: 'tenant',
    name: 'Folder',
    description: '',
    parent_id: 'project',
    metadata: {},
    created_at: '2026-11-01T09:00:00Z',
  });
  recovery.track();
  recovery.capture();
  w.formName = '';
  w.formDescription = '';
  let finish!: () => void;
  const pending = new Promise<void>((resolve) => {
    finish = resolve;
  });
  f.loadResource.mockImplementation(async () => {
    if (boundary === 'load') await pending;
    return true;
  });
  vi.mocked(w.openFolder).mockImplementation(async () => {
    if (boundary === 'folder') await pending;
  });
  const restoring = recovery.restore();
  await Promise.resolve();
  if (change === 'subject') f.context.set({ subject: 'bob' });
  if (change === 'clear') recovery.clear();
  if (change === 'tenant') f.tenantId.set('other');
  if (change === 'permission') f.canWrite.set(false);
  if (change === 'auth') f.authRequired.set(true);
  finish();
  expect(await restoring).toBe(false);
  expect(w.formName).toBe('');
  expect(w.formDescription).toBe('');
  expect(w.showDialog).not.toHaveBeenCalled();
});
