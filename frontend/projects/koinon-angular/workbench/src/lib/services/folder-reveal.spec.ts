// Copyright 2026 Firefly Software Foundation
// SPDX-License-Identifier: Apache-2.0
import { TestBed } from '@angular/core/testing';
import { expect, it, vi } from 'vitest';
import type { CatalogEntry } from '@fireflyframework/koinon-sdk';
import { KoinonFolderTree } from '../organisms/folder-tree';
it('reveals the known space without selecting it as an upload destination', async () => {
  const rows = [
    { id: 'space', kind: 'workspace', name: 'Research space', parent_id: null, status: 'ready' },
    {
      id: 'project',
      kind: 'project',
      name: 'Research project',
      parent_id: 'space',
      status: 'ready',
    },
    {
      id: 'folder',
      kind: 'collection',
      name: 'Source folder',
      parent_id: 'project',
      status: 'ready',
    },
  ] as CatalogEntry[];
  const fixture = TestBed.createComponent(KoinonFolderTree);
  fixture.componentRef.setInput('entries', rows);
  fixture.componentRef.setInput('contextKey', 'tenant');
  fixture.componentRef.setInput('currentId', '');
  fixture.componentRef.setInput('revealId', 'space');
  fixture.componentRef.setInput('selectableKinds', ['collection', 'corpus']);
  fixture.componentRef.setInput('loadChildren', async (id: string) => {
    const ids = rows.filter((row) => (row.parent_id || '') === id).map((row) => row.id);
    return { ids, page: 1, pages: 1, total: ids.length };
  });
  const selected = vi.fn();
  fixture.componentInstance.selected.subscribe(selected);
  fixture.detectChanges();
  await fixture.whenStable();
  fixture.detectChanges();
  expect(fixture.nativeElement.textContent).toContain('Research project');
  const space = fixture.nativeElement.querySelector('[data-tree-id="space"]');
  expect(space.getAttribute('aria-expanded')).toBe('true');
  expect(space.getAttribute('aria-selected')).toBe('false');
  expect(selected).not.toHaveBeenCalled();
  const project = fixture.componentInstance.visible().find((row) => row.id === 'project')!;
  await fixture.componentInstance.select(project);
  fixture.detectChanges();
  const folder = fixture.componentInstance.visible().find((row) => row.id === 'folder')!;
  await fixture.componentInstance.select(folder);
  expect(selected).toHaveBeenCalledExactlyOnceWith('folder');
  fixture.destroy();
});
