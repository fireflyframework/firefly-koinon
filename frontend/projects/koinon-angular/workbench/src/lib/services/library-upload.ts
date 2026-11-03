// Copyright 2026 Firefly Software Foundation
// SPDX-License-Identifier: Apache-2.0
import { DestroyRef, effect, signal, type Injector } from '@angular/core';
import type { CatalogEntry } from '@fireflyframework/koinon-sdk';
import type { KoinonWorkbench } from '../koinon-angular';
import { KoinonClientContext } from '@fireflyframework/koinon-angular/workbench/core';
import { preferredUploadMode, uploadModes, type UploadMode } from './library-upload-selection';
import { UploadObservationLoop } from './upload-observation-loop';
import { LibraryUploadCoordinator, shouldObserveUpload, type UploadScope } from './library-upload-coordinator';

export interface LibraryUploadRuntime {
  coordinator: LibraryUploadCoordinator;
  start(): Promise<void>;
  mode(file: File): UploadMode | null;
  modes(file: File): UploadMode[];
  chooseMode(file: File, mode: UploadMode): void;
  fresh(): boolean;
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
  let destination: CatalogEntry | undefined;
  let receivedAsset: string | null = null;
  const choices = new WeakMap<File, UploadMode>();
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
    const folder = destination ?? w.allEntries().find((entry) => entry.id === w.formParent);
    return {
      owner: w.f.authRequired() ? null : w.f.context(),
      clientRevision: clients.revision(),
      tenantId: w.f.tenantId(),
      workspaceId: folder?.workspace_id || '',
      projectId: folder?.project_id || '',
      parentId: folder?.id || '',
      transport: clients.getTransport(),
      allowed: !w.f.authRequired() && !!folder && canSelect(folder),
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
      const client = clients.get();
      const response = await client.sources.upload(target.tenantId, form, { signal });
      signal.throwIfAborted();
      const current = scope();
      if (
        current.owner !== target.owner ||
        current.clientRevision !== target.clientRevision ||
        current.transport !== target.transport ||
        current.tenantId !== target.tenantId ||
        !current.allowed
      )
        return false;
      const matches = (entry: CatalogEntry) =>
        entry.tenant_id === target.tenantId &&
        entry.workspace_id === target.workspaceId &&
        entry.project_id === target.projectId;
      if (
        !response.source?.id ||
        response.source.kind !== 'source' ||
        !matches(response.source) ||
        response.source.parent_id !== target.parentId ||
        !Array.isArray(response.assets) ||
        response.assets.some(
          (entry) => !entry.id || !matches(entry) || entry.parent_id !== response.source.id,
        )
      )
        throw Error('Upload response destination could not be verified');
      receivedAsset = response.assets[0]?.id || response.source.id;
      w.uploadedFiles.update((files) => new Set([...files, file]));
      w.uploadedCount.update((count) => count + 1);
      return true;
    },
  });
  let authority = {
    owner: w.f.context(),
    revision: clients.revision(),
    tenant: w.f.tenantId(),
    transport: clients.getTransport(),
  };
  effect(
    () => {
      const currentAuthority = {
        owner: w.f.authRequired() ? null : w.f.context(),
        revision: clients.revision(),
        tenant: w.f.tenantId(),
        transport: clients.getTransport(),
      };
      const changedAuthority =
        authority.owner !== currentAuthority.owner ||
        authority.revision !== currentAuthority.revision ||
        authority.tenant !== currentAuthority.tenant ||
        authority.transport !== currentAuthority.transport;
      authority = currentAuthority;
      const sameScope = coordinator.syncScope();
      if (changedAuthority) coordinator.invalidate();
      if (changedAuthority || !sameScope) {
        destination = undefined;
        receivedAsset = null;
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
      w.uploadActivity?.set(
        view.batch || view.transferring || view.uncertain
          ? {
              label: view.transferring
                ? 'Uploading files'
                : view.uncertain
                  ? 'Upload needs attention'
                  : ['queued', 'running'].includes(view.batch?.status || '')
                    ? 'Processing files'
                    : 'Upload updated',
              count: view.batch?.total_items || w.files.length,
              transferring: view.transferring,
            }
          : null,
      );
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
  const visible = signal(typeof document === 'undefined' || document.visibilityState !== 'hidden');
  const visibilityChanged = () => visible.set(document.visibilityState !== 'hidden');
  if (typeof document !== 'undefined')
    document.addEventListener('visibilitychange', visibilityChanged);
  const polling = new UploadObservationLoop({
    active: () => shouldObserveUpload(coordinator.view()),
    visible: () => visible(),
    read: () => coordinator.refresh(),
  });
  effect(
    () => {
      visible();
      coordinator.view();
      polling.update();
    },
    { injector },
  );
  injector.get(DestroyRef).onDestroy(() => {
    polling.dispose();
    coordinator.dispose();
    if (typeof document !== 'undefined')
      document.removeEventListener('visibilitychange', visibilityChanged);
  });
  const runtime: LibraryUploadRuntime = {
    coordinator,
    canSelect,
    mode: (file) => {
      const available = uploadModes(file.name, coordinator.view().capabilities),
        selected = choices.get(file);
      return selected && available.includes(selected)
        ? selected
        : preferredUploadMode(file.name, coordinator.view().capabilities);
    },
    modes: (file) => uploadModes(file.name, coordinator.view().capabilities),
    chooseMode: (file, mode) => {
      if (!coordinator.view().busy && runtime.modes(file).includes(mode)) choices.set(file, mode);
    },
    fresh: () => {
      if (!coordinator.detachSubmitted()) return false;
      destination = undefined;
      receivedAsset = null;
      return true;
    },
    start: async () => {
      if (coordinator.view().busy || coordinator.view().batch || coordinator.view().uncertain)
        return;
      const folder = w.allEntries().find((entry) => entry.id === w.formParent);
      if (!folder || !canSelect(folder)) return;
      destination = folder;
      const selected = w.files.map((file) => choices.get(file));
      await coordinator.start(w.files, selected);
    },
    open: async () => {
      const current = coordinator.view();
      if (current.busy) return;
      const owner = w.f.context(),
        revision = clients.revision(),
        parent = destination?.id || w.formParent;
      const item = current.items.find((row) => row.asset_id);
      const selected = item?.asset_id || receivedAsset;
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
      const parent = destination?.id || w.formParent;
      w.closeDialog();
      await w.openFolder(parent);
    },
  };
  runtimes.set(w, runtime);
  return runtime;
}
