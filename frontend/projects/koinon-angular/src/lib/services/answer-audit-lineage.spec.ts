// Copyright 2026 Firefly Software Foundation
// SPDX-License-Identifier: Apache-2.0
import { TestBed } from '@angular/core/testing';
import { signal } from '@angular/core';
import {
  KoinonClient,
  type KoinonTransport,
  type HttpMethod,
  type NativeReadReceipt,
  type SqlAttemptReceipt,
} from '@fireflyframework/koinon-sdk';
import { KoinonClientContext, KoinonFacade } from '@fireflyframework/koinon-angular';
import { KoinonAnswerAudit } from '../../../chat/page/src/artifacts/answer-audit';
const attempt: SqlAttemptReceipt = {
  result_id: 'sql-result',
  generation_id: 'generation-one',
  ordinal: 1,
  stage: 'execution',
  statement_sha256: 'a'.repeat(64),
  statement: 'SELECT owner FROM policy',
  outcome: 'succeeded',
  executed: true,
  engine: 'duckdb',
  execution_kind: 'imported_snapshot',
  dataset_id: 'dataset-one',
  snapshot_pins: { table: 'snapshot-one' },
};
const read: NativeReadReceipt = {
  result_id: 'sql-result',
  generation_id: 'generation-one',
  stage: 'model.context',
  domain: 'structured',
  tenant_id: 'north',
  workspace_id: 'workspace',
  entity_id: 'dataset-one',
  content_sha256: 'b'.repeat(64),
  snapshot_ids: ['snapshot-one'],
  origin: { database: 'warehouse-one', table: 'orders' },
};
async function inspect(reads: NativeReadReceipt[], sql = attempt) {
  const paths: string[] = [];
  const transport: KoinonTransport = {
    request: async <T>(_method: HttpMethod, path: string) => {
      paths.push(path);
      return (
        path.endsWith('/audit')
          ? {
              run_id: 'run',
              provenance_status: 'recorded',
              native_reads: reads,
              sql_attempts: [sql],
            }
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
    workspaceId: signal('workspace'),
    projectId: signal(''),
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
    text: 'Saved answer',
    status: 'completed',
    created_at: '2026-10-27T10:00:00Z',
    citations: [],
    artifacts: [],
  });
  fixture.componentRef.setInput('threadId', 'thread');
  fixture.componentRef.setInput('open', true);
  fixture.detectChanges();
  await fixture.whenStable();
  fixture.componentInstance.tab.set('execution');
  fixture.componentInstance.selectAttempt(0);
  fixture.detectChanges();
  return {
    fixture,
    paths,
    lineage: fixture.nativeElement.querySelector('.sql-lineage') as HTMLElement | null,
  };
}
it('shows every distinct recorded origin for the exact result while excluding contradictory associations', async () => {
  const { fixture, paths, lineage } = await inspect([
    read,
    { ...read, generation_id: null, origin: { database: 'warehouse-two' } },
    { ...read, origin: { table: 'orders', database: 'warehouse-one' } },
    { ...read, result_id: 'other-result', origin: { database: 'wrong-result' } },
    { ...read, generation_id: 'other-generation', origin: { database: 'wrong-generation' } },
    { ...read, entity_id: 'other-dataset', origin: { database: 'wrong-dataset' } },
    { ...read, domain: 'documents', origin: { database: 'wrong-domain' } },
  ]);
  expect(lineage).not.toBeNull();
  expect(lineage?.textContent).toContain('warehouse-one');
  expect(lineage?.textContent).toContain('warehouse-two');
  expect(lineage?.textContent).not.toContain('wrong-');
  expect(lineage?.querySelectorAll('ffk-recorded-origin').length).toBe(2);
  expect(fixture.nativeElement.querySelector('.execution-location')?.textContent).not.toContain(
    'warehouse-',
  );
  expect(paths).toEqual([
    '/tenants/north/chat/runs/run/audit',
    '/tenants/north/chat/runs/run/activity',
  ]);
  fixture.destroy();
});
it('does not associate a source using matching pins alone', async () => {
  const { fixture, lineage } = await inspect([{ ...read, result_id: 'other-result' }]);
  expect(lineage?.textContent).toContain('Original source identity was not recorded.');
  expect(lineage?.textContent).not.toContain('warehouse-one');
  fixture.destroy();
});
it('keeps current structured-producer null origin unknown despite a recorded metadata database', async () => {
  const { fixture, lineage } = await inspect([
    {
      ...read,
      origin: null,
      engine: 'postgresql',
      database: 'metadata-store',
      catalog: 'metadata-catalog',
      schema: 'metadata-schema',
    },
  ]);
  expect(lineage?.textContent).toContain('Original source identity was not recorded.');
  expect(lineage?.textContent).not.toContain('metadata-store');
  expect(lineage?.textContent).not.toContain('metadata-schema');
  fixture.destroy();
});
it('does not invent a dataset or generation binding when optional historical fields are absent', async () => {
  const { fixture, lineage } = await inspect([{ ...read, generation_id: null }], {
    ...attempt,
    dataset_id: null,
    generation_id: null,
  });
  expect(lineage?.textContent).toContain('warehouse-one');
  fixture.destroy();
});
