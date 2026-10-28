// Copyright 2026 Firefly Software Foundation
// SPDX-License-Identifier: Apache-2.0
import { TestBed } from '@angular/core/testing';
import { signal } from '@angular/core';
import {
  KoinonClient,
  KoinonError,
  type KoinonTransport,
  type RequestOptions,
  type HttpMethod,
} from '@fireflyframework/koinon-sdk';
import { KoinonClientContext, KoinonFacade } from '@fireflyframework/koinon-angular';
import { KoinonKnowledgeArtifacts } from '../../../chat/page/src/services/knowledge-artifacts';
const review = {
  id: 'review',
  revision: 'a'.repeat(64),
  kind: 'conversation',
  format: 'json',
  title: 'Reviewed answer',
  message_count: 1,
  source_count: 0,
  completeness: 'selected_messages',
  messages: [
    {
      id: 'm',
      role: 'assistant',
      text: 'Actual selected text',
      status: 'completed',
      revision: 'b'.repeat(64),
    },
  ],
  sources: [],
  source_manifest_complete: true,
  expires_at: '2099-01-01T00:00:00Z',
};
function setup(request: KoinonTransport['request']) {
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
    permissions: signal(
      new Set(['exports:read', 'exports:write', 'shares:read', 'shares:write', 'evidence:read']),
    ),
  };
  const clients = { revision: signal(0), get: () => new KoinonClient({ transport }) };
  TestBed.configureTestingModule({
    providers: [
      KoinonKnowledgeArtifacts,
      { provide: KoinonFacade, useValue: facade },
      { provide: KoinonClientContext, useValue: clients },
    ],
  });
  return { state: TestBed.inject(KoinonKnowledgeArtifacts), facade, clients };
}
it('reviews exact selected content without creating an export automatically', async () => {
  const calls: { method: HttpMethod; path: string; options: RequestOptions }[] = [];
  const { state } = setup(
    async <T>(method: HttpMethod, path: string, options: RequestOptions = {}) => {
      calls.push({ method, path, options });
      return review as T;
    },
  );
  await state.reviewExport({
    kind: 'conversation',
    thread_id: 'thread',
    message_ids: ['m'],
    format: 'json',
    include_evidence: true,
  });
  expect(calls).toHaveLength(1);
  expect(calls[0].path).toBe('/tenants/north/exports/reviews');
  expect(calls[0].options.body).toMatchObject({ message_ids: ['m'], format: 'json' });
  expect(state.exportRecord()).toBeNull();
  expect(state.exportReview()?.messages?.[0].text).toBe('Actual selected text');
});
it('refuses a review that does not include the actual selected messages', async () => {
  const { state } = setup(async <T>() => ({ ...review, messages: [] }) as T);
  expect(
    await state.reviewExport({
      kind: 'conversation',
      thread_id: 'thread',
      message_ids: ['m'],
      format: 'json',
    }),
  ).toBeNull();
  expect(state.exportReview()).toBeNull();
  expect(state.error()).toContain('selected');
});
it('ignores in-flight reviews after the context changes', async () => {
  let finish!: (value: unknown) => void;
  const { state, facade } = setup(
    <T>() =>
      new Promise<T>((resolve) => {
        finish = (value) => resolve(value as T);
      }),
  );
  const pending = state.reviewExport({
    kind: 'conversation',
    thread_id: 'thread',
    message_ids: ['m'],
    format: 'json',
  });
  facade.tenantId.set('south');
  TestBed.tick();
  finish(review);
  await pending;
  expect(state.exportReview()).toBeNull();
  expect(state.pending()).toBe(false);
});
it('propagates expired authentication but preserves a permission denial as an error', async () => {
  let status = 403;
  const { state, facade } = setup(async () => {
    throw new KoinonError(status, 'DENIED', 'Permission required');
  });
  await state.sources({ thread_id: 'thread', message_ids: ['m'] });
  expect(facade.authRequired()).toBe(false);
  expect(state.error()).toBe('Permission required');
  status = 401;
  await state.sources({ thread_id: 'thread', message_ids: ['m'] });
  expect(facade.authRequired()).toBe(true);
});
it('discards a review after same-subject context refresh even when visible scope strings match', async () => {
  let finish!: (value: unknown) => void;
  const { state, facade } = setup(
    <T>() =>
      new Promise<T>((resolve) => {
        finish = (value) => resolve(value as T);
      }),
  );
  const pending = state.reviewExport({
    kind: 'conversation',
    thread_id: 'thread',
    message_ids: ['m'],
    format: 'json',
  });
  facade.context.set({ ...facade.context() });
  finish(review);
  await pending;
  expect(state.exportReview()).toBeNull();
});
