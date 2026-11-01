// Copyright 2026 Firefly Software Foundation
// SPDX-License-Identifier: Apache-2.0
import { Injector, signal } from '@angular/core';
import { TestBed } from '@angular/core/testing';
import { expect, it, vi } from 'vitest';
import {
  KoinonClient,
  type CatalogEntry,
  type KoinonTransport,
  type RequestOptions,
} from '@fireflyframework/koinon-sdk';
import type { KoinonWorkbench } from '../koinon-angular';
import { KoinonClientContext } from './client-context';
import { libraryUpload } from './library-upload';

function setup() {
  const calls: RequestOptions[] = [];
  const transport: KoinonTransport = {
    request: async <T>(_method: string, _path: string, options: RequestOptions = {}) => {
      calls.push(options);
      return {
        configured: true,
        modes: ['document', 'dataset'],
        max_files: 100,
        max_file_bytes: 134217728,
        max_batch_bytes: 536870912,
        synchronous_max_file_bytes: 33554432,
      } as T;
    },
    stream: () => {
      throw new Error('Streaming is outside this upload fixture');
    },
  };
  const client = new KoinonClient({ transport });
  const pair = signal<KoinonTransport | null>(transport),
    revision = signal(0),
    context = signal<object | null>({ subject: 'actor-a' });
  const permissions = signal(new Set(['catalog:write', 'ingest:write']));
  const folder = {
    id: 'folder',
    tenant_id: 'tenant',
    workspace_id: 'space',
    project_id: 'project',
    kind: 'collection',
    status: 'ready',
  } as CatalogEntry;
  const fake = {
    files: [] as File[],
    formParent: 'folder',
    uploadMode: 'document',
    allEntries: () => [folder],
    f: {
      context,
      tenantId: signal('tenant'),
      workspaceId: signal('space'),
      projectId: signal('project'),
      parentId: signal('folder'),
      tenantPermissions: permissions,
      loadLibrary: vi.fn(async () => undefined),
      upload: vi.fn(async () => true),
      authRequired: signal(false),
      selected: signal(null),
    },
    uploadedFiles: signal(new Set<File>()),
    uploadedCount: signal(0),
    uploadCurrentFile: signal<File | null>(null),
    uploadFailedFile: signal<File | null>(null),
    dialogError: signal(''),
    uploadState: signal('select'),
    uploadDestinationOpen: signal(false),
    i18n: { text: (key: string) => key },
  };
  TestBed.configureTestingModule({
    providers: [
      {
        provide: KoinonClientContext,
        useValue: { revision, get: () => client, getTransport: () => pair() },
      },
    ],
  });
  const runtime = libraryUpload(fake as unknown as KoinonWorkbench, TestBed.inject(Injector));
  TestBed.tick();
  return { runtime, fake, pair, revision, context, calls, permissions, folder };
}
it('managed owner changes abort hashing, discard prior files and prevent old-actor create/PUT requests', async () => {
  const f = setup();
  let finish!: (value: ArrayBuffer) => void;
  const read = vi.fn(
    () =>
      new Promise<ArrayBuffer>((resolve) => {
        finish = resolve;
      }),
  );
  const file = new File(['original'], 'private-office.docx');
  Object.defineProperty(file, 'arrayBuffer', { value: read });
  f.fake.files = [file];
  const pending = f.runtime.start();
  await vi.waitFor(() => expect(read).toHaveBeenCalledOnce());
  f.context.set({ subject: 'actor-b' });
  f.pair.set(null);
  f.revision.update((value) => value + 1);
  expect(f.runtime.coordinator.view().stage).toBe('idle');
  TestBed.tick();
  expect(f.calls[0]!.signal?.aborted).toBe(true);
  expect(f.fake.files).toEqual([]);
  expect(f.fake.formParent).toBe('');
  finish(new ArrayBuffer(1));
  await pending;
  expect(f.calls).toHaveLength(1);
  expect(f.runtime.coordinator.view().items).toEqual([]);
});
it('only currently observed content-write and ingestion permissions make a folder selectable', () => {
  const f = setup();
  expect(f.runtime.canSelect(f.folder)).toBe(true);
  f.permissions.set(new Set(['catalog:read']));
  expect(f.runtime.canSelect(f.folder)).toBe(false);
  expect(f.runtime.canSelect(undefined)).toBe(false);
  expect(f.runtime.canSelect({ ...f.folder, tenant_id: 'another-organization' })).toBe(false);
});
