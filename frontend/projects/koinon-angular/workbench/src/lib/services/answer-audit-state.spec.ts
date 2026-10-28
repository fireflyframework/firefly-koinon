// Copyright 2026 Firefly Software Foundation
// SPDX-License-Identifier: Apache-2.0
import { TestBed } from '@angular/core/testing';
import { signal } from '@angular/core';
import {
  KoinonClient,
  KoinonError,
  type AnswerAudit,
  type ChatMessage,
  type KoinonTransport,
  type HttpMethod,
  type RequestOptions,
} from '@fireflyframework/koinon-sdk';
import { KoinonClientContext, KoinonFacade } from '@fireflyframework/koinon-angular';
import { KoinonAnswerAuditState } from '../../../../chat/page/src/artifacts/answer-audit-state';
const emptyAudit: AnswerAudit = {
  run_id: 'run',
  provenance_status: 'not_recorded',
  source_provenance_complete: null,
  generations: [],
  sources: [],
  private_files: [],
  native_reads: [],
  sql_attempts: [],
};
const message: ChatMessage = {
  id: 'answer',
  run_id: 'run',
  role: 'assistant',
  text: 'Saved answer',
  status: 'completed',
  citations: [],
  artifacts: [],
  created_at: '2026-10-27T10:00:00Z',
};
function setup(request: KoinonTransport['request'], evidence = true) {
  const transport: KoinonTransport = {
    request,
    stream: () => {
      throw Error('Unexpected stream');
    },
  };
  const facade = {
    context: signal({ subject: 'owner' }),
    tenantId: signal('north'),
    workspaceId: signal('w'),
    projectId: signal('p'),
    authRequired: signal(false),
    permissions: signal(new Set(evidence ? ['chat:use', 'evidence:read'] : ['chat:use'])),
  };
  TestBed.configureTestingModule({
    providers: [
      KoinonAnswerAuditState,
      { provide: KoinonFacade, useValue: facade },
      {
        provide: KoinonClientContext,
        useValue: { revision: signal(0), get: () => new KoinonClient({ transport }) },
      },
    ],
  });
  return { state: TestBed.inject(KoinonAnswerAuditState), facade };
}
it('loads observed server pages25 and source metadata without resolving any result until selected', async () => {
  const calls: { path: string; options: RequestOptions }[] = [];
  const { state } = setup(
    async <T>(_method: HttpMethod, path: string, options: RequestOptions = {}) => {
      calls.push({ path, options });
      if (path.endsWith('/audit')) return emptyAudit as T;
      if (path.endsWith('/activity'))
        return {
          items: [
            {
              call_id: 'call',
              tool_name: 'query_dataset',
              status: 'completed',
              occurred_at: message.created_at,
              summary: 'Read recorded rows',
              result_id: 'result',
            },
          ],
          total: 26,
          page: options.query?.['page'],
          page_size: 25,
          pages: 2,
        } as T;
      if (path.endsWith('/results/result'))
        return {
          id: 'result',
          run_id: 'run',
          kind: 'query',
          data: {
            query_id: 'q',
            execution_status: 'OK',
            row_count: 137,
            preview: [{ id: 1 }],
            truncated: true,
            sql: 'SELECT id FROM recorded_table',
          },
        } as T;
      return { revision: 'a'.repeat(64), sources: [], complete: false, omissions: [] } as T;
    },
  );
  await state.open('thread', message);
  expect(calls.find((row) => row.path.endsWith('/activity'))?.options.query).toEqual({
    page: 1,
    page_size: 25,
  });
  expect(calls.some((row) => row.path.includes('/results/'))).toBe(false);
  await state.loadActivity(2);
  expect(state.activity()?.page).toBe(2);
  state.selectResult(state.activity()!.items[0]);
  expect(calls.some((row) => row.path.includes('/results/'))).toBe(false);
  await state.resolve('run', 'result');
  expect(state.result()?.kind).toBe('query');
  expect(calls.filter((row) => row.path.includes('/results/'))).toHaveLength(1);
});
it('does not fabricate a trace or fetch protected metadata for a legacy answer without a run', async () => {
  let calls = 0;
  const { state } = setup(async <T>() => {
    calls++;
    return {} as T;
  }, false);
  const legacy = { ...message, run_id: undefined };
  await state.open('thread', legacy);
  expect(calls).toBe(0);
  expect(state.activity()).toBeNull();
  expect(state.manifest()).toBeNull();
});
it('discards activity and source responses after a same-subject context object refresh', async () => {
  let finish!: (value: unknown) => void;
  const { state, facade } = setup(<T>(_method: HttpMethod, path: string) =>
    path.endsWith('/activity')
      ? new Promise<T>((resolve) => {
          finish = (value) => resolve(value as T);
        })
      : Promise.resolve({ revision: 'a'.repeat(64), sources: [], complete: false } as T),
  );
  const pending = state.open('thread', message);
  facade.context.set({ ...facade.context() });
  finish({ items: [], page: 1, page_size: 25, total: 0, pages: 0 });
  await pending;
  expect(state.activity()).toBeNull();
  expect(state.manifest()).toBeNull();
});
it('drops a deferred tool result after a same-subject credential context refresh', async () => {
  let finish!: (value: unknown) => void;
  const { state, facade } = setup(async <T>(_method: HttpMethod, path: string) => {
    if (path.endsWith('/audit')) return emptyAudit as T;
    if (path.endsWith('/activity'))
      return {
        items: [
          {
            call_id: 'call',
            tool_name: 'query_dataset',
            status: 'completed',
            occurred_at: message.created_at,
            summary: 'Recorded query',
            result_id: 'result',
          },
        ],
        total: 1,
        page: 1,
        page_size: 25,
        pages: 1,
      } as T;
    return new Promise<T>((resolve) => {
      finish = (value) => resolve(value as T);
    });
  }, false);
  await state.open('thread', message);
  state.selectResult(state.activity()!.items[0]);
  const pending = state.resolve('run', 'result');
  const rejected = expect(pending).rejects.toMatchObject({ name: 'AbortError' });
  facade.context.set({ ...facade.context() });
  finish({
    id: 'result',
    run_id: 'run',
    kind: 'query',
    data: { query_id: 'q', execution_status: 'OK', preview: [] },
  });
  await rejected;
  expect(state.result()).toBeNull();
  expect(state.resultError()).toBe('');
});
it('rejects unobserved result identifiers before making any result request', async () => {
  let requests = 0;
  const { state } = setup(async <T>() => {
    requests++;
    return { items: [], total: 0, page: 1, page_size: 25, pages: 0 } as T;
  }, false);
  await state.open('thread', message);
  await expect(state.resolve('run', 'invented')).rejects.toThrow('Select a recorded tool result');
  expect(requests).toBe(2);
});

for (const code of [401, 403])
  it(`propagates ${code} without confusing denied access with an expired session`, async () => {
    const { state, facade } = setup(async () => {
      throw new KoinonError(code, 'ACCESS_DENIED', 'The request is unavailable.');
    }, false);
    await state.open('thread', message);
    expect(facade.authRequired()).toBe(code === 401);
    expect(state.activity()).toBeNull();
    expect(state.activityError() || state.auditError()).toBeTruthy();
  });
it('requests essential owner provenance with chat access and without broader evidence permission', async () => {
  const paths: string[] = [];
  const { state } = setup(async <T>(_method: HttpMethod, path: string) => {
    paths.push(path);
    if (path.endsWith('/audit'))
      return {
        run_id: 'run',
        provenance_status: 'recorded',
        source_provenance_complete: true,
        generations: [],
        sources: [],
        private_files: [],
        native_reads: [],
        sql_attempts: [],
      } as T;
    return { items: [], total: 0, page: 1, page_size: 25, pages: 0 } as T;
  }, false);
  await state.open('thread', message);
  expect(paths).toContain('/tenants/north/chat/runs/run/audit');
  expect(paths.some((path) => path.includes('/evidence/') || path.includes('/configuration'))).toBe(
    false,
  );
});
it('discards a pending owner receipt after a same-subject context refresh', async () => {
  let finish!: (value: AnswerAudit) => void;
  const { state, facade } = setup(
    <T>(_method: HttpMethod, path: string) =>
      path.endsWith('/audit')
        ? new Promise<T>((resolve) => {
            finish = (value) => resolve(value as T);
          })
        : Promise.resolve({ items: [], total: 0, page: 1, page_size: 25, pages: 0 } as T),
    false,
  );
  const pending = state.open('thread', message);
  facade.context.set({ ...facade.context() });
  finish(emptyAudit);
  await pending;
  expect(state.audit()).toBeNull();
  expect(state.sources()).toEqual([]);
});
it('rejects owner receipts from a different run without substituting current settings', async () => {
  const paths: string[] = [];
  const { state } = setup(async <T>(_method: HttpMethod, path: string) => {
    paths.push(path);
    return (
      path.endsWith('/audit')
        ? { ...emptyAudit, run_id: 'foreign' }
        : { items: [], total: 0, page: 1, page_size: 25, pages: 0 }
    ) as T;
  }, false);
  await state.open('thread', message);
  expect(state.audit()).toBeNull();
  expect(state.auditError()).toContain('incomplete');
  expect(paths.some((path) => path.includes('/configuration'))).toBe(false);
});
it('opens a run audit with only GET requests even when broader evidence access is granted', async () => {
  const calls: { method: HttpMethod; path: string; body: unknown }[] = [];
  const { state } = setup(
    async <T>(method: HttpMethod, path: string, options: RequestOptions = {}) => {
      calls.push({ method, path, body: options.body });
      return (
        path.endsWith('/audit')
          ? emptyAudit
          : path.endsWith('/activity')
            ? { items: [], total: 0, page: 1, page_size: 25, pages: 0 }
            : { revision: 'a'.repeat(64), sources: [], complete: true }
      ) as T;
    },
  );
  await state.open('thread', message);
  await state.loadManifest();
  expect(calls).toEqual([
    { method: 'GET', path: '/tenants/north/chat/runs/run/audit', body: undefined },
    { method: 'GET', path: '/tenants/north/chat/runs/run/activity', body: undefined },
  ]);
  expect(state.manifest()).toBeNull();
});
it('does not fall back to broader evidence after an owner-audit403 or an explicit source retry', async () => {
  const paths: string[] = [];
  const { state, facade } = setup(async <T>(_method: HttpMethod, path: string) => {
    paths.push(path);
    if (path.endsWith('/audit')) throw new KoinonError(403, 'FORBIDDEN', 'Owner audit denied');
    return { items: [], total: 0, page: 1, page_size: 25, pages: 0 } as T;
  });
  await state.open('thread', message);
  await state.loadManifest();
  expect(paths.some((path) => path.includes('/evidence/'))).toBe(false);
  expect(state.sources()).toEqual([]);
  expect(state.manifest()).toBeNull();
  expect(state.auditError()).toBe('Owner audit denied');
  expect(facade.authRequired()).toBe(false);
});
it('keeps the scoped legacy manifest request only for a record without a run identifier', async () => {
  const calls: { method: HttpMethod; path: string; body: unknown }[] = [];
  const { state } = setup(
    async <T>(method: HttpMethod, path: string, options: RequestOptions = {}) => {
      calls.push({ method, path, body: options.body });
      return { revision: 'a'.repeat(64), sources: [], complete: false } as T;
    },
  );
  await state.open('thread', { ...message, run_id: undefined });
  expect(calls).toEqual([
    {
      method: 'POST',
      path: '/tenants/north/evidence/conversations',
      body: { thread_id: 'thread', message_ids: ['answer'] },
    },
  ]);
  expect(state.audit()).toBeNull();
});
it('discards a deferred legacy manifest after the same subject receives a new context object', async () => {
  let finish!: (value: unknown) => void;
  const { state, facade } = setup(
    <T>() =>
      new Promise<T>((resolve) => {
        finish = (value) => resolve(value as T);
      }),
  );
  const pending = state.open('thread', { ...message, run_id: undefined });
  facade.context.set({ ...facade.context() });
  finish({
    revision: 'a'.repeat(64),
    sources: [
      { id: 'old-source', asset_id: 'document', title: 'Historical source', kind: 'document' },
    ],
    complete: false,
  });
  await pending;
  expect(state.manifest()).toBeNull();
  expect(state.sources()).toEqual([]);
});
it('does not retain an earlier legacy source authority when the next owner audit is denied', async () => {
  let legacyReads = 0;
  const { state } = setup(async <T>(_method: HttpMethod, path: string) => {
    if (path.includes('/evidence/')) {
      legacyReads++;
      return {
        revision: 'a'.repeat(64),
        sources: [
          { id: 'old-source', asset_id: 'document', title: 'Historical source', kind: 'document' },
        ],
        complete: false,
      } as T;
    }
    if (path.endsWith('/audit')) throw new KoinonError(403, 'FORBIDDEN', 'Owner audit denied');
    return { items: [], total: 0, page: 1, page_size: 25, pages: 0 } as T;
  });
  await state.open('thread', { ...message, run_id: undefined });
  expect(state.sources()[0]?.title).toBe('Historical source');
  await state.open('thread', message);
  expect(state.sources()).toEqual([]);
  expect(state.manifest()).toBeNull();
  expect(legacyReads).toBe(1);
});
