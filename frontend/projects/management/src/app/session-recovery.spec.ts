// Copyright 2026 Firefly Software Foundation
// SPDX-License-Identifier: Apache-2.0
import { signal } from '@angular/core';
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
    selected: signal(null),
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
