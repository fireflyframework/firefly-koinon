// Copyright 2026 Firefly Software Foundation
// SPDX-License-Identifier: Apache-2.0
import { signal } from '@angular/core';
import { TestBed } from '@angular/core/testing';
import {
  KoinonClient,
  type HttpMethod,
  type KoinonTransport,
  type RequestOptions,
  type SourceReference,
} from '@fireflyframework/koinon-sdk';
import { KoinonClientContext, KoinonFacade } from '@fireflyframework/koinon-angular';
import { KoinonAnswerAudit } from '../../../../chat/page/src/artifacts/answer-audit';

const text = 'The service review owner is Ava Chen.';
const digest = 'b1a4d0793cc70b1c41102f5b0b6ed7cb66d29873fe1c175754af8a36287d8e9b';
const source: SourceReference = {
  id: 'recorded-source',
  asset_id: 'document',
  source_id: 'catalog-source',
  kind: 'document',
  title: 'Service review',
  source_version_id: 'used-version',
  extraction_id: 'used-extraction',
  source_part_id: 'used-part',
  source_part_sha256: digest,
  used_revision: 'source-part-sha256:' + digest,
  recorded_page: 3,
  page_basis: 'recorded_loader',
  quote: text,
  availability: 'changed',
};
const part = {
  document_id: 'document',
  catalog_source_id: 'catalog-source',
  native_source_id: 'native-source',
  source_version_id: 'used-version',
  extraction_id: 'used-extraction',
  source_part_id: 'used-part',
  kind: 'chunk',
  sha256: digest,
  text,
  recorded_page: 3,
  page_basis: 'recorded_loader',
  raw_sha256: 'a'.repeat(64),
  normalized_sha256: 'b'.repeat(64),
  input_sha256: 'b'.repeat(64),
};

async function setup(read: () => Promise<unknown> = async () => part, reference = source) {
  const requests: { path: string; signal?: AbortSignal }[] = [];
  const transport: KoinonTransport = {
    request: async <T>(_method: HttpMethod, path: string, options?: RequestOptions) => {
      requests.push({ path, signal: options?.signal });
      return (
        path.endsWith('/audit')
          ? {
              run_id: 'run',
              provenance_status: 'recorded',
              source_provenance_complete: true,
              sources: [reference],
              native_reads: [],
              sql_attempts: [],
            }
          : path.includes('/versions/')
            ? await read()
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
    projectId: signal('project'),
    authRequired: signal(false),
    permissions: signal(new Set(['evidence:read', 'catalog:read'])),
  };
  TestBed.configureTestingModule({
    imports: [KoinonAnswerAudit],
    providers: [
      { provide: KoinonFacade, useValue: facade },
      {
        provide: KoinonClientContext,
        useValue: {
          revision: signal(0),
          get: () => new KoinonClient({ transport }),
        },
      },
    ],
  });
  const fixture = TestBed.createComponent(KoinonAnswerAudit);
  fixture.componentRef.setInput('threadId', 'thread');
  fixture.componentRef.setInput('message', {
    id: 'answer',
    role: 'assistant',
    text: 'Ava owns the review.',
    status: 'completed',
    created_at: '2026-10-30T10:00:00Z',
    run_id: 'run',
    citations: [],
    artifacts: [],
  });
  fixture.componentRef.setInput('open', true);
  fixture.detectChanges();
  await fixture.whenStable();
  fixture.componentInstance.tab.set('sources');
  fixture.detectChanges();
  await fixture.whenStable();
  const navigate = vi.fn();
  fixture.componentInstance.resourceRequested.subscribe(navigate);
  const open = [...fixture.nativeElement.querySelectorAll('button')].find(
    (button) => button.textContent?.trim() === 'Open source',
  ) as HTMLButtonElement;
  expect(open).toBeTruthy();
  open.click();
  fixture.detectChanges();
  return { fixture, facade, requests, navigate };
}

it('opens the exact historical document part without navigating to the current source', async () => {
  const { fixture, requests, navigate } = await setup();
  await fixture.whenStable();
  fixture.detectChanges();
  expect(navigate).not.toHaveBeenCalled();
  expect(
    requests.some(
      (request) =>
        request.path ===
        '/tenants/north/documents/document/versions/used-version/extractions/used-extraction/parts/used-part',
    ),
  ).toBe(true);
  const panel = fixture.nativeElement.querySelector('ffk-recorded-document-source');
  expect(panel?.textContent).toContain('Source used in this answer');
  expect(panel?.textContent).toContain(text);
  expect(panel?.textContent).toContain('used-version');
  expect(panel?.textContent).toContain('Source has changed');
});

it('rejects text changes even when the response keeps the saved quote and digest', async () => {
  const { fixture, navigate } = await setup(async () => ({
    ...part,
    text: text + ' Unrecorded addition.',
  }));
  await fixture.whenStable();
  fixture.detectChanges();
  expect(navigate).not.toHaveBeenCalled();
  const panel = fixture.nativeElement.querySelector('ffk-recorded-document-source');
  expect(panel?.textContent).toContain('The source does not match the recorded answer.');
  expect(panel?.querySelector('.recorded-content')).toBeNull();
});

for (const mismatch of [
  'document_id',
  'catalog_source_id',
  'source_version_id',
  'extraction_id',
  'source_part_id',
  'sha256',
  'recorded_page',
]) {
  it(`rejects an exact-part response with a different ${mismatch}`, async () => {
    const { fixture } = await setup(async () => ({
      ...part,
      [mismatch]: mismatch === 'recorded_page' ? 9 : 'different-value',
    }));
    await fixture.whenStable();
    fixture.detectChanges();
    const panel = fixture.nativeElement.querySelector('ffk-recorded-document-source');
    expect(panel?.textContent).toContain('The source does not match the recorded answer.');
    expect(panel?.querySelector('.recorded-content')).toBeNull();
  });
}

it('does not fall back to the current document for an incomplete immutable identity', async () => {
  const { fixture, requests, navigate } = await setup(async () => part, {
    ...source,
    extraction_id: undefined,
  });
  await fixture.whenStable();
  fixture.detectChanges();
  expect(navigate).not.toHaveBeenCalled();
  expect(requests.filter((request) => request.path.includes('/documents/'))).toHaveLength(0);
  expect(
    fixture.nativeElement.querySelector('ffk-recorded-document-source')?.textContent,
  ).toContain('The recorded source identity is incomplete.');
});

it('shows an unpaginated historical fragment without inventing a page number', async () => {
  const { fixture } = await setup(async () => ({ ...part, recorded_page: null }), {
    ...source,
    recorded_page: null,
  });
  await fixture.whenStable();
  fixture.detectChanges();
  const panel = fixture.nativeElement.querySelector('ffk-recorded-document-source');
  expect(panel?.querySelector('.recorded-content')?.textContent).toContain(text);
  expect(panel?.querySelector('.location')).toBeNull();
});

it('does not navigate to a current document when only an immutable revision claim remains', async () => {
  const { fixture, requests, navigate } = await setup(async () => part, {
    ...source,
    source_version_id: undefined,
    extraction_id: undefined,
    source_part_id: undefined,
    source_part_sha256: undefined,
    recorded_page: undefined,
    page_basis: undefined,
  });
  await fixture.whenStable();
  fixture.detectChanges();
  expect(navigate).not.toHaveBeenCalled();
  expect(requests.filter((request) => request.path.includes('/documents/'))).toHaveLength(0);
  expect(
    fixture.nativeElement.querySelector('ffk-recorded-document-source')?.textContent,
  ).toContain('The recorded source identity is incomplete.');
});

it('returns to the selected audit source without opening a current document or repeating the read', async () => {
  const { fixture, requests, navigate } = await setup();
  await fixture.whenStable();
  fixture.detectChanges();
  const back = [
    ...fixture.nativeElement.querySelectorAll('ffk-recorded-document-source button'),
  ].find((button) => button.textContent?.trim() === 'Back to sources') as HTMLButtonElement;
  back.click();
  fixture.detectChanges();
  await fixture.whenStable();
  expect(fixture.componentInstance.tab()).toBe('sources');
  expect(fixture.componentInstance.sourceId()).toBe(source.id);
  expect(
    fixture.nativeElement.querySelector('ffk-recorded-document-source .recorded-content'),
  ).toBeNull();
  expect(navigate).not.toHaveBeenCalled();
  expect(requests.filter((request) => request.path.includes('/versions/'))).toHaveLength(1);
});

it('discards a late historical read when the signed-in context changes', async () => {
  let release!: (value: unknown) => void;
  const pending = new Promise((resolve) => {
    release = resolve;
  });
  const { fixture, facade, requests } = await setup(() => pending);
  await Promise.resolve();
  const read = requests.find((request) => request.path.includes('/versions/'));
  expect(read).toBeTruthy();
  facade.context.set({ subject: 'other-owner' });
  fixture.detectChanges();
  release(part);
  await fixture.whenStable();
  fixture.detectChanges();
  expect(read?.signal?.aborted).toBe(true);
  expect(
    fixture.nativeElement.querySelector('ffk-recorded-document-source .recorded-content'),
  ).toBeNull();
});
