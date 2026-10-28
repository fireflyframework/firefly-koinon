// Copyright 2026 Firefly Software Foundation
// SPDX-License-Identifier: Apache-2.0
import { TestBed } from '@angular/core/testing';
import { signal } from '@angular/core';
import {
  KoinonClient,
  KoinonError,
  type KoinonTransport,
  type HttpMethod,
  type ChatMessage,
} from '@fireflyframework/koinon-sdk';
import { KoinonClientContext, KoinonFacade } from '@fireflyframework/koinon-angular';
import { KoinonAnswerAudit } from '../../../chat/page/src/artifacts/answer-audit';
it('shows recorded legacy policy and citations without inventing a run or making protected requests', async () => {
  let requests = 0;
  let denied = false;
  const transport: KoinonTransport = {
    request: async <T>() => {
      requests++;
      if (denied) throw new KoinonError(403, 'FORBIDDEN', 'Owner audit denied');
      return {} as T;
    },
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
  const message: ChatMessage = {
    id: 'legacy',
    role: 'assistant',
    text: 'Saved answer',
    status: 'cancelled',
    created_at: '2026-10-27T10:00:00Z',
    answer_policy: { outcome: 'refused', reason: 'Recorded policy reason' },
    citations: [{ title: 'Recorded policy', text: 'Recorded passage', document_id: 'document' }],
    artifacts: [],
  };
  const fixture = TestBed.createComponent(KoinonAnswerAudit);
  fixture.componentRef.setInput('message', message);
  fixture.componentRef.setInput('threadId', 'thread');
  fixture.componentRef.setInput('open', true);
  fixture.detectChanges();
  await fixture.whenStable();
  expect(requests).toBe(0);
  expect(fixture.nativeElement.textContent).toContain('Execution trace is unavailable');
  expect(fixture.nativeElement.textContent).toContain('Recorded policy reason');
  expect(fixture.nativeElement.textContent).not.toContain('Recorded passage');
  const tabs = fixture.nativeElement.querySelectorAll(
    '[role=tab]',
  ) as NodeListOf<HTMLButtonElement>;
  expect(tabs.length).toBe(3);
  expect(tabs[0].getAttribute('aria-selected')).toBe('true');
  tabs[0].dispatchEvent(new KeyboardEvent('keydown', { key: 'ArrowRight', bubbles: true }));
  fixture.detectChanges();
  expect(tabs[1].getAttribute('aria-selected')).toBe('true');
  expect(fixture.nativeElement.querySelector('[role=tabpanel]:not([hidden])')?.id).toBe(
    tabs[1].getAttribute('aria-controls'),
  );
  const source = [
    ...fixture.nativeElement.querySelectorAll('.source-options button'),
  ][0] as HTMLButtonElement;
  source.click();
  fixture.detectChanges();
  expect(source.getAttribute('aria-pressed')).toBe('true');
  expect(fixture.nativeElement.textContent).toContain('Recorded passage');
  tabs[1].dispatchEvent(new KeyboardEvent('keydown', { key: 'End', bubbles: true }));
  fixture.detectChanges();
  expect(tabs[2].getAttribute('aria-selected')).toBe('true');
  tabs[2].dispatchEvent(new KeyboardEvent('keydown', { key: 'Home', bubbles: true }));
  fixture.detectChanges();
  expect(tabs[0].getAttribute('aria-selected')).toBe('true');
  expect(fixture.nativeElement.textContent).not.toContain('Confidence');
  const opened = vi.spyOn(fixture.componentInstance.state, 'open');
  fixture.componentRef.setInput('message', { ...message, text: 'A text-only delta' });
  fixture.detectChanges();
  await fixture.whenStable();
  expect(opened).not.toHaveBeenCalled();
  let citation = '';
  fixture.componentInstance.citationSelected.subscribe(
    (value) => (citation = value.document_id ?? ''),
  );
  const button = [...fixture.nativeElement.querySelectorAll('button')].find(
    (row) => row.textContent?.trim() === 'Open recorded citation',
  ) as HTMLButtonElement;
  button.click();
  expect(citation).toBe('document');
  fixture.componentRef.setInput('message', { ...message, id: 'no-citations', citations: [] });
  fixture.detectChanges();
  await fixture.whenStable();
  fixture.componentInstance.tab.set('sources');
  fixture.detectChanges();
  expect(
    fixture.nativeElement.querySelector('[role=tabpanel]:not([hidden])')?.textContent,
  ).toContain('Source provenance is unavailable.');
  fixture.componentRef.setInput('message', {
    ...message,
    id: 'proposal-only',
    answer_policy: {
      outcome: 'review_required',
      reason: 'Review the proposed change before applying it.',
    },
  });
  fixture.detectChanges();
  await fixture.whenStable();
  expect(fixture.componentInstance.outcome()).toBe('Review required');
  expect(
    fixture.nativeElement.querySelector('[role=tabpanel]:not([hidden])')?.textContent,
  ).toContain('Review the proposed change before applying it.');
  denied = true;
  fixture.componentRef.setInput('message', { ...message, id: 'denied-run', run_id: 'run' });
  fixture.detectChanges();
  await fixture.whenStable();
  fixture.componentInstance.tab.set('sources');
  fixture.detectChanges();
  expect(fixture.componentInstance.state.auditError()).toBe('Owner audit denied');
  expect(fixture.componentInstance.fallbackCitations()).toEqual([]);
  expect(
    fixture.nativeElement.querySelector('[role=tabpanel]:not([hidden])')?.textContent,
  ).not.toContain('Recorded passage');
  fixture.destroy();
});
it('shows stored owner generation, private receipts and actual SQL attempts without broader evidence access', async () => {
  const paths: string[] = [];
  const receipt = {
    run_id: 'run',
    provenance_status: 'recorded',
    source_provenance_complete: true,
    generations: [
      {
        id: 'generation-old',
        start_sequence: 0,
        agent_id: 'agent-old',
        agent_revision: 2,
        provider_id: 'provider-old',
        provider_revision: 3,
        provider_kind: 'ollama',
        model_id: 'recorded-model:1',
        model_class: 'OllamaModel',
        api: 'chat',
        started_at: '2026-10-27T10:00:00Z',
        finished_at: '2026-10-27T10:00:05Z',
        status: 'completed',
      },
    ],
    sources: [
      {
        id: 'dataset-evidence',
        asset_id: 'canonical-dataset',
        title: 'Recorded dataset',
        kind: 'dataset',
      },
      {
        id: 'document-evidence',
        asset_id: 'document-asset',
        title: 'Recorded document',
        kind: 'document',
      },
    ],
    private_files: [
      {
        id: 'private-file',
        filename: 'Recorded plan.pdf',
        media_type: 'application/pdf',
        sha256: 'a'.repeat(64),
        used_revision: 4,
        availability: 'deleted',
      },
    ],
    native_reads: [
      {
        result_id: 'result',
        stage: 'model.context',
        domain: 'structured',
        tenant_id: 'north',
        workspace_id: 'w',
        entity_id: 'canonical-dataset',
        content_sha256: 'd'.repeat(64),
        engine: 'postgresql',
        database: 'recorded_metadata_db',
        catalog: 'metadata_catalog',
        schema: 'retained_schema',
        read_kind: 'metadata',
        origin: {
          original_filename: 'Revenue.xlsx',
          sheet_or_json_path: 'Sheet1',
          connection_name: 'Recorded warehouse',
          database: 'warehouse_origin',
          schema: 'sales',
          table: 'orders',
        },
      },
      {
        result_id: 'document-result',
        stage: 'retrieval',
        domain: 'documents',
        tenant_id: 'north',
        workspace_id: 'w',
        entity_id: 'document-asset',
        content_sha256: 'e'.repeat(64),
        engine: 'postgresql',
        database: 'recorded_document_store',
        catalog: 'document_catalog',
        schema: 'recorded_documents',
        read_kind: 'indexed_document',
        origin: { original_filename: 'Original policy.pdf' },
      },
    ],
    sql_attempts: [
      {
        result_id: 'result',
        ordinal: 1,
        stage: 'validation',
        statement_sha256: 'b'.repeat(64),
        statement: 'DROP TABLE forbidden',
        outcome: 'blocked',
        executed: false,
        reason_code: 'READ_ONLY_POLICY',
      },
      {
        result_id: 'result',
        ordinal: 2,
        stage: 'execution',
        statement_sha256: 'c'.repeat(64),
        statement: 'SELECT owner FROM policy',
        outcome: 'succeeded',
        executed: true,
        row_count: 47,
        truncated: false,
        engine: 'duckdb',
        database: 'memory',
        catalog: 'memory',
        schema: 'main',
        execution_kind: 'imported_snapshot',
        dataset_id: 'canonical-dataset',
        native_dataset_id: 'retained-dataset',
        tables: [
          { table_id: 'table-one', table_name: 'orders_import', snapshot_id: 'snapshot-used' },
        ],
        snapshot_pins: { 'table-one': 'snapshot-used', 'unmapped-native': 'other-snapshot' },
      },
    ],
  };
  const transport: KoinonTransport = {
    request: async <T>(_method: HttpMethod, path: string) => {
      paths.push(path);
      return (
        path.endsWith('/audit')
          ? receipt
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
    workspaceId: signal('w'),
    projectId: signal('p'),
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
  fixture.componentRef.setInput('message', {
    id: 'answer',
    run_id: 'run',
    role: 'assistant',
    status: 'completed',
    text: 'Recorded answer',
    citations: [],
    artifacts: [],
    created_at: '2026-10-27T10:00:00Z',
  });
  fixture.componentRef.setInput('threadId', 'thread');
  fixture.componentRef.setInput('open', true);
  fixture.detectChanges();
  await fixture.whenStable();
  fixture.detectChanges();
  expect(fixture.nativeElement.textContent).toContain('recorded-model:1');
  expect(fixture.nativeElement.textContent).toContain('agent-old');
  expect(fixture.nativeElement.textContent).toContain('provider-old');
  expect(
    paths.some(
      (path) =>
        path.includes('/evidence/') ||
        path.includes('/configuration') ||
        path.includes('/providers/'),
    ),
  ).toBe(false);
  fixture.componentInstance.tab.set('sources');
  fixture.detectChanges();
  const catalogButtons = [
    ...fixture.nativeElement.querySelectorAll('.source-options button'),
  ] as HTMLButtonElement[];
  catalogButtons.find((button) => button.textContent?.includes('Recorded dataset'))!.click();
  fixture.detectChanges();
  expect(fixture.nativeElement.querySelector('.source-detail')?.textContent).toContain(
    'Original source identity was not recorded.',
  );
  expect(fixture.nativeElement.querySelector('.source-detail')?.textContent).not.toContain(
    'Revenue.xlsx',
  );
  catalogButtons.find((button) => button.textContent?.includes('Recorded document'))!.click();
  fixture.detectChanges();
  expect(fixture.nativeElement.querySelector('.source-detail')?.textContent).toContain(
    'Original source identity was not recorded.',
  );
  const privateButton = [...fixture.nativeElement.querySelectorAll('.source-options button')].find(
    (row) => row.textContent?.includes('Recorded plan.pdf'),
  ) as HTMLButtonElement;
  privateButton.click();
  fixture.detectChanges();
  expect(fixture.nativeElement.textContent).toContain('It does not include file contents.');
  expect(fixture.nativeElement.textContent).toContain('a'.repeat(64));
  expect(fixture.nativeElement.textContent).toContain('Deleted');
  fixture.componentInstance.tab.set('execution');
  fixture.detectChanges();
  expect(fixture.nativeElement.textContent).not.toContain('DROP TABLE forbidden');
  const attempts = fixture.nativeElement.querySelectorAll(
    '.receipt-toggle',
  ) as NodeListOf<HTMLButtonElement>;
  attempts[0].click();
  fixture.detectChanges();
  expect(fixture.nativeElement.textContent).toContain('DROP TABLE forbidden');
  expect(fixture.nativeElement.textContent).toContain('Not executed');
  expect(fixture.nativeElement.querySelector('.execution-location')?.textContent).toContain(
    'Not recorded',
  );
  attempts[1].click();
  fixture.detectChanges();
  expect(fixture.nativeElement.textContent).not.toContain('DROP TABLE forbidden');
  expect(fixture.nativeElement.textContent).toContain('SELECT owner FROM policy');
  expect(fixture.nativeElement.querySelector('ffk-code-block code')?.textContent).toBe(
    'SELECT owner FROM policy',
  );
  expect(fixture.nativeElement.querySelector('ffk-code-block .keyword')?.textContent).toBe(
    'SELECT',
  );
  expect(fixture.nativeElement.textContent).toContain('47');
  expect(fixture.nativeElement.textContent).toContain('Imported snapshot execution');
  expect(fixture.nativeElement.textContent).toContain('duckdb');
  expect(fixture.nativeElement.textContent).toContain('orders_import');
  expect(fixture.nativeElement.textContent).toContain('snapshot-used');
  expect(fixture.nativeElement.textContent).toContain('other-snapshot');
  expect(fixture.nativeElement.querySelectorAll('.table-snapshots code').length).toBe(0);
  const technical = fixture.nativeElement.querySelector(
    '.receipt-detail .technical-references',
  ) as HTMLDetailsElement;
  expect(technical.open).toBe(false);
  expect(
    fixture.nativeElement.querySelectorAll('.receipt-detail .technical-references').length,
  ).toBe(1);
  expect(fixture.nativeElement.querySelector('.execution-location')?.textContent).toContain(
    'Recorded dataset',
  );
  expect(fixture.nativeElement.querySelector('.execution-location')?.textContent).not.toContain(
    'canonical-dataset',
  );
  expect(
    fixture.nativeElement.querySelector('.table-snapshots').compareDocumentPosition(technical) &
      Node.DOCUMENT_POSITION_FOLLOWING,
  ).toBeTruthy();
  attempts[2].click();
  fixture.detectChanges();
  expect(fixture.nativeElement.textContent).toContain('recorded_metadata_db');
  expect(fixture.nativeElement.textContent).toContain('warehouse_origin');
  expect(fixture.nativeElement.textContent).toContain('Revenue.xlsx');
  attempts[3].click();
  fixture.detectChanges();
  expect(fixture.nativeElement.textContent).toContain('Indexed document content');
  expect(fixture.nativeElement.textContent).toContain('recorded_document_store');
  expect(fixture.nativeElement.textContent).toContain('Original policy.pdf');
  expect(paths.some((path) => path.includes('/results/') || path.includes('/attachments/'))).toBe(
    false,
  );
  fixture.componentInstance.tab.set('overview');
  fixture.componentInstance.state.audit.update((value) =>
    value ? { ...value, source_provenance_complete: null } : null,
  );
  fixture.detectChanges();
  expect(
    fixture.nativeElement.querySelector('[role=tabpanel]:not([hidden])')?.textContent,
  ).toContain('Source coverage was not recorded.');
  fixture.componentInstance.state.audit.update((value) =>
    value ? { ...value, source_provenance_complete: false } : null,
  );
  fixture.detectChanges();
  const overview = fixture.nativeElement.querySelector(
    '[role=tabpanel]:not([hidden])',
  )?.textContent;
  expect(overview).toContain('Source provenance is incomplete.');
  expect(overview).not.toContain('Historical source provenance is incomplete.');
  fixture.destroy();
});
