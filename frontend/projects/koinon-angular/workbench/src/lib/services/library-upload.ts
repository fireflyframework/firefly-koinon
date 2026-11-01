// Copyright 2026 Firefly Software Foundation
// SPDX-License-Identifier: Apache-2.0
import { DestroyRef, effect, type Injector } from '@angular/core';
import type { CatalogEntry } from '@fireflyframework/koinon-sdk';
import type { KoinonWorkbench } from '../koinon-angular';
import { KoinonClientContext } from './client-context';
import { LibraryUploadCoordinator, type UploadScope } from './library-upload-coordinator';

export interface LibraryUploadRuntime {
  coordinator: LibraryUploadCoordinator;
  start(): Promise<void>;
  canSelect(entry: CatalogEntry | undefined): boolean;
  open(): Promise<void>;
  folder(): Promise<void>;
}
const runtimes = new WeakMap<KoinonWorkbench, LibraryUploadRuntime>();

/** WebCrypto reads only one observed, bounded original at a time; no parser runs in the API process. */
export async function hashOriginal(file: File, signal: AbortSignal): Promise<string> {
  signal.throwIfAborted();
  const bytes = await file.arrayBuffer();
  signal.throwIfAborted();
  const digest = await crypto.subtle.digest('SHA-256', bytes);
  signal.throwIfAborted();
  return Array.from(new Uint8Array(digest), (byte) => byte.toString(16).padStart(2, '0')).join('');
}
export function libraryUpload(w: KoinonWorkbench, injector: Injector): LibraryUploadRuntime {
  const existing = runtimes.get(w);
  if (existing) {
    existing.coordinator.syncScope();
    return existing;
  }
  const clients = injector.get(KoinonClientContext);
  let deniedOwner: object | null = null;
  const canSelect = (entry: CatalogEntry | undefined) => {
    if (
      w.f.context() === deniedOwner ||
      !entry ||
      !entry.workspace_id ||
      !['collection', 'corpus'].includes(entry.kind) ||
      entry.status === 'archived' ||
      entry.tenant_id !== w.f.tenantId()
    )
      return false;
    const permissions = new Set(w.f.tenantPermissions());
    const context = w.f.context();
    const scopes =
      context && 'workspace_permissions' in context ? context.workspace_permissions : null;
    const scoped: unknown =
      scopes && typeof scopes === 'object' ? Reflect.get(scopes, entry.workspace_id) : null;
    if (Array.isArray(scoped) && scoped.every((value) => typeof value === 'string'))
      for (const permission of scoped) permissions.add(permission);
    return permissions.has('catalog:write') && permissions.has('ingest:write');
  };
  const scope = (): UploadScope => {
    const folder = w.allEntries().find((entry) => entry.id === w.formParent);
    return {
      owner: w.f.context(),
      clientRevision: clients.revision(),
      tenantId: w.f.tenantId(),
      workspaceId: folder?.workspace_id || '',
      projectId: folder?.project_id || '',
      parentId: folder?.id || '',
      navigationId: w.f.parentId(),
      transport: clients.getTransport(),
      allowed: !!folder && canSelect(folder),
    };
  };
  const coordinator = new LibraryUploadCoordinator({
    scope,
    client: () => clients.get(),
    hash: hashOriginal,
    changed: () => w.f.loadLibrary({ page: 1 }),
    authorityLost: (status) => {
      deniedOwner = w.f.context();
      if (status === 401) w.f.authRequired.set(true);
      w.dialogError.set(
        w.i18n.text(
          'Current upload access could not be verified. Refresh your account access before continuing.',
        ),
      );
    },
    synchronous: async (file, mode, target, signal) => {
      const form = new FormData();
      form.append('file', file);
      form.append('parent_id', target.parentId);
      form.append('mode', mode);
      form.append('workspace_id', target.workspaceId);
      form.append('project_id', target.projectId);
      const done = await w.f.upload(form, { signal });
      if (done) {
        w.uploadedFiles.update((files) => new Set([...files, file]));
        w.uploadedCount.update((count) => count + 1);
      }
      return done;
    },
  });
  effect(
    () => {
      if (!coordinator.syncScope()) {
        w.files = [];
        w.uploadedFiles.set(new Set());
        w.uploadedCount.set(0);
        w.uploadCurrentFile.set(null);
        w.uploadFailedFile.set(null);
        w.dialogError.set('');
        w.formParent = '';
        w.uploadDestinationOpen.set(true);
      }
      const view = coordinator.view();
      w.uploadState.set(
        view.transferring
          ? 'receiving'
          : view.batch || view.uncertain || view.stage === 'observed'
            ? 'complete'
            : 'select',
      );
    },
    { injector },
  );
  injector.get(DestroyRef).onDestroy(() => coordinator.dispose());
  const runtime: LibraryUploadRuntime = {
    coordinator,
    canSelect,
    start: async () => {
      if (w.uploadMode !== 'document' && w.uploadMode !== 'dataset') {
        w.dialogError.set(w.i18n.text('Choose document or dataset mode before uploading.'));
        return;
      }
      await coordinator.start(w.files, w.uploadMode);
    },
    open: async () => {
      const current = coordinator.view();
      if (current.busy) return;
      const owner = w.f.context(),
        revision = clients.revision(),
        parent = w.formParent;
      const item = current.items.find((row) => row.asset_id);
      const selected = item?.asset_id || (w.uploadedCount() ? w.f.selected()?.id : null);
      w.closeDialog();
      await w.openFolder(parent);
      if (owner !== w.f.context() || revision !== clients.revision() || !clients.getTransport())
        return;
      if (
        selected &&
        (await w.f.loadResource(selected)) &&
        owner === w.f.context() &&
        revision === clients.revision()
      ) {
        const entry = w.f.selected();
        if (entry) w.select(entry);
      }
    },
    folder: async () => {
      if (coordinator.view().busy || !clients.getTransport()) return;
      const parent = w.formParent;
      w.closeDialog();
      await w.openFolder(parent);
    },
  };
  runtimes.set(w, runtime);
  return runtime;
}
