// Copyright 2026 Firefly Software Foundation SPDX-License-Identifier: Apache-2.0
import type { CatalogEntry } from '@fireflyframework/koinon-sdk';
import { isFolder, isSystemManaged } from './library-tree';

export type LibraryAction = 'open' | 'details' | 'edit' | 'move' | 'archive' | 'create' | 'add';
export interface LibraryActionRequest {
  action: LibraryAction;
  entry: CatalogEntry | null;
}
export interface LibraryContextRequest {
  entry: CatalogEntry | null;
  x: number;
  y: number;
  trigger: HTMLElement;
}
export interface LibraryMenuAction {
  id: LibraryAction;
  label: string;
  icon: string;
}

export function libraryActions(
  entry: CatalogEntry | null,
  canEdit: boolean,
  canAdd: boolean,
  createLabel: string,
): LibraryMenuAction[] {
  if (!entry)
    return [
      ...(canEdit && createLabel
        ? [{ id: 'create' as const, label: createLabel, icon: 'folder' }]
        : []),
      ...(canAdd ? [{ id: 'add' as const, label: 'Add knowledge', icon: 'plus' }] : []),
    ];
  const actions: LibraryMenuAction[] = [];
  if (isFolder(entry)) actions.push({ id: 'open', label: 'Open folder', icon: 'folder' });
  actions.push({ id: 'details', label: 'Details', icon: 'info' });
  if (canEdit) {
    actions.push({ id: 'edit', label: 'Edit details', icon: 'edit' });
    if (!isSystemManaged(entry)) {
      if (entry.kind === 'collection' || entry.kind === 'corpus')
        actions.push({ id: 'move', label: 'Move Library folder', icon: 'folder' });
      actions.push({ id: 'archive', label: 'Archive', icon: 'archive' });
    }
  }
  return actions;
}
