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

export function canRunLibraryAction(
  entry: CatalogEntry | null,
  action: LibraryAction,
  canEdit: boolean,
  canAdd = false,
  createLabel = '',
  canRead = true,
): boolean {
  if (!entry) return action === 'create' ? canEdit && !!createLabel : action === 'add' && canAdd;
  if (action === 'open') return isFolder(entry) || (entry.kind === 'document' && canRead);
  if (action === 'details') return true;
  return (
    canEdit &&
    (action === 'edit' ||
      (!isSystemManaged(entry) &&
        (action === 'archive' ||
          (action === 'move' && (entry.kind === 'collection' || entry.kind === 'corpus')))))
  );
}
