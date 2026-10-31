// Copyright 2026 Firefly Software Foundation
// SPDX-License-Identifier: Apache-2.0
import { TestBed } from '@angular/core/testing';
import { signal } from '@angular/core';
import { KoinonClientContext, KoinonFacade } from '@fireflyframework/koinon-angular';
import { KoinonClient, KoinonError, type HttpMethod, type KnowledgeIntent, type KnowledgeCommitReceipt, type KoinonTransport, type RequestOptions } from '@fireflyframework/koinon-sdk';
import { KoinonKnowledgeIntents } from '../../../../chat/page/src/services/knowledge-intents';

const digest = 'a'.repeat(64);
const text = 'The reviewed threshold is 47.';
const selection = { thread_id: 'selected-thread', message_ids: ['selected-answer'] };
const reviewed = (changes: Partial<KnowledgeIntent> = {}): KnowledgeIntent => ({
  id: 'intent', revision: 1, tenant_id: 'north', owner_subject: 'owner', action: 'create_draft',
  target_item_id: 'new-knowledge', destination: { id: 'folder', workspace_id: 'w', project_id: 'p', name: 'Reviewed policies', ancestry_digest: digest },
  before: null, after: { title: 'Reviewed threshold', body: text },
  evidence: [{ kind: 'document_passage', source: { id: 'source', asset_id: 'document', kind: 'document', title: 'Operating policy', quote: text, source_part_id: 'immutable-part', used_revision: 'source-part-sha256:' + digest } }],
  authorization_digest: digest, status: 'preview', created_at: '2026-10-31T00:00:00Z', expires_at: '2099-01-01T00:00:00Z', ...changes,
});
const receipt = (changes: Partial<KnowledgeCommitReceipt> = {}): KnowledgeCommitReceipt => ({
  operation_id: 'operation', intent_id: 'intent', intent_revision: 1, authorization_digest: digest,
  item_id: 'new-knowledge', native_item_id: 'native-item', native_version_id: 'native-version',
  version: 1, serving_version: null, action: 'create_draft', content_sha256: digest, evidence_sha256: digest,
  committed_at: '2026-10-31T00:00:00Z', retrieval_state: 'not_published', ...changes,
});
interface Call { method: HttpMethod; path: string; options: RequestOptions }
function setup(handler?: (call: Call) => Promise<unknown>) {
  const calls: Call[] = [];
  const transport: KoinonTransport = {
    request: async <T>(method: HttpMethod, path: string, options: RequestOptions = {}) => {
      const call = { method, path, options }; calls.push(call);
      return (handler ? await handler(call) : path.endsWith('/confirm')
        ? { status: 'committed', receipt: receipt() } : reviewed()) as T;
    },
    stream: () => { throw Error('Unexpected stream'); },
  };
  const facade = {
    context: signal({ subject: 'owner' }), tenantId: signal('north'), workspaceId: signal('w'),
    projectId: signal('p'), parentId: signal('folder'), authRequired: signal(false),
    entries: signal([{ id: 'folder', kind: 'collection', name: 'Reviewed policies', status: 'ready' }]),
    permissions: signal(new Set(['chat:use', 'catalog:read', 'catalog:write', 'ingest:write'])),
  };
  const revision = signal(0), client = new KoinonClient({ transport });
  TestBed.configureTestingModule({ providers: [KoinonKnowledgeIntents,
    { provide: KoinonFacade, useValue: facade },
    { provide: KoinonClientContext, useValue: { revision, get: () => client } },
  ] });
  const state = TestBed.inject(KoinonKnowledgeIntents);
  TestBed.tick();
  state.configure(selection, text);
  state.title.set('Reviewed threshold');
  return { state, facade, calls, revision };
}

it('uses the typed preview then a separate exact confirmation, defaulting to draft', async () => {
  const { state, calls } = setup();
  expect(state.publication()).toBe('draft');
  expect(calls).toHaveLength(0);
  await state.preview();
  expect(calls).toHaveLength(1);
  expect(calls[0]).toMatchObject({ method: 'POST', path: '/tenants/north/knowledge-intents', options: { body: {
    action: 'create_draft', destination_id: 'folder', content: { title: 'Reviewed threshold', body: text },
    origin: { kind: 'conversation', ...selection },
  } } });
  expect(calls[0].options.body).not.toHaveProperty('include_remembered_context');
  expect(state.stage()).toBe('review');
  await state.confirm();
  expect(calls[1].options.body).toEqual({ confirm: true, expected_revision: 1, authorization_digest: digest });
  expect(calls[1].options.headers?.['Idempotency-Key']).toBeTruthy();
  expect(state.stage()).toBe('saved');
  expect(state.receipt()?.retrieval_state).toBe('not_published');
});

it('requires unchecked remembered-context consent and resets it for each edited preview', async () => {
  const { state, calls } = setup(async (call) => call.path.endsWith('/confirm') ? { status: 'committed', receipt: receipt() } : reviewed({ remembered_context_present: true }));
  await state.preview();
  expect(state.consent()).toBe(false);
  expect(state.canConfirm()).toBe(false);
  await state.confirm();
  expect(calls).toHaveLength(1);
  state.consent.set(true);
  state.edit();
  expect(state.intent()).toBeNull();
  expect(state.consent()).toBe(false);
  await state.preview();
  expect(state.canConfirm()).toBe(false);
  state.consent.set(true);
  await state.confirm();
  expect(calls.at(-1)?.path).toMatch(/\/confirm$/);
  expect(calls.at(-1)?.options.body).toMatchObject({ include_remembered_context: true, confirm: true });
  expect(calls.filter((call) => !call.path.endsWith('/confirm')).every((call) =>
    !Object.hasOwn(call.options.body as object, 'include_remembered_context'))).toBe(true);
});

it('publishes only after the explicit published preview and its separate confirmation', async () => {
  const { state, calls } = setup(async (call) => call.path.endsWith('/confirm')
    ? { status: 'committed', receipt: receipt({ action: 'create_published', serving_version: 1, retrieval_state: 'lexical_ready' }) }
    : reviewed({ action: 'create_published' }));
  state.publication.set('published');
  await state.preview();
  expect(calls).toHaveLength(1);
  expect(calls[0].options.body).toMatchObject({ action: 'create_published' });
  expect(state.receipt()).toBeNull();
  await state.confirm();
  expect(state.stage()).toBe('saved');
  expect(state.receipt()?.serving_version).toBe(1);
});

it('shows pending outcomes, resumes the same selection and checks status with GET only', async () => {
  const { state, calls } = setup(async (call) => call.path.endsWith('/confirm')
    ? { status: 'pending', operation_id: 'operation', intent_id: 'intent' }
    : call.method === 'GET' ? reviewed({ status: 'committed', receipt: receipt() }) : reviewed());
  await state.preview(); await state.confirm();
  expect(state.stage()).toBe('pending');
  expect(state.canPreview()).toBe(false);
  state.suspend(); state.configure(selection, text);
  expect(state.stage()).toBe('pending');
  await state.confirm();
  expect(calls.filter((call) => call.path.endsWith('/confirm'))).toHaveLength(1);
  await state.refresh();
  expect(calls.at(-1)?.method).toBe('GET');
  expect(state.stage()).toBe('saved');
});

it('retains the confirmation key after an unknown outcome and requires a fresh consent decision', async () => {
  let attempts = 0;
  const { state, calls } = setup(async (call) => {
    if (call.path.endsWith('/confirm')) {
      if (++attempts === 1) throw Error('Connection interrupted');
      return { status: 'committed', receipt: receipt() };
    }
    return reviewed({ remembered_context_present: true });
  });
  await state.preview(); state.consent.set(true); await state.confirm();
  const key = calls.at(-1)?.options.headers?.['Idempotency-Key'];
  expect(state.stage()).toBe('pending');
  expect(state.consent()).toBe(false);
  await state.refresh();
  expect(state.stage()).toBe('review'); expect(state.canConfirm()).toBe(false);
  state.consent.set(true); await state.confirm();
  expect(calls.at(-1)?.options.headers?.['Idempotency-Key']).toBe(key);
  expect(state.stage()).toBe('saved');
});

it('invalidates a conflicting review and never retries confirmation automatically', async () => {
  const { state, calls } = setup(async (call) => {
    if (call.path.endsWith('/confirm')) throw new KoinonError(409, 'KNOWLEDGE_INTENT_CONFLICT', 'Changed');
    return reviewed({ remembered_context_present: true });
  });
  await state.preview(); state.consent.set(true); await state.confirm();
  expect(state.intent()).toBeNull(); expect(state.consent()).toBe(false);
  expect(state.stage()).toBe('edit'); expect(state.error()).toContain('Review the proposal again');
  await state.confirm(); expect(calls).toHaveLength(2);
});

it('cancels the exact reviewed revision without a confirmation request', async () => {
  const { state, calls } = setup(async (call) => call.path.endsWith('/cancel')
    ? reviewed({ revision: 2, status: 'cancelled' }) : reviewed());
  await state.preview(); await state.cancel();
  expect(calls.at(-1)?.options.body).toEqual({ expected_revision: 1 });
  expect(state.stage()).toBe('cancelled');
  expect(calls.some((call) => call.path.endsWith('/confirm'))).toBe(false);
});

it('aborts and ignores a late private preview after a client or context change', async () => {
  let finish!: (value: KnowledgeIntent) => void;
  const { state, facade, calls } = setup(() => new Promise((resolve) => { finish = resolve; }));
  const request = state.preview();
  facade.tenantId.set('south'); TestBed.tick();
  expect(calls[0].options.signal?.aborted).toBe(true);
  finish(reviewed()); await request;
  expect(state.intent()).toBeNull(); expect(state.body()).toBe(''); expect(state.pending()).toBe(false);
});

it('does not confirm expired previews', async () => {
  const { state, calls } = setup(async () => reviewed({ expires_at: '2020-01-01T00:00:00Z' }));
  await state.preview(); await state.confirm();
  expect(calls).toHaveLength(1); expect(state.intent()).toBeNull();
});

it('rejects mismatched preview ownership before enabling confirmation', async () => {
  const { state } = setup(async () => reviewed({ owner_subject: 'another-owner' }));
  await state.preview();
  expect(state.intent()).toBeNull(); expect(state.canConfirm()).toBe(false);
});

it('keeps an unverified receipt pending instead of announcing a successful save', async () => {
  const { state } = setup(async (call) => call.path.endsWith('/confirm')
    ? { status: 'committed', receipt: receipt({ intent_id: 'another-intent' }) } : reviewed());
  await state.preview(); await state.confirm();
  expect(state.stage()).toBe('pending'); expect(state.receipt()).toBeNull();
  expect(state.error()).toContain('Check its status');
});

it('preserves the authored form when the server denies preview for a destination', async () => {
  const { state } = setup(async () => { throw new KoinonError(403, 'ACCESS_DENIED', 'Destination denied'); });
  await state.preview();
  expect(state.stage()).toBe('edit'); expect(state.title()).toBe('Reviewed threshold');
  expect(state.body()).toBe(text); expect(state.destination()).toBe('folder');
  expect(state.error()).toContain('Check your organization and permissions');
});

it('discards a late confirmation receipt after switching to another selected reply', async () => {
  let finish!: (value: unknown) => void;
  const { state, calls } = setup(async (call) => call.path.endsWith('/confirm')
    ? new Promise((resolve) => { finish = resolve; }) : reviewed());
  await state.preview(); const request = state.confirm();
  state.configure({ thread_id: 'other-thread', message_ids: ['other-answer'] }, 'Another selected answer');
  expect(calls.at(-1)?.options.signal?.aborted).toBe(true);
  finish({ status: 'committed', receipt: receipt() }); await request;
  expect(state.receipt()).toBeNull(); expect(state.stage()).toBe('edit');
  expect(state.body()).toBe('Another selected answer'); expect(state.consent()).toBe(false);
});

it('resets the private review when the bound SDK credential revision changes', async () => {
  const { state, revision } = setup();
  await state.preview(); revision.update((value) => value + 1); TestBed.tick();
  expect(state.intent()).toBeNull(); expect(state.body()).toBe(''); expect(state.canConfirm()).toBe(false);
});
