// Copyright 2026 Firefly Software Foundation
// SPDX-License-Identifier: Apache-2.0
import '@angular/compiler';
import { Injector, runInInjectionContext, signal } from '@angular/core';
import {
  KoinonClient,
  KoinonError,
  type ChatFolder,
  type ChatThread,
  type KoinonTransport,
  type RequestOptions,
  type HttpMethod,
} from '@fireflyframework/koinon-sdk';
import { KoinonFacade } from '../koinon-facade';
import { KoinonClientContext } from './client-context';
import { KoinonConversationGroups } from './conversation-groups';
const thread: ChatThread = {
  id: 'thread',
  title: 'Actual title',
  title_source: 'manual',
  revision: 4,
  folder_id: null,
  archived_at: null,
  scope: { workspace_id: 'w', project_id: 'p' },
  created_at: '2026-10-27T12:00:00Z',
  updated_at: '2026-10-27T12:00:00Z',
};
const folder: ChatFolder = {
  id: 'folder',
  name: 'Research',
  parent_id: null,
  scope: { workspace_id: 'w' },
  revision: 2,
  conversation_count: 1,
  created_at: thread.created_at,
  updated_at: thread.updated_at,
};
function setup() {
  const calls: { method: string; path: string; options: RequestOptions }[] = [];
  const transport: KoinonTransport = {
    request: async <T>(method: HttpMethod, path: string, options: RequestOptions = {}) => {
      calls.push({ method, path, options });
      if (method === 'PATCH')
        return { ...thread, ...((options.body ?? {}) as Partial<ChatThread>), revision: 5 } as T;
      if (method === 'DELETE') return undefined as T;
      if (path.endsWith('title-suggestion'))
        return { title: 'Suggested title', based_on_revision: 4 } as T;
      return {
        items: path.endsWith('folders') ? [folder] : [thread],
        page: options.query?.['page'] ?? 1,
        page_size: 8,
        pages: 3,
        total: 20,
      } as T;
    },
    stream: () => {
      throw Error('Unexpected stream');
    },
  };
  const facade = {
    tenantId: signal('north'),
    workspaceId: signal('w'),
    projectId: signal('p'),
    authRequired: signal(false),
    permissions: signal(new Set(['chat:use'])),
  };
  const clients = { revision: signal(0), get: () => new KoinonClient({ transport }) };
  const injector = Injector.create({
    providers: [
      { provide: KoinonFacade, useValue: facade },
      { provide: KoinonClientContext, useValue: clients },
    ],
  });
  return {
    service: runInInjectionContext(injector, () => new KoinonConversationGroups()),
    calls,
    facade,
    transport,
  };
}
describe('scoped grouped conversation requests', () => {
  it('loads actual root/recent pages and lazy child branches with supported scope filters', async () => {
    const { service, calls } = setup();
    await service.initialize();
    expect(calls).toHaveLength(2);
    expect(calls.find((row) => row.path.endsWith('folders'))?.options.query?.['root_only']).toBe(
      true,
    );
    expect(calls.find((row) => row.path.endsWith('threads'))?.options.query).toMatchObject({
      unfiled: true,
      workspace_id: 'w',
      project_id: 'p',
    });
    await service.toggle(folder);
    expect(calls.at(-2)?.options.query?.['parent_id']).toBe('folder');
    expect(calls.at(-1)?.options.query?.['folder_id']).toBe('folder');
    await service.moreRecent();
    expect(calls.at(-1)?.options.query?.['page']).toBe(2);
    service.ngOnDestroy();
  });
  it('keeps AI proposals separate from explicit CAS save and preserves null unfiling', async () => {
    const { service, calls } = setup();
    await service.initialize();
    const suggestion = await service.suggestTitle(thread, 'agent');
    expect(suggestion?.title).toBe('Suggested title');
    expect(calls.some((row) => row.method === 'PATCH')).toBe(false);
    await service.renameThread(thread, suggestion!.title, suggestion!.based_on_revision);
    expect(calls.find((row) => row.method === 'PATCH')?.options.body).toEqual({
      title: 'Suggested title',
      expected_revision: 4,
    });
    await service.moveThread(thread, null);
    expect(calls.filter((row) => row.method === 'PATCH').at(-1)?.options.body).toEqual({
      folder_id: null,
      expected_revision: 4,
    });
    service.ngOnDestroy();
  });
});

it('aborts and discards an old space response after the host context changes', async () => {
  const { service, transport, facade } = setup();
  const original = transport.request;
  let release!: (page: unknown) => void;
  let oldSignal: AbortSignal | undefined;
  transport.request = async <T>(method:HttpMethod, path:string, options:RequestOptions = {}) => {
    if (path.endsWith('folders') && options.query?.['workspace_id'] === 'w') {
      oldSignal = options.signal;
      return await new Promise<T>((resolve) => {
        release = (page:unknown)=>resolve(page as T);
      });
    }
    if (path.endsWith('folders'))
      return {
        items: [{ ...folder, id: 'new-folder', scope: { workspace_id: 'other' } }],
        page: 1,
        page_size: 12,
        pages: 1,
        total: 1,
      } as T;
    return original<T>(method, path, options);
  };
  const old = service.initialize();
  facade.workspaceId.set('other');
  await service.initialize();
  release({ items: [folder], page: 1, page_size: 12, pages: 1, total: 1 });
  await old;
  expect(oldSignal?.aborted).toBe(true);
  expect(service.roots().items.map((row) => row.id)).toEqual(['new-folder']);
  service.ngOnDestroy();
});
it('propagates expired sessions without turning an access denial into a login failure', async () => {
  const denied = setup();
  denied.transport.request = async () => {
    throw new KoinonError(403, 'DENIED', 'Access denied');
  };
  await denied.service.initialize();
  expect(denied.facade.authRequired()).toBe(false);
  expect(denied.service.roots().error).toBe('Access denied');
  denied.service.ngOnDestroy();
  const expired = setup();
  expired.transport.request = async () => {
    throw new KoinonError(401, 'EXPIRED', 'Session expired');
  };
  await expired.service.initialize();
  expect(expired.facade.authRequired()).toBe(true);
  expect(expired.service.roots().items).toEqual([]);
  expired.service.ngOnDestroy();
});
