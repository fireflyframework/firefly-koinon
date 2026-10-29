// Copyright 2026 Firefly Software Foundation
// SPDX-License-Identifier: Apache-2.0
import { signal } from '@angular/core';
import { TestBed } from '@angular/core/testing';
import {
  KoinonClient,
  type KoinonTransport,
  type HttpMethod,
  type ChatMessage,
} from '@fireflyframework/koinon-sdk';
import { KoinonClientContext, KoinonFacade } from '@fireflyframework/koinon-angular';
import { KoinonAnswerAudit } from '../../../../chat/page/src/artifacts/answer-audit';
const source = {
  id: 'source',
  asset_id: 'document',
  kind: 'document',
  title: 'Recorded policy',
  quote: 'Recorded source passage.',
  availability: 'available',
};
const file = {
  id: 'private',
  filename: 'Recorded notes.txt',
  media_type: 'text/plain',
  sha256: 'a'.repeat(64),
  used_revision: 1,
  availability: 'available',
};
const message: ChatMessage = {
  id: 'answer',
  run_id: 'run',
  role: 'assistant',
  status: 'completed',
  text: 'Recorded answer',
  citations: [],
  artifacts: [],
  created_at: '2026-10-29T10:00:00Z',
};
const receipt = (sources = [] as object[], private_files = [] as object[]) => ({
  run_id: 'run',
  provenance_status: 'recorded',
  source_provenance_complete: true,
  sources,
  private_files,
  native_reads: [],
  sql_attempts: [],
});
async function setup(value: ReturnType<typeof receipt>, delayed = false, initiallyClosed = false) {
  let resolve!: (value: ReturnType<typeof receipt>) => void;
  const pending = new Promise<ReturnType<typeof receipt>>((done) => (resolve = done)),
    paths: string[] = [];
  const transport: KoinonTransport = {
    request: async <T>(_method: HttpMethod, path: string) => {
      paths.push(path);
      return (
        path.endsWith('/audit')
          ? delayed
            ? await pending
            : value
          : { items: [], total: 0, page: 1, page_size: 25, pages: 0 }
      ) as T;
    },
    stream: () => {
      throw Error('Unexpected stream');
    },
  };
  const facade = {
    context: signal({ subject: 'owner' }),
    tenantId: signal('north'),
    workspaceId: signal('space'),
    projectId: signal('project'),
    authRequired: signal(false),
    permissions: signal(new Set(['chat:use'])),
  };
  TestBed.configureTestingModule({
    imports: [KoinonAnswerAudit],
    providers: [
      { provide: KoinonFacade, useValue: facade },
      {
        provide: KoinonClientContext,
        useValue: { revision: signal(0), get: () => new KoinonClient({ transport }) },
      },
    ],
  });
  const fixture = TestBed.createComponent(KoinonAnswerAudit);
  fixture.componentRef.setInput('message', message);
  fixture.componentRef.setInput('threadId', 'thread');
  fixture.componentRef.setInput('open', !initiallyClosed);
  fixture.detectChanges();
  if (initiallyClosed) {
    await fixture.whenStable();
    fixture.componentRef.setInput('open', true);
    fixture.detectChanges();
  }
  if (!delayed) {
    await fixture.whenStable();
    fixture.detectChanges();
  }
  return { fixture, panel: fixture.componentInstance, facade, paths, resolve };
}
it('opens a sole private receipt on Sources without exposing its technical fingerprint or reading broader evidence', async () => {
  const { fixture, panel, paths } = await setup(receipt([], [file]));
  expect(panel.privateId()).toBe('');
  panel.tab.set('sources');
  fixture.detectChanges();
  await fixture.whenStable();
  fixture.detectChanges();
  expect(panel.privateId()).toBe('private');
  expect(fixture.nativeElement.querySelector('.source-detail')?.textContent).toContain(
    'It does not include file contents.',
  );
  expect(fixture.nativeElement.querySelector('.technical-references')?.open).toBe(false);
  const choice = fixture.nativeElement.querySelector('.source-options button');
  expect(choice.getAttribute('aria-pressed')).toBe('true');
  expect(choice.querySelector('ffk-icon[name=chevron]')).not.toBeNull();
  expect(paths.length).toBe(2);
  expect(paths.some((path) => path.includes('/evidence/'))).toBe(false);
});
it('opens a sole catalog source but keeps combined source and private choices explicit', async () => {
  const { fixture, panel } = await setup(receipt([source], [file]));
  panel.tab.set('sources');
  fixture.detectChanges();
  await fixture.whenStable();
  expect(panel.sourceId()).toBe('');
  expect(panel.privateId()).toBe('');
  panel.selectPrivate('private');
  fixture.detectChanges();
  await fixture.whenStable();
  expect(panel.selectedPrivate()?.id).toBe('private');
  expect(panel.sourceId()).toBe('');
  panel.state.audit.set({ ...panel.state.audit()!, private_files: [] });
  fixture.detectChanges();
  await fixture.whenStable();
  expect(panel.sourceId()).toBe('');
  panel.privateId.set('');
  fixture.detectChanges();
  await fixture.whenStable();
  fixture.detectChanges();
  expect(panel.sourceId()).toBe('source');
  expect(fixture.nativeElement.querySelector('.source-detail')?.textContent).toContain(
    'Recorded source passage.',
  );
});
for (const selection of ['sql', 'read', 'citation', 'private', 'source', 'result'])
  it(`does not replace an explicit ${selection} selection when the sole receipt arrives later`, async () => {
    const { fixture, panel, resolve } = await setup(receipt([], [file]), true);
    panel.tab.set('sources');
    if (selection === 'sql') panel.selectAttempt(0);
    if (selection === 'read') panel.selectRead(0);
    if (selection === 'citation') panel.selectCitation(0);
    if (selection === 'private') panel.selectPrivate('explicit-private');
    if (selection === 'source') panel.selectSource('explicit-source');
    if (selection === 'result')
      panel.state.selected.set({
        call_id: 'call',
        summary: 'Recorded query',
        tool_name: 'query_dataset',
        status: 'completed',
        occurred_at: '2026-10-29T10:00:00Z',
      });
    resolve(receipt([], [file]));
    await fixture.whenStable();
    fixture.detectChanges();
    expect(panel.privateId()).toBe(selection === 'private' ? 'explicit-private' : '');
  });
it('clears all local selections on a different answer and a permission/context close', async () => {
  const { fixture, panel, facade } = await setup(receipt([], [file]));
  panel.tab.set('sources');
  fixture.detectChanges();
  await fixture.whenStable();
  panel.selectAttempt(0);
  panel.readIndex.set(0);
  fixture.componentRef.setInput('message', { ...message, id: 'next-answer', run_id: undefined });
  fixture.detectChanges();
  await fixture.whenStable();
  fixture.detectChanges();
  expect(panel.privateId()).toBe('');
  expect(panel.sourceId()).toBe('');
  expect(panel.attemptIndex()).toBeNull();
  expect(panel.readIndex()).toBeNull();
  expect(fixture.nativeElement.querySelector('.source-detail')).toBeNull();
  panel.selectPrivate('private');
  panel.selectAttempt(0);
  panel.readIndex.set(0);
  facade.permissions.set(new Set());
  fixture.detectChanges();
  await fixture.whenStable();
  fixture.detectChanges();
  expect(panel.privateId()).toBe('');
  expect(panel.sourceId()).toBe('');
  expect(panel.attemptIndex()).toBeNull();
  expect(panel.readIndex()).toBeNull();
  expect(panel.state.audit()).toBeNull();
});
it('never reveals a late sole receipt after its authorized context is replaced', async () => {
  const { fixture, panel, facade, resolve } = await setup(receipt([], [file]), true);
  panel.tab.set('sources');
  facade.context.set({ subject: 'another-owner' });
  fixture.detectChanges();
  resolve(receipt([], [file]));
  await fixture.whenStable();
  fixture.detectChanges();
  expect(panel.privateId()).toBe('');
  expect(panel.selectedPrivate()).toBeNull();
  expect(fixture.nativeElement.querySelector('.source-detail')).toBeNull();
});

it('subscribes to Sources when Audit was mounted closed before its first opening', async () => {
  const { fixture, panel } = await setup(receipt([], [file]), false, true);
  panel.tab.set('sources');
  fixture.detectChanges();
  await fixture.whenStable();
  fixture.detectChanges();
  expect(panel.privateId()).toBe('private');
  expect(fixture.nativeElement.querySelector('.source-detail h3')?.textContent).toContain(
    file.filename,
  );
});
