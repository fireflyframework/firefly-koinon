// Copyright 2026 Firefly Software Foundation SPDX-License-Identifier: Apache-2.0
import { TestBed } from '@angular/core/testing';
import type { CatalogEntry } from '@fireflyframework/koinon-sdk';
import { KoinonResourceList } from '../organisms/resource-list';
import { KoinonLibraryTemplate } from '../templates/library-template';
import { libraryActions } from '../organisms/library-context-menu';
import { canRunLibraryAction } from './library-context-actions';

const folder: CatalogEntry = {
  id: 'folder',
  tenant_id: 'tenant',
  name: 'Policies',
  kind: 'collection',
  parent_id: 'project',
  workspace_id: 'space',
  project_id: 'project',
  description: '',
  metadata: {},
  status: 'ready',
  created_at: '2026-11-02T00:00:00Z',
};

it('opens the same item actions with a right click and the visible action button', () => {
  const fixture = TestBed.createComponent(KoinonResourceList);
  fixture.componentRef.setInput('items', [folder]);
  fixture.detectChanges();
  const requests: unknown[] = [];
  fixture.componentInstance.contextRequested.subscribe((value) => requests.push(value.entry));
  const row = fixture.nativeElement.querySelector('.row:not(.header)');
  const event = new MouseEvent('contextmenu', { bubbles: true, cancelable: true });
  row.dispatchEvent(event);
  expect(event.defaultPrevented).toBe(true);
  fixture.nativeElement.querySelector('button[aria-haspopup="menu"]').click();
  expect(requests).toEqual([folder, folder]);
});

it('supports Shift+F10 from an item without opening the browser menu', () => {
  const fixture = TestBed.createComponent(KoinonResourceList);
  fixture.componentRef.setInput('items', [folder]);
  fixture.detectChanges();
  const requests: unknown[] = [];
  fixture.componentInstance.contextRequested.subscribe((value) => requests.push(value.entry));
  const event = new KeyboardEvent('keydown', {
    key: 'F10',
    shiftKey: true,
    bubbles: true,
    cancelable: true,
  });
  fixture.nativeElement.querySelector('button.name').dispatchEvent(event);
  expect(event.defaultPrevented).toBe(true);
  expect(requests).toEqual([folder]);
});

it('keeps system folders protected and removes mutation actions for readers', () => {
  expect(
    libraryActions({ ...folder, system_managed: true }, true, true, 'Create a folder').map(
      (action) => action.id,
    ),
  ).toEqual(['open', 'details', 'edit']);
  expect(libraryActions(folder, false, false, '').map((action) => action.id)).toEqual([
    'open',
    'details',
  ]);
  expect(libraryActions(folder, true, true, '').map((action) => action.id)).toEqual([
    'open',
    'details',
    'edit',
    'move',
    'archive',
  ]);
  expect(libraryActions(null, false, false, '')).toEqual([]);
});

it('routes creation in empty space through the existing create action and rechecks rights', () => {
  const fixture = TestBed.createComponent(KoinonLibraryTemplate);
  fixture.componentRef.setInput('canEdit', true);
  fixture.componentRef.setInput('canAdd', true);
  fixture.componentRef.setInput('createLabel', 'Create a folder');
  fixture.detectChanges();
  let created = 0;
  fixture.componentInstance.createRequested.subscribe(() => created++);
  const surface = fixture.nativeElement.querySelector('.collection-surface');
  surface.dispatchEvent(new MouseEvent('contextmenu', { bubbles: true, cancelable: true }));
  expect(fixture.componentInstance.contextMenu?.entry).toBeNull();
  fixture.componentInstance.chooseContext('create');
  expect(created).toBe(1);
  surface.dispatchEvent(new MouseEvent('contextmenu', { bubbles: true, cancelable: true }));
  fixture.componentRef.setInput('canEdit', false);
  fixture.detectChanges();
  fixture.componentInstance.chooseContext('create');
  expect(created).toBe(1);
});

it('rejects stale mutation choices against current permissions and protected item state', () => {
  expect(canRunLibraryAction(folder, 'archive', false)).toBe(false);
  expect(canRunLibraryAction({ ...folder, system_managed: true }, 'archive', true)).toBe(false);
  expect(canRunLibraryAction({ ...folder, system_managed: true }, 'move', true)).toBe(false);
  expect(canRunLibraryAction({ ...folder, kind: 'workspace' }, 'move', true)).toBe(false);
  expect(canRunLibraryAction(folder, 'create', true, true, 'Create a folder')).toBe(false);
  expect(canRunLibraryAction(folder, 'details', false)).toBe(true);
});
