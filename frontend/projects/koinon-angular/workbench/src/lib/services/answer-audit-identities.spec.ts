// Copyright 2026 Firefly Software Foundation
// SPDX-License-Identifier: Apache-2.0
import { signal } from '@angular/core';
import { TestBed } from '@angular/core/testing';
import {
  KoinonClient,
  type KoinonTransport,
  type HttpMethod,
  type SourceReference,
} from '@fireflyframework/koinon-sdk';
import { KoinonClientContext, KoinonFacade, KoinonI18n } from '@fireflyframework/koinon-angular';
import { KoinonAnswerAudit } from '../../../../chat/page/src/artifacts/answer-audit';

async function setup() {
  const paths: string[] = [];
  const receipt = {
    run_id: 'run',
    provenance_status: 'recorded',
    source_manifest_complete: true,
    sources: [
      {
        id: 'document-evidence',
        kind: 'document',
        asset_id: 'document',
        title: 'Recorded policy',
        source_id: 'source-parent',
        source_version_id: 'original-version',
        extraction_id: 'recorded-view',
        source_part_id: 'persisted-passage',
        source_part_sha256: 'a'.repeat(64),
        chunk_id: null,
        page: null,
        recorded_page: 7,
        page_basis: 'recorded_loader',
        used_revision: 'source-part-sha256:' + 'a'.repeat(64),
        quote: 'The recorded policy.',
        availability: 'available',
      },
      {
        id: 'knowledge-evidence',
        kind: 'knowledge_version',
        asset_id: 'published-item',
        knowledge_item_id: 'published-item',
        knowledge_version_id: 'published-version',
        knowledge_version: 3,
        title: 'Published renewal policy',
        used_revision: 'knowledge-content-sha256:' + 'b'.repeat(64),
        quote: 'Renewals require review.',
        availability: 'available',
      },
      {
        id: 'snapshot-evidence',
        kind: 'dataset',
        asset_id: 'dataset',
        title: 'Quarterly activity',
        snapshot_id: 'snapshot-used',
        used_revision: 'snapshot-sha256:' + 'f'.repeat(64),
        availability: 'available',
      },
    ],
    native_reads: [
      {
        result_id: 'document-read',
        stage: 'rlm.read',
        domain: 'documents',
        tenant_id: 'north',
        workspace_id: 'workspace',
        entity_id: 'document',
        read_kind: 'document_extraction',
        source_ids: ['native-source'],
        snapshot_ids: [],
        source_version_id: 'original-version',
        extraction_id: 'recorded-view',
        content_sha256: 'c'.repeat(64),
        origin: { original_filename: 'policy.pdf', connection_id: 'document-connection' },
      },
      {
        result_id: 'knowledge-read',
        stage: 'model.context',
        domain: 'knowledge',
        tenant_id: 'north',
        workspace_id: 'workspace',
        entity_id: 'published-item',
        read_kind: 'knowledge_version',
        source_ids: ['published-item'],
        snapshot_ids: [],
        knowledge_item_id: 'published-item',
        knowledge_version_id: 'published-version',
        knowledge_version: 3,
        content_sha256: 'd'.repeat(64),
      },
      {
        result_id: 'other-version-read',
        stage: 'model.context',
        domain: 'knowledge',
        tenant_id: 'north',
        workspace_id: 'workspace',
        entity_id: 'published-item',
        read_kind: 'knowledge_version',
        knowledge_item_id: 'published-item',
        knowledge_version_id: 'other-version',
        knowledge_version: 4,
        source_ids: ['published-item'],
        snapshot_ids: [],
        content_sha256: 'e'.repeat(64),
        origin: { original_filename: 'unrelated-origin.pdf' },
      },
      {
        result_id: 'snapshot-read',
        stage: 'execution',
        domain: 'structured',
        tenant_id: 'north',
        workspace_id: 'workspace',
        entity_id: 'dataset',
        content_sha256: 'f'.repeat(64),
        snapshot_ids: ['snapshot-used'],
        origin: { original_filename: 'recorded-source.xlsx', connection_id: 'dataset-connection' },
      },
      {
        result_id: 'other-snapshot-read',
        stage: 'execution',
        domain: 'structured',
        tenant_id: 'north',
        workspace_id: 'workspace',
        entity_id: 'dataset',
        content_sha256: 'a'.repeat(64),
        snapshot_ids: ['other-snapshot'],
        origin: { original_filename: 'other-snapshot.xlsx' },
      },
    ],
    private_files: [
      {
        id: 'private-file',
        filename: 'provided.pdf',
        media_type: 'application/pdf',
        sha256: 'a'.repeat(64),
        used_revision: 1,
        availability: 'available',
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
      throw Error('Audit must not start a generation');
    },
  };
  TestBed.configureTestingModule({
    imports: [KoinonAnswerAudit],
    providers: [
      {
        provide: KoinonFacade,
        useValue: {
          context: signal({ subject: 'owner' }),
          tenantId: signal('north'),
          workspaceId: signal('workspace'),
          projectId: signal(''),
          authRequired: signal(false),
          permissions: signal(new Set(['chat:use'])),
        },
      },
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
  return { fixture, paths };
}

it('distinguishes exact document extractions from published knowledge without inventing SQL location', async () => {
  const { fixture, paths } = await setup();
  fixture.componentInstance.tab.set('execution');
  fixture.componentInstance.selectRead(0);
  fixture.detectChanges();
  let detail = fixture.nativeElement.querySelector('.receipt-detail') as HTMLElement;
  expect(detail.textContent).toContain('Recorded document extraction');
  expect(detail.textContent).toContain('original-version');
  expect(detail.textContent).toContain('recorded-view');
  fixture.componentInstance.selectRead(1);
  fixture.detectChanges();
  detail = fixture.nativeElement.querySelector('.receipt-detail') as HTMLElement;
  expect(detail.textContent).toContain('Published knowledge content');
  expect(detail.textContent).toContain('published-version');
  expect(detail.textContent).toContain('Knowledge version');
  expect(detail.querySelector('.read-location')?.textContent).not.toContain('Database');
  expect(paths).toEqual([
    '/tenants/north/chat/runs/run/audit',
    '/tenants/north/chat/runs/run/activity',
  ]);
  fixture.destroy();
});

it('shows only the selected immutable knowledge version and labels its fingerprint accurately', async () => {
  const { fixture } = await setup();
  fixture.componentInstance.tab.set('sources');
  fixture.componentInstance.selectSource('knowledge-evidence');
  fixture.detectChanges();
  const detail = fixture.nativeElement.querySelector('.source-detail') as HTMLElement;
  expect(detail.textContent).toContain('Renewals require review.');
  expect(detail.textContent).toContain('Knowledge content fingerprint');
  expect(detail.textContent).toContain('published-version');
  expect(detail.textContent).not.toContain('unrelated-origin.pdf');
  expect(detail.textContent).not.toContain('Original source identity was not recorded.');
  const technical = detail.querySelector('details.technical-references') as HTMLDetailsElement;
  expect(technical.open).toBe(false);
  expect(technical.textContent).toContain('Knowledge content fingerprint');
  expect(detail.querySelector(':scope > dl')?.textContent).not.toContain('fingerprint');
  expect(
    fixture.componentInstance.sourceReads(fixture.componentInstance.selectedSource()!).length,
  ).toBe(1);
  const otherRead = fixture.componentInstance.state
    .audit()!
    .native_reads!.find((read) => read.knowledge_version_id === 'other-version')!;
  expect(fixture.componentInstance.readTitle(otherRead)).toBeNull();
  fixture.destroy();
});

it('localizes extraction and knowledge labels while preserving exact identifiers', async () => {
  const { fixture } = await setup();
  TestBed.inject(KoinonI18n).apply({
    locale: 'es-ES',
    time_zone: 'Europe/Madrid',
    response_language: 'es',
  });
  fixture.componentInstance.tab.set('execution');
  fixture.componentInstance.selectRead(0);
  fixture.detectChanges();
  expect(fixture.nativeElement.querySelector('.receipt-detail')?.textContent).toContain(
    'Extracción de documento registrada',
  );
  expect(fixture.nativeElement.querySelector('.receipt-detail')?.textContent).toContain(
    'original-version',
  );
  fixture.destroy();
});

it('keeps source origins bound to the selected table snapshot', async () => {
  const { fixture } = await setup();
  fixture.componentInstance.tab.set('sources');
  fixture.componentInstance.selectSource('snapshot-evidence');
  fixture.detectChanges();
  const source = fixture.componentInstance.selectedSource()!;
  expect(fixture.componentInstance.sourceReads(source).length).toBe(1);
  const detail = fixture.nativeElement.querySelector('.source-detail') as HTMLElement;
  expect(detail.textContent).toContain('recorded-source.xlsx');
  expect(detail.textContent).not.toContain('other-snapshot.xlsx');
  expect(detail.querySelector('details.technical-references')?.textContent).toContain(
    'dataset-connection',
  );
  expect(detail.querySelector('ffk-recorded-origin')?.textContent).not.toContain(
    'dataset-connection',
  );
  fixture.destroy();
});

it('keeps private fingerprints inside the technical disclosure', async () => {
  const { fixture } = await setup();
  fixture.componentInstance.tab.set('sources');
  fixture.componentInstance.selectPrivate('private-file');
  fixture.detectChanges();
  const detail = fixture.nativeElement.querySelector('.source-detail') as HTMLElement;
  expect(detail.querySelector(':scope > dl')?.textContent).not.toContain('File fingerprint');
  const technical = detail.querySelector('details.technical-references') as HTMLDetailsElement;
  expect(technical.open).toBe(false);
  expect(technical.textContent).toContain('a'.repeat(64));
  fixture.destroy();
});

it('keeps origins unknown when a legacy reference has no exact version or snapshot identity', async () => {
  const { fixture } = await setup();
  const legacy: SourceReference[] = [
    {
      id: 'legacy-document',
      asset_id: 'document',
      kind: 'document',
      title: 'Legacy passage',
      chunk_id: 'old-passage',
    },
    { id: 'legacy-dataset', asset_id: 'dataset', kind: 'dataset', title: 'Legacy data' },
  ];
  for (const source of legacy) expect(fixture.componentInstance.sourceReads(source)).toEqual([]);
  fixture.destroy();
});
