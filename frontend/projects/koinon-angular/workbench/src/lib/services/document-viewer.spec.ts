// Copyright 2026 Firefly Software Foundation
// SPDX-License-Identifier: Apache-2.0
import { TestBed } from '@angular/core/testing';
import { signal } from '@angular/core';
import { KoinonClient, type CatalogEntry, type RequestOptions } from '@fireflyframework/koinon-sdk';
import { KoinonFacade } from '../koinon-facade';
import { KoinonClientContext } from './client-context';
import { KoinonDocumentViewer } from './document-viewer';
const entry = {
  id: 'document',
  tenant_id: 'tenant',
  workspace_id: 'space',
  kind: 'document',
  name: 'Policy.pdf',
  metadata: { latest_version: 'WRONG' },
} as unknown as CatalogEntry;
const text = '<script>Untrusted source</script> — política';
const digest = 'da7fce663a4eda3011466e6f768e6cf88e680580f1cd82c857732400e168868f';
function setup() {
  const context = signal({ subject: 'reader' }),
    revision = signal(0),
    permissions = signal(new Set(['catalog:read']));
  const availability = {
    read: { state: 'ready' },
    phase: 'failed',
    revision: { source_version_id: 'serving-old', extraction_id: 'view-old' },
  };
  const request = vi.fn(
    async (_method: string, path: string, options: RequestOptions = {}): Promise<unknown> => {
      if (path.endsWith('/availability')) return { items: { document: availability } };
      if (path.endsWith('/versions/serving-old'))
        return {
          document_id: 'document',
          source_version_id: 'serving-old',
          filename: 'Policy.pdf',
          media_type: 'application/pdf',
          sha256: digest,
          byte_size: 9,
        };
      if (path.endsWith('/parts'))
        return {
          items: [
            {
              document_id: 'document',
              source_version_id: 'serving-old',
              extraction_id: 'view-old',
              source_part_id: 'part-1',
              kind: 'chunk',
              ordinal: 0,
              sha256: digest,
            },
          ],
          page: options.query?.['page'] || 1,
          pages: 2,
          total: 2,
          has_next: true,
        };
      if (path.endsWith('/parts/part-1'))
        return {
          document_id: 'document',
          source_version_id: 'serving-old',
          extraction_id: 'view-old',
          source_part_id: 'part-1',
          kind: 'chunk',
          sha256: digest,
          text,
        };
      if (path.endsWith('/original'))
        return {
          blob: new Blob(['%PDF-safe'], { type: 'application/pdf' }),
          content_type: 'application/pdf',
          etag: '"' + digest + '"',
          filename: 'Policy.pdf',
          not_modified: false,
        };
      throw Error('Unexpected viewer request: ' + path);
    },
  );
  const transport = { request },
    client = new KoinonClient({ transport: transport as never });
  TestBed.configureTestingModule({
    providers: [
      KoinonDocumentViewer,
      {
        provide: KoinonFacade,
        useValue: {
          context,
          tenantId: signal('tenant'),
          workspaceId: signal('space'),
          projectId: signal('project'),
          authRequired: signal(false),
          permissions,
        },
      },
      {
        provide: KoinonClientContext,
        useValue: { revision, getTransport: () => transport, get: () => client },
      },
    ],
  });
  return {
    state: TestBed.inject(KoinonDocumentViewer),
    context,
    revision,
    permissions,
    request,
    availability,
  };
}
it('uses observed serving pins after failed replacement without eager original or latest reads', async () => {
  const { state, request } = setup();
  await state.open(entry);
  expect(state.version()?.source_version_id).toBe('serving-old');
  expect(state.content()?.text).toBe(text);
  expect(request.mock.calls[0]![2]!.body).toEqual({
    asset_ids: ['document'],
    workspace_id: 'space',
  });
  expect(request.mock.calls.some((c) => /WRONG|\/original$|\/versions$/.test(c[1]))).toBe(false);
});
it('does not read pending content or offer original without read capability', async () => {
  const { state, availability, request } = setup();
  availability.read.state = 'pending';
  await state.open(entry);
  await state.downloadOriginal();
  expect(state.version()).toBeNull();
  expect(request).toHaveBeenCalledOnce();
  expect(state.error()).toContain('not yet available');
});
it('bounds paging and pins every page to the authorized extraction', async () => {
  const { state, request } = setup();
  await state.open(entry);
  await state.loadPage(2);
  const calls = request.mock.calls.filter((c) => c[1].endsWith('/parts'));
  expect(calls[1]![1]).toContain('/versions/serving-old/extractions/view-old/parts');
  expect(calls[1]![2]!.query).toEqual({ page: 2, page_size: 25, kind: 'chunk' });
  await state.loadPage(999);
  expect(request.mock.calls.filter((c) => c[1].endsWith('/parts'))).toHaveLength(2);
});
it('rejects late responses from an old actor', async () => {
  const { state, request, context } = setup();
  let finish!: (value: unknown) => void;
  request.mockImplementationOnce(
    () =>
      new Promise((resolve) => {
        finish = resolve;
      }),
  );
  const reading = state.open(entry);
  context.set({ subject: 'different-reader' });
  TestBed.tick();
  finish({
    items: {
      document: { read: { state: 'ready' }, revision: { source_version_id: 'serving-old' } },
    },
  });
  await reading;
  expect(state.target()).toBeNull();
  expect(state.version()).toBeNull();
  expect(request).toHaveBeenCalledOnce();
});
it('hides cached content immediately after token rotation', async () => {
  const { state, revision } = setup();
  await state.open(entry);
  revision.update((n) => n + 1);
  expect(state.content()).toBeNull();
  expect(state.version()).toBeNull();
});
it('fails closed on mismatched document identity', async () => {
  const { state, request } = setup(),
    native = request.getMockImplementation()!;
  request.mockImplementation(async (m, p, o) =>
    p.endsWith('/versions/serving-old')
      ? { document_id: 'other', source_version_id: 'serving-old' }
      : native(m, p, o),
  );
  await state.open(entry);
  expect(state.version()).toBeNull();
  expect(state.error()).toBeTruthy();
});
it('does not use document APIs for datasets or another tenant', async () => {
  const { state, request } = setup();
  await state.open({ ...entry, kind: 'dataset' });
  await state.open({ ...entry, tenant_id: 'other' });
  expect(request).not.toHaveBeenCalled();
});
it('refuses active HTML as an inline original', async () => {
  const { state, request } = setup();
  await state.open(entry);
  request.mockImplementationOnce(async () => ({
    blob: new Blob(['<html>x</']),
    content_type: 'text/html',
    etag: '"' + digest + '"',
    filename: 'file.html',
  }));
  await state.previewOriginal();
  expect(state.preview()).toBeNull();
  expect(state.error()).toContain('cannot be previewed');
});

it('keeps extracted text readable when the source exceeds the original transfer limit', async () => {
  const { state, request } = setup(),
    native = request.getMockImplementation()!;
  request.mockImplementation(async (m, p, o) =>
    p.endsWith('/versions/serving-old')
      ? {
          document_id: 'document',
          source_version_id: 'serving-old',
          sha256: digest,
          byte_size: 134217729,
          media_type: 'application/pdf',
        }
      : native(m, p, o),
  );
  await state.open(entry);
  expect(state.content()?.text).toBe(text);
  expect(state.version()?.byte_size).toBe(134217729);
  await state.downloadOriginal();
  expect(request.mock.calls.some((c) => c[1].endsWith('/original'))).toBe(false);
  expect(state.error()).toContain('128 MiB');
  expect(state.content()?.text).toBe(text);
});
it('rejects an original whose byte count differs from the pinned version', async () => {
  const { state, request } = setup();
  await state.open(entry);
  request.mockImplementationOnce(async () => ({
    blob: new Blob(['short']),
    content_type: 'application/pdf',
    etag: '"' + digest + '"',
    filename: 'Policy.pdf',
    not_modified: false,
  }));
  await state.previewOriginal();
  expect(state.preview()).toBeNull();
  expect(state.error()).toBeTruthy();
  expect(state.content()?.text).toBe(text);
});
it('accepts native octet-stream only when pinned PDF MIME and signature match', async () => {
  const { state, request } = setup();
  await state.open(entry);
  request.mockImplementationOnce(async () => ({
    blob: new Blob(['%PDF-safe']),
    content_type: 'application/octet-stream',
    etag: '"' + digest + '"',
    filename: 'Policy.pdf',
    not_modified: false,
  }));
  const create = vi.spyOn(URL, 'createObjectURL').mockReturnValue('blob:controlled-original'),
    revoke = vi.spyOn(URL, 'revokeObjectURL').mockImplementation(() => undefined);
  await state.previewOriginal();
  expect(state.preview()?.type).toBe('application/pdf');
  expect(create).toHaveBeenCalledOnce();
  state.close();
  expect(revoke).toHaveBeenCalledWith('blob:controlled-original');
  create.mockRestore();
  revoke.mockRestore();
});
it('does not preview bytes without a matching safe file signature', async () => {
  const { state, request } = setup();
  await state.open(entry);
  request.mockImplementationOnce(async () => ({
    blob: new Blob(['<html>x</']),
    content_type: 'application/octet-stream',
    etag: '"' + digest + '"',
    filename: 'Policy.pdf',
    not_modified: false,
  }));
  await state.previewOriginal();
  expect(state.preview()).toBeNull();
  expect(state.error()).toContain('cannot be previewed');
});

it('rejects an original ETag that does not match the pinned SHA256', async () => {
  const { state, request } = setup();
  await state.open(entry);
  request.mockImplementationOnce(async () => ({
    blob: new Blob(['%PDF-safe']),
    content_type: 'application/octet-stream',
    etag: '"' + 'f'.repeat(64) + '"',
    filename: 'Policy.pdf',
    not_modified: false,
  }));
  await state.previewOriginal();
  expect(state.preview()).toBeNull();
  expect(state.error()).toBeTruthy();
});
it('checks the preview size budget before requesting original bytes', async () => {
  const { state, request } = setup(),
    native = request.getMockImplementation()!;
  request.mockImplementation(async (m, p, o) =>
    p.endsWith('/versions/serving-old')
      ? {
          document_id: 'document',
          source_version_id: 'serving-old',
          sha256: digest,
          byte_size: 16777217,
          media_type: 'application/pdf',
        }
      : native(m, p, o),
  );
  await state.open(entry);
  expect(state.content()?.text).toBe(text);
  expect(state.canPreview()).toBe(false);
  await state.previewOriginal();
  expect(request.mock.calls.some((c) => c[1].endsWith('/original'))).toBe(false);
  expect(state.error()).toContain('16 MiB');
});
