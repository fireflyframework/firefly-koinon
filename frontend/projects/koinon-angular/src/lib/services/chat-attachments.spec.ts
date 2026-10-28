// Copyright 2026 Firefly Software Foundation
// SPDX-License-Identifier: Apache-2.0
import { TestBed } from '@angular/core/testing';
import { signal } from '@angular/core';
import {
  KoinonClient,
  KoinonError,
  type AttachmentCapabilities,
  type AttachmentView,
  type HttpMethod,
  type RequestOptions,
  type KoinonTransport,
} from '@fireflyframework/koinon-sdk';
import {
  KoinonFacade,
  KoinonAssistant,
  KoinonClientContext,
} from '@fireflyframework/koinon-angular';
import { KoinonChatAttachments } from '../../../chat/page/src/services/chat-attachments';
const capabilities: AttachmentCapabilities = {
  storage: { available: true, reason: 'Test' },
  database: { available: true, reason: 'Test' },
  extraction: { available: true, reason: 'Test' },
  limits: {
    max_selected: 10,
    max_file_bytes: 1000,
    max_image_bytes: 1000,
    max_thread_files: 20,
    max_thread_bytes: 10000,
    max_model_text_chars: 1000,
    max_model_binary_bytes: 1000,
    extraction_timeout_seconds: 30,
    ttl_seconds: 60,
  },
  formats: [
    {
      kind: 'document',
      media_type: 'text/plain',
      extensions: ['.txt'],
      extraction: { available: true, reason: 'Test' },
    },
  ],
  promotion: {},
};
function remote(revision = 2): AttachmentView {
  return {
    id: 'file',
    tenant_id: 'tenant',
    thread_id: 'thread',
    filename: 'Notes.txt',
    media_type: 'text/plain',
    kind: 'document',
    size_bytes: 5,
    sha256: 'a'.repeat(64),
    status: 'ready',
    revision,
    created_at: new Date().toISOString(),
    expires_at: new Date(Date.now() + 1000).toISOString(),
    chunk_count: 1,
    progress: { status: 'succeeded', percent: 100, attempts: 1 },
  };
}
function setup(
  handler: (method: HttpMethod, path: string, options: RequestOptions) => Promise<unknown>,
) {
  const facade = {
    tenantId: signal('tenant'),
    capabilities: signal({ attachments: capabilities }),
    authRequired: signal(false),
  };
  const assistant = {
    threadId: signal(''),
    contextVersion: signal(0),
    running: signal(false),
    pending: signal(false),
    selectedAgent: signal({ input_modalities: ['text'] }),
    ensureThread: async () => {
      assistant.threadId.set('thread');
      return 'thread';
    },
  };
  const transport: KoinonTransport = {
    request: async <T>(method: HttpMethod, path: string, options: RequestOptions = {}) =>
      (path.endsWith('/capabilities') ? capabilities : await handler(method, path, options)) as T,
    stream: () => {
      throw Error('Unexpected stream');
    },
  };
  const client = new KoinonClient({ transport });
  TestBed.configureTestingModule({
    providers: [
      KoinonChatAttachments,
      { provide: KoinonFacade, useValue: facade },
      { provide: KoinonAssistant, useValue: assistant },
      { provide: KoinonClientContext, useValue: { get: () => client, revision: signal(0) } },
    ],
  });
  const files = TestBed.inject(KoinonChatAttachments);
  TestBed.tick();
  return { files, facade, assistant };
}
const file = () => new File(['Notes'], 'Notes.txt', { type: 'text/plain' });
afterEach(() => vi.useRealTimers());
it('expires a ready selection without allowing expired IDs to be sent', async () => {
  vi.useFakeTimers();
  const { files } = setup(async () => remote());
  await files.select([file()]);
  expect(files.ready()).toBe(true);
  expect(files.ids()).toEqual(['file']);
  vi.advanceTimersByTime(1001);
  expect(files.ready()).toBe(false);
  expect(files.ids()).toEqual([]);
  expect(files.attachments()[0].state).toBe('failed');
});
it('ignores an upload response after the owning context changes', async () => {
  let release: () => void = () => {
    throw Error('Upload did not start');
  };
  const { files, facade, assistant } = setup(
    async () =>
      await new Promise((resolve) => {
        release = () => resolve(remote());
      }),
  );
  const selection = files.select([file()]);
  await Promise.resolve();
  await Promise.resolve();
  expect(files.attachments()).toHaveLength(1);
  facade.tenantId.set('other');
  assistant.contextVersion.update((value) => value + 1);
  TestBed.tick();
  release();
  await selection;
  expect(files.attachments()).toEqual([]);
  expect(files.ids()).toEqual([]);
});
it('reuses the upload idempotency key after an uncertain transport failure', async () => {
  const keys: unknown[] = [];
  let count = 0;
  const { files } = setup(async (method, _path, options) => {
    if (method === 'POST') {
      keys.push(options.headers?.['Idempotency-Key']);
      if (++count === 1) throw new KoinonError(503, 'UNAVAILABLE', 'Connection interrupted');
    }
    return remote();
  });
  await files.select([file()]);
  expect(files.attachments()[0].state).toBe('failed');
  await files.retry(files.attachments()[0].id);
  expect(keys).toHaveLength(2);
  expect(keys[0]).toBeTruthy();
  expect(keys[1]).toBe(keys[0]);
  expect(files.ready()).toBe(true);
});
it('refreshes the file revision after a removal conflict before retrying deletion', async () => {
  const revisions: unknown[] = [];
  const { files } = setup(async (method, _path, options) => {
    if (method === 'DELETE') {
      revisions.push(options.query?.['expected_revision']);
      if (revisions.length === 1) throw new KoinonError(409, 'CONFLICT', 'File changed');
      return undefined;
    }
    return remote(method === 'GET' ? 3 : 2);
  });
  await files.select([file()]);
  const key = files.attachments()[0].id;
  await files.remove(key);
  expect(files.attachments()).toHaveLength(1);
  await files.remove(key);
  expect(revisions).toEqual([2, 3]);
  expect(files.attachments()).toEqual([]);
});
