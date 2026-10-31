// Copyright 2026 Firefly Software Foundation
// SPDX-License-Identifier: Apache-2.0
import { TestBed } from '@angular/core/testing';
import { signal } from '@angular/core';
import { KoinonClient, type HttpMethod, type KnowledgeIntent, type KnowledgeIntentInput, type KoinonTransport, type RequestOptions } from '@fireflyframework/koinon-sdk';
import { KoinonClientContext, KoinonFacade } from '@fireflyframework/koinon-angular';
import { KoinonKnowledgeReview } from '../../../../chat/page/src/artifacts/knowledge-review';
const hash = 'b'.repeat(64), text = 'The reviewed threshold is 47.';
const entry = (id: string, kind: string, parent_id: string | null) => ({ id, kind, parent_id, tenant_id: 'north', name: id, status: 'ready', workspace_id: 'workspace', project_id: 'project' });
async function mount() {
  const calls: { method: HttpMethod; path: string; options: RequestOptions }[] = [];
  let review: KnowledgeIntent | null = null;
  const transport: KoinonTransport = {
    request: async <T>(method: HttpMethod, path: string, options: RequestOptions = {}) => {
      calls.push({ method, path, options });
      if (path.endsWith('/knowledge-intents')) {
        const input = options.body as KnowledgeIntentInput;
        review = { id: 'review-' + calls.length, revision: 1, tenant_id: 'north', owner_subject: 'owner', action: input.action,
          target_item_id: 'knowledge', destination: { id: 'folder', workspace_id: 'workspace', project_id: 'project', name: 'Reviewed policies', ancestry_digest: hash },
          before: null, after: input.content, authorization_digest: hash, remembered_context_present: true,
          evidence: [{ kind: 'document_passage', basis: 'remembered_context', source: { id: 'source', asset_id: 'document', kind: 'document', title: 'Operating policy', quote: text, source_part_id: 'immutable-part', used_revision: 'source-part-sha256:' + hash } }],
          status: 'preview', created_at: '2026-10-31T00:00:00Z', expires_at: '2099-01-01T00:00:00Z' };
        return review as T;
      }
      if (path.endsWith('/cancel')) return { ...review, revision: 2, status: 'cancelled' } as T;
      if (path.endsWith('/confirm') && review) return { status: 'committed', receipt: {
        operation_id: 'operation', intent_id: review.id, intent_revision: review.revision, authorization_digest: hash,
        item_id: 'knowledge', native_item_id: 'native-item', native_version_id: 'native-version', version: 1,
        serving_version: review.action === 'create_published' ? 1 : null, action: review.action,
        content_sha256: hash, evidence_sha256: hash, committed_at: '2026-10-31T00:00:00Z', retrieval_state: 'not_published',
      } } as T;
      throw Error('Unexpected request: ' + path);
    },
    stream: () => { throw Error('Unexpected stream'); },
  };
  const rows = [entry('workspace', 'workspace', null), entry('project', 'project', 'workspace'), entry('folder', 'collection', 'project')];
  const facade = {
    context: signal({ subject: 'owner', workspaces: [rows[0]] }), tenantId: signal('north'), workspaceId: signal('workspace'), projectId: signal('project'), parentId: signal('folder'),
    entries: signal(rows), authRequired: signal(false), permissions: signal(new Set(['chat:use', 'catalog:read', 'catalog:write', 'ingest:write'])),
    loadChildren: async (id: string) => ({ ids: rows.filter((row) => (row.parent_id ?? '') === id).map((row) => row.id), page: 1, pages: 1 }),
  };
  const client = new KoinonClient({ transport });
  TestBed.configureTestingModule({ imports: [KoinonKnowledgeReview], providers: [
    { provide: KoinonFacade, useValue: facade }, { provide: KoinonClientContext, useValue: { revision: signal(0), get: () => client } },
  ] });
  const fixture = TestBed.createComponent(KoinonKnowledgeReview);
  fixture.componentRef.setInput('open', true);
  fixture.componentRef.setInput('selection', { thread_id: 'thread', message_ids: ['answer'] });
  fixture.componentRef.setInput('message', { id: 'answer', role: 'assistant', status: 'completed', text, created_at: '2026-10-31T00:00:00Z', citations: [], artifacts: [] });
  fixture.detectChanges(); await fixture.whenStable(); fixture.detectChanges();
  const button = (label: string) => [...(fixture.nativeElement as HTMLElement).querySelectorAll<HTMLButtonElement>('button')].find((row) => row.textContent?.trim() === label)!;
  const setTitle = () => {
    const title = (fixture.nativeElement as HTMLElement).querySelector<HTMLInputElement>('input[name="knowledgeTitle"]')!;
    title.value = 'Reviewed threshold'; title.dispatchEvent(new Event('input'));
  };
  return { fixture, calls, facade, button, setTitle };
}

it('requires server review and a separate checkbox-backed confirmation for the selected answer', async () => {
  const { fixture, calls, button, setTitle } = await mount();
  expect(calls).toHaveLength(0);
  expect(fixture.nativeElement.querySelector('textarea').value).toBe(text);
  expect(fixture.nativeElement.querySelector('select').value).toBe('draft');
  setTitle(); fixture.detectChanges(); await fixture.whenStable(); fixture.detectChanges();
  button('Review proposal').click(); await fixture.whenStable(); fixture.detectChanges();
  expect(calls).toHaveLength(1);
  expect(calls[0].options.body).toMatchObject({ action: 'create_draft', origin: { kind: 'conversation', thread_id: 'thread', message_ids: ['answer'] } });
  expect(fixture.nativeElement.textContent).toContain('No existing knowledge item');
  expect(fixture.nativeElement.textContent).toContain('Remembered supporting context');
  expect(button('Confirm and save draft').disabled).toBe(true);
  const consent = (fixture.nativeElement as HTMLElement).querySelector<HTMLInputElement>('input[type="checkbox"]')!;
  expect(consent.checked).toBe(false); consent.click();
  await fixture.whenStable(); fixture.detectChanges();
  button('Confirm and save draft').click(); await fixture.whenStable(); fixture.detectChanges();
  expect(calls.at(-1)?.options.body).toEqual({ confirm: true, expected_revision: 1, authorization_digest: hash, include_remembered_context: true });
  expect(fixture.nativeElement.textContent).toContain('Your draft was saved');
});

it('resets consent when editing and cancels only through the reviewed server revision', async () => {
  const { fixture, calls, button, setTitle } = await mount();
  setTitle(); await fixture.whenStable(); fixture.detectChanges();
  button('Review proposal').click(); await fixture.whenStable(); fixture.detectChanges();
  (fixture.nativeElement as HTMLElement).querySelector<HTMLInputElement>('input[type="checkbox"]')!.click();
  await fixture.whenStable(); fixture.detectChanges();
  button('Edit proposal').click(); await fixture.whenStable(); fixture.detectChanges();
  expect(fixture.componentInstance.s.consent()).toBe(false);
  expect(fixture.nativeElement.querySelector('input[type="checkbox"]')).toBeNull();
  button('Review proposal').click(); await fixture.whenStable(); fixture.detectChanges();
  expect(button('Confirm and save draft').disabled).toBe(true);
  button('Cancel proposal').click(); await fixture.whenStable(); fixture.detectChanges();
  expect(calls.at(-1)?.path).toMatch(/\/cancel$/);
  expect(calls.at(-1)?.options.body).toEqual({ expected_revision: 1 });
  expect(calls.some((call) => call.path.endsWith('/confirm'))).toBe(false);
  expect(fixture.nativeElement.textContent).toContain('No knowledge was saved');
});

it('clears private proposal state and closes when the organization context is replaced', async () => {
  const { fixture, facade, button, setTitle } = await mount();
  const closed = vi.fn(); fixture.componentInstance.closed.subscribe(closed);
  setTitle(); await fixture.whenStable(); fixture.detectChanges();
  button('Review proposal').click(); await fixture.whenStable(); fixture.detectChanges();
  facade.context.set({ subject: 'another-owner', workspaces: [] });
  fixture.detectChanges(); await fixture.whenStable(); fixture.detectChanges();
  expect(closed).toHaveBeenCalled();
  expect(fixture.componentInstance.s.intent()).toBeNull();
  expect(fixture.componentInstance.s.body()).toBe('');
  expect(fixture.componentInstance.s.consent()).toBe(false);
});
