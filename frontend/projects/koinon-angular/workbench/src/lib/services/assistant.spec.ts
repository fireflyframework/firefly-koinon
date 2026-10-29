// Copyright 2026 Firefly Software Foundation SPDX-License-Identifier: Apache-2.0
import { TestBed } from '@angular/core/testing';
import {
  KoinonClient,
  KoinonError,
  type KoinonTransport,
  type HttpMethod,
  type RequestOptions,
  type ChatMessage,
} from '@fireflyframework/koinon-sdk';
import { provideKoinonClient } from '../client-provider';
import { KoinonFacade } from '../koinon-facade';
import { KoinonAssistant } from './assistant';
const defaultChatSettings = (path: string, id = 'agent') => ({
  tenant_id: path.split('/')[2],
  default_agent_id: id,
  revision: 1,
  configured: true,
  can_run: true,
  status: 'ready',
});
const message = (id: string, text: string): ChatMessage => ({
  id,
  role: 'assistant',
  run_id: 'run',
  text,
  status: 'completed',
  citations: [],
  artifacts: [],
  created_at: '2026-10-26',
});
describe('persisted assistant runs', () => {
  it('handles reset without erasing other messages and reloads canonical completion', async () => {
    let reload = 0,
      submitted = false;
    let threadReads = 0;
    const transport: KoinonTransport = {
      request: async <T>(_method: HttpMethod, path: string) => {
        const value = path.endsWith('/chat/settings')
          ? defaultChatSettings(path)
          : path.endsWith('/agents')
            ? { items: [{ id: 'agent', name: 'Local research', status: 'ready', checks: [] }] }
            : path.endsWith('/chat/threads')
              ? { items: [{ id: 'thread', title: 'Research', scope: {} }] }
              : path.endsWith('/messages')
                ? {
                    items: submitted
                      ? [
                          message('earlier', 'Keep this answer'),
                          {
                            ...message('answer', ++reload < 3 ? '' : 'Canonical answer'),
                            run_id: 'run',
                            status: reload < 3 ? 'running' : 'completed',
                            ...(reload === 1 ? { answer_policy: { outcome: 'grounded' } } : {}),
                          },
                        ]
                      : [message('earlier', 'Keep this answer')],
                  }
                : path.endsWith('/runs')
                  ? ((submitted = true), { run_id: 'run', message_id: 'answer' })
                  : path.endsWith('/chat/threads/thread')
                    ? (++threadReads,
                      {
                        id: 'thread',
                        title: 'Service review changes',
                        revision: 2,
                        title_source: 'ai',
                        scope: {},
                      })
                    : {};
        return value as T;
      },
      stream: async function* <T>() {
        for (const event of [
          { type: 'message_delta', data: { text: 'Discarded partial' } },
          { type: 'message_reset', data: { message_id: 'answer', status: 'completed' } },
          {
            type: 'message_metadata',
            data: {
              answer_policy: { outcome: 'grounded' },
              presentation: {
                locale: 'es-ES',
                time_zone: 'Europe/Madrid',
                response_language: 'es',
              },
            },
          },
          { type: 'message_delta', data: { text: 'Canonical answer' } },
          { type: 'completed', data: { status: 'completed' } },
        ]) {
          yield { id: '', ...event, data: event.data as T };
          if (event.type === 'message_reset')
            expect(
              assistant.messages().find((message) => message.id === 'answer')?.answer_policy,
            ).toBeUndefined();
          if (event.type === 'message_metadata') {
            expect(
              assistant.messages().find((message) => message.id === 'answer')?.answer_policy
                ?.outcome,
            ).toBe('grounded');
            expect(
              assistant.messages().find((message) => message.id === 'answer')?.presentation?.locale,
            ).toBe('es-ES');
          }
        }
      },
    };
    await TestBed.configureTestingModule({
      providers: [
        KoinonFacade,
        KoinonAssistant,
        ...provideKoinonClient(new KoinonClient({ transport }), transport),
      ],
    }).compileComponents();
    const f = TestBed.inject(KoinonFacade);
    f.tenantId.set('tenant');
    const assistant = TestBed.inject(KoinonAssistant);
    await assistant.initialize();
    await assistant.send('Explain this evidence');
    expect(assistant.messages().find((x) => x.id === 'earlier')?.text).toBe('Keep this answer');
    expect(assistant.messages().find((x) => x.id === 'answer')?.text).toBe('Canonical answer');
    expect(assistant.running()).toBe(false);
    expect(assistant.error()).toBe('');
    expect(threadReads).toBe(1);
    expect(assistant.activeThread()?.title).toBe('Service review changes');
  });
});
it('pages and filters server history without changing the active conversation knowledge scope', async () => {
  const queries: unknown[] = [];
  const first = {
    id: 'thread-first',
    title: 'Current conversation',
    revision: 1,
    title_source: 'manual',
    folder_id: null,
    archived_at: null,
    scope: { workspace_id: 'space-a' },
  };
  const second = {
    ...first,
    id: 'thread-second',
    title: 'Archived policy',
    archived_at: '2026-10-26',
    scope: { workspace_id: 'space-b' },
  };
  const transport: KoinonTransport = {
    request: async <T>(_method: HttpMethod, path: string, options?: RequestOptions) => {
      if (path.endsWith('/chat/settings')) return defaultChatSettings(path) as T;
      if (path.endsWith('/agents')) return { items: [] } as T;
      if (path.endsWith('/chat/threads')) {
        queries.push(options?.query);
        return {
          items: [options?.query?.['page'] === 2 ? second : first],
          page: options?.query?.['page'] ?? 1,
          page_size: 25,
          total: 51,
          pages: 3,
        } as T;
      }
      if (path.endsWith('/messages')) return { items: [] } as T;
      if (path.endsWith('/thread-first')) return first as T;
      throw new Error('Unexpected history request');
    },
    stream: () => {
      throw new Error('History browsing must not start a model run');
    },
  };
  TestBed.configureTestingModule({
    providers: [
      KoinonFacade,
      KoinonAssistant,
      ...provideKoinonClient(new KoinonClient({ transport }), transport),
    ],
  });
  TestBed.inject(KoinonFacade).tenantId.set('tenant');
  const assistant = TestBed.inject(KoinonAssistant);
  await assistant.initialize();
  await assistant.loadThreads({ page: 2, q: 'policy', status: 'archived' });
  expect(assistant.threads().map((row) => row.id)).toEqual(['thread-second']);
  expect(assistant.activeThread()?.id).toBe('thread-first');
  expect(assistant.scope()).toEqual({ workspace_id: 'space-a' });
  expect(assistant.historyPage()?.total).toBe(51);
  expect(queries[1]).toEqual({ page: 2, page_size: 25, q: 'policy', status: 'archived' });
});
it('loads older messages using the opaque server cursor without replacing current messages', async () => {
  const reads: unknown[] = [],
    transport: KoinonTransport = {
      request: async <T>(_method: HttpMethod, path: string, options?: RequestOptions) => {
        const value = path.endsWith('/chat/settings')
          ? defaultChatSettings(path)
          : path.endsWith('/agents')
            ? { items: [] }
            : path.endsWith('/chat/threads')
              ? { items: [{ id: 'thread', title: 'Research', scope: {} }] }
              : path.endsWith('/messages')
                ? (reads.push(options?.query),
                  options?.query?.['before']
                    ? {
                        items: [
                          { ...message('older', 'Earlier evidence'), created_at: '2026-10-25' },
                        ],
                        next_cursor: null,
                      }
                    : {
                        items: [message('current', 'Current evidence')],
                        next_cursor: 'opaque-page-cursor',
                      })
                : {};
        return value as T;
      },
      stream: () => {
        throw new Error('Unexpected stream');
      },
    };
  TestBed.configureTestingModule({
    providers: [
      KoinonFacade,
      KoinonAssistant,
      ...provideKoinonClient(new KoinonClient({ transport }), transport),
    ],
  });
  TestBed.inject(KoinonFacade).tenantId.set('tenant');
  const assistant = TestBed.inject(KoinonAssistant);
  await assistant.initialize();
  expect(assistant.olderCursor()).toBe('opaque-page-cursor');
  await assistant.loadOlder();
  expect(assistant.messages().map((row) => row.id)).toEqual(['older', 'current']);
  expect(assistant.olderCursor()).toBeNull();
  expect(reads).toEqual([{ limit: 40 }, { before: 'opaque-page-cursor', limit: 40 }]);
});
it('allows an explicitly runnable unverified agent without labeling it ready', async () => {
  let completed = false;
  let createdBody: unknown;
  const transport: KoinonTransport = {
    request: async <T>(method: HttpMethod, path: string, options?: RequestOptions) => {
      if (method === 'POST' && path.endsWith('/chat/threads')) createdBody = options?.body;
      const value = path.endsWith('/chat/settings')
        ? defaultChatSettings(path, 'trial')
        : path.endsWith('/agents')
          ? {
              items: [
                {
                  id: 'trial',
                  name: 'Local trial',
                  status: 'unverified',
                  can_run: true,
                  checks: [],
                },
              ],
            }
          : path.endsWith('/chat/threads')
            ? method === 'GET'
              ? { items: [] }
              : { id: 'thread', title: 'Trial', scope: {} }
            : path.endsWith('/runs')
              ? { run_id: 'run', message_id: 'answer' }
              : path.endsWith('/messages')
                ? {
                    items: [
                      {
                        ...message('answer', completed ? 'Observed answer' : ''),
                        status: completed ? 'completed' : 'running',
                      },
                    ],
                  }
                : {};
      return value as T;
    },
    stream: async function* <T>() {
      completed = true;
      yield { id: '1', type: 'completed', data: { status: 'completed' } as T };
    },
  };
  TestBed.configureTestingModule({
    providers: [
      KoinonFacade,
      KoinonAssistant,
      ...provideKoinonClient(new KoinonClient({ transport }), transport),
    ],
  });
  TestBed.inject(KoinonFacade).tenantId.set('tenant');
  const assistant = TestBed.inject(KoinonAssistant);
  await assistant.initialize();
  expect(await assistant.send('Try this local agent')).toBe(true);
  expect(assistant.selectedAgent()?.status).toBe('unverified');
  expect(createdBody).toEqual({ scope: {} });
  expect(assistant.messages()[0].text).toBe('Observed answer');
});
for (const status of [401, 403])
  it(`assistant ${status} preserves the session-expiry boundary`, async () => {
    const transport: KoinonTransport = {
      request: async () => {
        throw new KoinonError(status, 'DENIED', 'Observed request failure');
      },
      stream: () => {
        throw new Error('Unexpected stream');
      },
    };
    TestBed.configureTestingModule({
      providers: [
        KoinonFacade,
        KoinonAssistant,
        ...provideKoinonClient(new KoinonClient({ transport }), transport),
      ],
    });
    const f = TestBed.inject(KoinonFacade);
    f.tenantId.set('tenant');
    const assistant = TestBed.inject(KoinonAssistant);
    await assistant.initialize();
    expect(f.authRequired()).toBe(status === 401);
    expect(assistant.error()).toBe('Observed request failure');
  });

it('resumes an interrupted event stream from the last cursor without resubmitting the question', async () => {
  let submitted = 0,
    streams = 0,
    completed = false;
  const cursors: unknown[] = [];
  const transport: KoinonTransport = {
    request: async <T>(method: HttpMethod, path: string) => {
      const value = path.endsWith('/chat/settings')
        ? defaultChatSettings(path)
        : path.endsWith('/agents')
          ? { items: [{ id: 'agent', name: 'Guide', status: 'ready' }] }
          : path.endsWith('/chat/threads')
            ? { items: [{ id: 'thread', title: 'Research', scope: {} }] }
            : path.endsWith('/runs')
              ? (++submitted, { run_id: 'run', message_id: 'answer', event_cursor: '0' })
              : path.endsWith('/messages')
                ? {
                    items: submitted
                      ? [
                          {
                            ...message('answer', completed ? 'First second' : ''),
                            status: completed ? 'completed' : 'running',
                          },
                        ]
                      : [],
                  }
                : {};
      return value as T;
    },
    stream: async function* <T>(_method: HttpMethod, _path: string, options?: RequestOptions) {
      cursors.push(options?.headers?.['Last-Event-ID']);
      ++streams;
      yield { id: '1', type: 'message_delta', data: { text: 'First ' } as T };
      if (streams === 1) throw new TypeError('Controlled connection interruption');
      yield { id: '2', type: 'message_delta', data: { text: 'second' } as T };
      completed = true;
      yield { id: '3', type: 'completed', data: { status: 'completed' } as T };
    },
  };
  TestBed.configureTestingModule({
    providers: [
      KoinonFacade,
      KoinonAssistant,
      ...provideKoinonClient(new KoinonClient({ transport }), transport),
    ],
  });
  TestBed.inject(KoinonFacade).tenantId.set('tenant');
  const assistant = TestBed.inject(KoinonAssistant);
  await assistant.initialize();
  expect(await assistant.send('Explain this evidence')).toBe(true);
  expect(submitted).toBe(1);
  expect(streams).toBe(2);
  expect(cursors).toEqual(['0', '1']);
  expect(assistant.messages()[0].text).toBe('First second');
  expect(assistant.error()).toBe('');
});

for (const status of [401, 403, 503])
  it(`bounds stream recovery and preserves a ${status} denial`, async () => {
    let submitted = 0,
      streams = 0;
    const transport: KoinonTransport = {
      request: async <T>(_method: HttpMethod, path: string) => {
        const value = path.endsWith('/chat/settings')
          ? defaultChatSettings(path)
          : path.endsWith('/agents')
            ? { items: [{ id: 'agent', status: 'ready' }] }
            : path.endsWith('/chat/threads')
              ? { items: [{ id: 'thread', title: 'Research', scope: {} }] }
              : path.endsWith('/runs')
                ? (++submitted, { run_id: 'run', message_id: 'answer' })
                : path.endsWith('/messages')
                  ? { items: submitted ? [{ ...message('answer', ''), status: 'running' }] : [] }
                  : {};
        return value as T;
      },
      stream: () => {
        ++streams;
        throw new KoinonError(status, 'CONTROLLED_FAILURE', 'Observed stream failure');
      },
    };
    TestBed.configureTestingModule({
      providers: [
        KoinonFacade,
        KoinonAssistant,
        ...provideKoinonClient(new KoinonClient({ transport }), transport),
      ],
    });
    const facade = TestBed.inject(KoinonFacade);
    facade.tenantId.set('tenant');
    const assistant = TestBed.inject(KoinonAssistant);
    await assistant.initialize();
    await assistant.send('Explain this evidence');
    expect(submitted).toBe(1);
    expect(streams).toBe(status === 503 ? 3 : 1);
    expect(facade.authRequired()).toBe(status === 401);
    expect(assistant.error()).toBe('Observed stream failure');
    expect(assistant.running()).toBe(false);
  });

it('abandons a pending reconnect when the organization context changes', async () => {
  let submitted = false,
    streams = 0;
  const transport: KoinonTransport = {
    request: async <T>(_method: HttpMethod, path: string) => {
      const value = path.endsWith('/chat/settings')
        ? defaultChatSettings(path)
        : path.endsWith('/agents')
          ? { items: [{ id: 'agent', status: 'ready' }] }
          : path.endsWith('/chat/threads')
            ? { items: [{ id: 'thread', title: 'Research', scope: {} }] }
            : path.endsWith('/runs')
              ? ((submitted = true), { run_id: 'run', message_id: 'answer' })
              : path.endsWith('/messages')
                ? { items: submitted ? [{ ...message('answer', ''), status: 'running' }] : [] }
                : {};
      return value as T;
    },
    stream: () => {
      ++streams;
      throw new TypeError('Controlled interruption');
    },
  };
  TestBed.configureTestingModule({
    providers: [
      KoinonFacade,
      KoinonAssistant,
      ...provideKoinonClient(new KoinonClient({ transport }), transport),
    ],
  });
  const facade = TestBed.inject(KoinonFacade);
  facade.tenantId.set('tenant');
  const assistant = TestBed.inject(KoinonAssistant);
  await assistant.initialize();
  const sending = assistant.send('Explain this evidence');
  await new Promise((resolve) => setTimeout(resolve, 0));
  expect(streams).toBe(1);
  facade.tenantId.set('another-tenant');
  TestBed.tick();
  await sending;
  expect(streams).toBe(1);
  expect(assistant.messages()).toEqual([]);
  expect(assistant.error()).toBe('');
  expect(assistant.running()).toBe(false);
});

it('asks the server to page agents and history within the selected knowledge scope', async () => {
  const reads: { path: string; query: RequestOptions['query'] }[] = [];
  const transport: KoinonTransport = {
    request: async <T>(_method: HttpMethod, path: string, options?: RequestOptions) => {
      reads.push({ path, query: options?.query });
      return { items: [] } as T;
    },
    stream: () => {
      throw new Error('Unexpected stream');
    },
  };
  TestBed.configureTestingModule({
    providers: [
      KoinonFacade,
      KoinonAssistant,
      ...provideKoinonClient(new KoinonClient({ transport }), transport),
    ],
  });
  const facade = TestBed.inject(KoinonFacade);
  facade.tenantId.set('tenant');
  facade.workspaceId.set('workspace');
  facade.projectId.set('project');
  await TestBed.inject(KoinonAssistant).initialize();
  expect(reads.find((read) => read.path.endsWith('/chat/settings'))?.query).toEqual({
    workspace_id: 'workspace',
    project_id: 'project',
  });
  expect(reads.find((read) => read.path.endsWith('/agents'))?.query).toEqual({
    workspace_id: 'workspace',
    project_id: 'project',
  });
  expect(reads.find((read) => read.path.endsWith('/chat/threads'))?.query).toEqual({
    page: 1,
    page_size: 25,
    status: 'active',
    workspace_id: 'workspace',
    project_id: 'project',
  });
});

it('keeps grouped chat scope unchanged and includes only explicit attachment IDs', async () => {
  const writes: { path: string; body: unknown }[] = [];
  const scope = {
    workspace_id: 'workspace',
    project_id: 'project',
    asset_ids: ['selected-document'],
  };
  const transport: KoinonTransport = {
    request: async <T>(method: HttpMethod, path: string, options?: RequestOptions) => {
      if (method === 'POST') writes.push({ path, body: options?.body });
      const value = path.endsWith('/chat/settings')
        ? defaultChatSettings(path)
        : path.endsWith('/agents')
          ? { items: [{ id: 'agent', status: 'ready' }] }
          : path.endsWith('/chat/threads')
            ? method === 'POST'
              ? { id: 'created', scope, revision: 1 }
              : { items: [] }
            : path.endsWith('/runs')
              ? { run_id: 'run', message_id: 'answer' }
              : path.endsWith('/messages')
                ? { items: [message('answer', 'Stored result')] }
                : path.endsWith('/created')
                  ? { id: 'created', scope, revision: 2 }
                  : {};
      return value as T;
    },
    stream: () => {
      throw Error('Completed history must not start a stream');
    },
  };
  TestBed.configureTestingModule({
    providers: [
      KoinonFacade,
      KoinonAssistant,
      ...provideKoinonClient(new KoinonClient({ transport }), transport),
    ],
  });
  const facade = TestBed.inject(KoinonFacade);
  facade.tenantId.set('tenant');
  const assistant = TestBed.inject(KoinonAssistant);
  await assistant.initialize();
  assistant.newConversation({
    id: 'folder',
    name: 'Policy',
    scope,
    parent_id: null,
    revision: 1,
    conversation_count: 0,
    created_at: '2026-10-26',
    updated_at: '2026-10-26',
  });
  expect(assistant.scope()).toEqual(scope);
  expect(await assistant.ensureThread()).toBe('created');
  expect(await assistant.send('Explain this file', ['file-b', 'file-a'])).toBe(true);
  expect(writes.filter((row) => row.path.endsWith('/chat/threads'))).toHaveLength(1);
  expect(writes[0].body).toEqual({ folder_id: 'folder', scope });
  expect(writes.find((row) => row.path.endsWith('/runs'))?.body).toMatchObject({
    attachment_ids: ['file-b', 'file-a'],
    scope,
  });
});

it('projects tool lifecycle once per invocation and ignores older replayed transitions', async () => {
  let submitted = false;
  const activity = {
    call_id: 'call',
    tool_name: 'search_knowledge' as const,
    status: 'completed' as const,
    occurred_at: '2026-10-27T12:00:02Z',
    duration_ms: 12,
    summary: 'Read accessible sources',
  };
  const transport: KoinonTransport = {
    request: async <T>(_method: HttpMethod, path: string) => {
      const value = path.endsWith('/chat/settings')
        ? defaultChatSettings(path)
        : path.endsWith('/agents')
          ? { items: [{ id: 'agent', status: 'ready' }] }
          : path.endsWith('/chat/threads')
            ? { items: [{ id: 'thread', scope: {}, revision: 1 }] }
            : path.endsWith('/runs')
              ? ((submitted = true), { run_id: 'run', message_id: 'answer' })
              : path.endsWith('/messages')
                ? { items: submitted ? [{ ...message('answer', ''), status: 'running' }] : [] }
                : path.endsWith('/thread')
                  ? { id: 'thread', scope: {}, revision: 1 }
                  : {};
      return value as T;
    },
    stream: async function* <T>() {
      for (const entry of [
        { ...activity, status: 'queued', occurred_at: '2026-10-27T12:00:00Z' },
        activity,
        { ...activity, status: 'running', occurred_at: '2026-10-27T12:00:01Z' },
      ]) {
        yield { id: entry.occurred_at, type: 'tool_activity', data: { tool_activity: entry } as T };
      }
      expect(assistant.messages()[0].tool_activities).toEqual([activity]);
      expect(assistant.messages()[0].tool_activity_count).toBe(1);
      throw new KoinonError(403, 'FORBIDDEN', 'Stopped fixture');
    },
  };
  TestBed.configureTestingModule({
    providers: [
      KoinonFacade,
      KoinonAssistant,
      ...provideKoinonClient(new KoinonClient({ transport }), transport),
    ],
  });
  TestBed.inject(KoinonFacade).tenantId.set('tenant');
  const assistant = TestBed.inject(KoinonAssistant);
  await assistant.initialize();
  expect(await assistant.send('Read the policy')).toBe(true);
  expect(assistant.error()).toBe('Stopped fixture');
  expect(assistant.messages()[0].tool_activities).toEqual([activity]);
});

it('discards a delayed thread creation when a new folder draft replaces it', async () => {
  let release: () => void = () => {
    throw Error('Deferred response has not been registered');
  };
  const transport: KoinonTransport = {
    request: async <T>(method: HttpMethod, path: string) => {
      if (path.endsWith('/chat/threads') && method === 'POST')
        return await new Promise<T>((resolve) => {
          release = () => resolve({ id: 'old-thread', scope: {}, revision: 1 } as T);
        });
      return (
        path.endsWith('/chat/settings')
          ? defaultChatSettings(path)
          : path.endsWith('/agents')
            ? { items: [{ id: 'agent', status: 'ready' }] }
            : { items: [] }
      ) as T;
    },
    stream: () => {
      throw Error('Unexpected stream');
    },
  };
  TestBed.configureTestingModule({
    providers: [
      KoinonFacade,
      KoinonAssistant,
      ...provideKoinonClient(new KoinonClient({ transport }), transport),
    ],
  });
  TestBed.inject(KoinonFacade).tenantId.set('tenant');
  const assistant = TestBed.inject(KoinonAssistant);
  await assistant.initialize();
  const pending = assistant.ensureThread();
  expect(assistant.pending()).toBe(true);
  assistant.newConversation({
    id: 'new-folder',
    name: 'New context',
    scope: { workspace_id: 'new-space' },
    parent_id: null,
    revision: 1,
    conversation_count: 0,
    created_at: '2026-10-26',
    updated_at: '2026-10-26',
  });
  release();
  expect(await pending).toBeNull();
  expect(assistant.threadId()).toBe('');
  expect(assistant.activeThread()).toBeUndefined();
  expect(assistant.draftFolder()?.id).toBe('new-folder');
  expect(assistant.scope()).toEqual({ workspace_id: 'new-space' });
  expect(assistant.pending()).toBe(false);
});

it('does not reinsert old tool activity when a deferred page arrives after a run reset', async () => {
  let submitted = false;
  let release: () => void = () => {
    throw Error('Deferred response has not been registered');
  };
  const previous = {
    call_id: 'old-attempt',
    tool_name: 'search_knowledge' as const,
    status: 'completed' as const,
    occurred_at: '2026-10-27T12:00:00Z',
    summary: 'Previous attempt',
  };
  const transport: KoinonTransport = {
    request: async <T>(_method: HttpMethod, path: string) => {
      if (path.endsWith('/activity'))
        return await new Promise<T>((resolve) => {
          release = () => resolve({ items: [previous], total: 1, page: 1, pages: 1 } as T);
        });
      return (
        path.endsWith('/chat/settings')
          ? defaultChatSettings(path)
          : path.endsWith('/agents')
            ? { items: [{ id: 'agent', status: 'ready' }] }
            : path.endsWith('/chat/threads')
              ? { items: [{ id: 'thread', scope: {}, revision: 1 }] }
              : path.endsWith('/runs')
                ? ((submitted = true), { run_id: 'run', message_id: 'answer' })
                : path.endsWith('/messages')
                  ? {
                      items: submitted
                        ? [
                            {
                              ...message('answer', ''),
                              status: 'running',
                              tool_activities: [],
                              tool_activity_count: 0,
                            },
                          ]
                        : [],
                    }
                  : path.endsWith('/thread')
                    ? { id: 'thread', scope: {}, revision: 1 }
                    : {}
      ) as T;
    },
    stream: async function* <T>() {
      const pending = assistant.loadActivity(assistant.messages()[0]);
      yield {
        id: '1',
        type: 'message_reset',
        data: { message_id: 'answer', status: 'running' } as T,
      };
      release();
      await pending;
      expect(assistant.messages()[0].tool_activities).toEqual([]);
      expect(assistant.messages()[0].tool_activity_count).toBe(0);
      throw new KoinonError(403, 'FORBIDDEN', 'End of controlled stream');
    },
  };
  TestBed.configureTestingModule({
    providers: [
      KoinonFacade,
      KoinonAssistant,
      ...provideKoinonClient(new KoinonClient({ transport }), transport),
    ],
  });
  TestBed.inject(KoinonFacade).tenantId.set('tenant');
  const assistant = TestBed.inject(KoinonAssistant);
  await assistant.initialize();
  await assistant.send('Read sources');
  expect(assistant.messages()[0].tool_activities).toEqual([]);
  expect(assistant.activityLoading().size).toBe(0);
});

it.each([
  ['configured second agent', 'second', true, true, 'second'],
  ['missing organization default', null, false, false, ''],
  ['disabled organization default', 'second', true, false, ''],
  ['inaccessible organization default', 'missing', false, false, ''],
] as const)(
  'uses the organization chat setting without fallback: %s',
  async (_label, id, configured, canRun, expected) => {
    const reads: string[] = [];
    const transport: KoinonTransport = {
      request: async <T>(_method: HttpMethod, path: string) => {
        reads.push(path);
        return (
          path.endsWith('/chat/settings')
            ? {
                tenant_id: 'tenant',
                default_agent_id: id,
                revision: 7,
                configured,
                can_run: canRun,
                status: canRun ? 'ready' : id ? 'disabled' : 'unconfigured',
              }
            : path.endsWith('/agents')
              ? {
                  items: [
                    { id: 'first', status: 'ready', can_run: true },
                    { id: 'second', status: canRun ? 'ready' : 'disabled', can_run: canRun },
                  ],
                }
              : { items: [] }
        ) as T;
      },
      stream: () => {
        throw new Error('Unexpected stream');
      },
    };
    TestBed.configureTestingModule({
      providers: [
        KoinonFacade,
        KoinonAssistant,
        ...provideKoinonClient(new KoinonClient({ transport }), transport),
      ],
    });
    TestBed.inject(KoinonFacade).tenantId.set('tenant');
    const assistant = TestBed.inject(KoinonAssistant);
    await assistant.initialize();
    expect(assistant.agentId()).toBe(expected);
    expect(assistant.canUseAgent()).toBe(!!expected);
    expect(reads).toContain('/tenants/tenant/chat/settings');
  },
);

it('drops a previously selected organization agent when a fresh settings read is forbidden', async () => {
  let denied = false;
  const transport: KoinonTransport = {
    request: async <T>(_method: HttpMethod, path: string) => {
      if (path.endsWith('/chat/settings')) {
        if (denied) throw new KoinonError(403, 'DENIED', 'Chat configuration is inaccessible');
        return defaultChatSettings(path) as T;
      }
      return (
        path.endsWith('/agents') ? { items: [{ id: 'agent', status: 'ready' }] } : { items: [] }
      ) as T;
    },
    stream: () => {
      throw new Error('Unexpected stream');
    },
  };
  TestBed.configureTestingModule({
    providers: [
      KoinonFacade,
      KoinonAssistant,
      ...provideKoinonClient(new KoinonClient({ transport }), transport),
    ],
  });
  TestBed.inject(KoinonFacade).tenantId.set('tenant');
  const assistant = TestBed.inject(KoinonAssistant);
  await assistant.initialize();
  expect(assistant.agentId()).toBe('agent');
  denied = true;
  await assistant.initialize();
  expect(assistant.agentId()).toBe('');
  expect(assistant.canUseAgent()).toBe(false);
  expect(await assistant.send('Try the old agent')).toBe(false);
});

it('finds the configured organization agent beyond the first authorized agent page', async () => {
  const reads: RequestOptions['query'][] = [];
  const transport: KoinonTransport = {
    request: async <T>(_method: HttpMethod, path: string, options?: RequestOptions) => {
      if (path.endsWith('/chat/settings')) return defaultChatSettings(path, 'configured') as T;
      if (path.endsWith('/agents')) {
        reads.push(options?.query);
        return {
          items: [{ id: options?.query?.['page'] === 2 ? 'configured' : 'other', status: 'ready' }],
          page: options?.query?.['page'] ?? 1,
          pages: 2,
        } as T;
      }
      return { items: [] } as T;
    },
    stream: () => {
      throw new Error('Unexpected stream');
    },
  };
  TestBed.configureTestingModule({
    providers: [
      KoinonFacade,
      KoinonAssistant,
      ...provideKoinonClient(new KoinonClient({ transport }), transport),
    ],
  });
  const facade = TestBed.inject(KoinonFacade);
  facade.tenantId.set('tenant');
  facade.workspaceId.set('workspace');
  const assistant = TestBed.inject(KoinonAssistant);
  await assistant.initialize();
  expect(assistant.agentId()).toBe('configured');
  expect(assistant.canUseAgent()).toBe(true);
  expect(reads).toEqual([{ workspace_id: 'workspace' }, { workspace_id: 'workspace', page: 2 }]);
});
