// Copyright 2026 Firefly Software Foundation
// SPDX-License-Identifier: Apache-2.0
import { Injectable, DestroyRef, computed, effect, inject, signal, untracked } from '@angular/core';
import type {
  CatalogEntry,
  ContextResponse,
  DocumentVersion,
  DocumentPartPage,
  DocumentPartContent,
  DocumentPartSummary,
  BinaryDownload,
} from '@fireflyframework/koinon-sdk';
import { createAvailabilityApi } from '@fireflyframework/koinon-sdk/availability';
import { KoinonFacade } from '@fireflyframework/koinon-angular/workbench/core';
import { KoinonClientContext } from '@fireflyframework/koinon-angular/workbench/core';
interface Selection {
  entry: CatalogEntry;
  key: string;
  context: ContextResponse | null;
}
const maxOriginalBytes = 128 * 1024 * 1024;
const maxInlineBytes = 16 * 1024 * 1024;
const inlineTypes = new Set([
  'application/pdf',
  'image/png',
  'image/jpeg',
  'image/webp',
  'image/gif',
]);
@Injectable()
export class KoinonDocumentViewer {
  private readonly facade = inject(KoinonFacade);
  private readonly clients = inject(KoinonClientContext);
  private readonly selected = signal<Selection | null>(null);
  private readonly identity = computed(() =>
    JSON.stringify([
      this.clients.revision(),
      this.facade.tenantId(),
      this.facade.workspaceId(),
      this.facade.projectId(),
      this.facade.context()?.subject,
      this.facade.authRequired(),
      [...this.facade.permissions()].sort(),
    ]),
  );
  private readonly observedVersion = signal<DocumentVersion | null>(null);
  private readonly observedParts = signal<DocumentPartPage | null>(null);
  private readonly observedContent = signal<DocumentPartContent | null>(null);
  private readonly observedPreview = signal<{ url: string; type: string } | null>(null);
  private readonly failure = signal('');
  private readonly loading = signal(false);
  private sequence = 0;
  private controller?: AbortController;
  private extraction = '';
  readonly target = computed(() => (this.current() ? this.selected()!.entry : null));
  readonly version = computed(() => (this.current() ? this.observedVersion() : null));
  readonly parts = computed(() => (this.current() ? this.observedParts() : null));
  readonly content = computed(() => (this.current() ? this.observedContent() : null));
  readonly preview = computed(() => (this.current() ? this.observedPreview() : null));
  readonly error = computed(() => (this.current() ? this.failure() : ''));
  readonly pending = computed(() => this.current() && this.loading());
  readonly transferLimited = computed(() => (this.version()?.byte_size ?? 0) > maxOriginalBytes);
  readonly canDownload = computed(() => !!this.version() && !this.transferLimited());
  readonly canPreview = computed(
    () =>
      inlineTypes.has(this.version()?.media_type?.toLowerCase() ?? '') &&
      (this.version()?.byte_size ?? Infinity) <= maxInlineBytes,
  );
  constructor() {
    effect(() => {
      this.identity();
      this.facade.context();
      if (untracked(this.selected) && !this.current()) untracked(() => this.close());
    });
    inject(DestroyRef).onDestroy(() => this.close());
  }
  private current() {
    const s = this.selected();
    return (
      !!s &&
      s.key === this.identity() &&
      s.context === this.facade.context() &&
      !!s.context?.subject &&
      !this.facade.authRequired() &&
      this.facade.permissions().has('catalog:read')
    );
  }
  private cancel() {
    ++this.sequence;
    this.controller?.abort();
    this.loading.set(false);
  }
  close() {
    this.cancel();
    this.clearPreview();
    this.selected.set(null);
    this.observedVersion.set(null);
    this.observedParts.set(null);
    this.observedContent.set(null);
    this.failure.set('');
    this.extraction = '';
  }
  clearPreview() {
    const value = this.observedPreview();
    if (value) URL.revokeObjectURL(value.url);
    this.observedPreview.set(null);
  }
  async open(entry: CatalogEntry) {
    this.close();
    if (
      entry.kind !== 'document' ||
      entry.tenant_id !== this.facade.tenantId() ||
      (this.facade.workspaceId() && entry.workspace_id !== this.facade.workspaceId())
    )
      return;
    this.selected.set({
      entry: { ...entry },
      key: this.identity(),
      context: this.facade.context(),
    });
    await this.read(async (signal, current) => {
      const transport = this.clients.getTransport();
      if (!transport) throw Error();
      const result = await createAvailabilityApi(transport).observe(
        this.facade.tenantId(),
        {
          asset_ids: [entry.id],
          ...(entry.workspace_id ? { workspace_id: entry.workspace_id } : {}),
        },
        { signal },
      );
      if (!current()) return;
      const value = result.items[entry.id],
        versionId = value?.revision?.source_version_id;
      if (value?.read?.state !== 'ready' || !versionId) {
        this.failure.set(
          'This document is not yet available to read. Inspect its processing status and try again.',
        );
        return;
      }
      const version = await this.clients
        .get()
        .documents.version(this.facade.tenantId(), entry.id, versionId, { signal });
      if (!current()) return;
      if (
        version.document_id !== entry.id ||
        version.source_version_id !== versionId ||
        !Number.isSafeInteger(version.byte_size) ||
        version.byte_size < 0 ||
        !/^[a-f0-9]{64}$/.test(version.sha256)
      )
        throw Error();
      this.observedVersion.set(version);
      this.extraction = value.revision?.extraction_id ?? '';
      if (this.extraction) await this.readParts(1, signal, current);
    });
  }
  private async readParts(page: number, signal: AbortSignal, current: () => boolean) {
    const entry = this.target(),
      version = this.version();
    if (!entry || !version || !this.extraction) return;
    const result = await this.clients
      .get()
      .documents.parts(
        this.facade.tenantId(),
        entry.id,
        version.source_version_id,
        this.extraction,
        { page, page_size: 25, kind: 'chunk' },
        { signal },
      );
    if (!current()) return;
    if (
      result.page !== page ||
      result.items.length > 25 ||
      !Number.isSafeInteger(result.total) ||
      result.total < 0 ||
      result.pages < 0 ||
      result.items.some(
        (p) =>
          p.document_id !== entry.id ||
          p.source_version_id !== version.source_version_id ||
          p.extraction_id !== this.extraction ||
          p.kind !== 'chunk' ||
          !/^[a-f0-9]{64}$/.test(p.sha256),
      )
    )
      throw Error();
    this.observedParts.set(result);
    this.observedContent.set(null);
    if (result.items[0]) await this.readPart(result.items[0], signal, current);
  }
  async loadPage(page: number) {
    if (this.pending() || !Number.isInteger(page) || page < 1 || page > (this.parts()?.pages ?? 0))
      return;
    this.clearPreview();
    await this.read((signal, current) => this.readParts(page, signal, current));
  }
  async selectPart(part: DocumentPartSummary) {
    if (
      this.pending() ||
      !this.parts()?.items.some(
        (p) => p.source_part_id === part.source_part_id && p.sha256 === part.sha256,
      )
    )
      return;
    this.clearPreview();
    this.observedContent.set(null);
    await this.read((signal, current) => this.readPart(part, signal, current));
  }
  private async readPart(part: DocumentPartSummary, signal: AbortSignal, current: () => boolean) {
    const entry = this.target(),
      version = this.version();
    if (!entry || !version) return;
    const value = await this.clients
      .get()
      .documents.part(
        this.facade.tenantId(),
        entry.id,
        version.source_version_id,
        this.extraction,
        part.source_part_id,
        { signal },
      );
    if (!current()) return;
    if (
      value.document_id !== entry.id ||
      value.source_version_id !== version.source_version_id ||
      value.extraction_id !== this.extraction ||
      value.source_part_id !== part.source_part_id ||
      value.sha256 !== part.sha256 ||
      value.kind !== 'chunk' ||
      typeof value.text !== 'string'
    )
      throw Error();
    const bytes = new TextEncoder().encode(value.text);
    if (bytes.byteLength > 1048576) throw Error();
    const hash = Array.from(new Uint8Array(await crypto.subtle.digest('SHA-256', bytes)))
      .map((n) => n.toString(16).padStart(2, '0'))
      .join('');
    if (!current()) return;
    if (hash !== part.sha256) throw Error();
    this.observedContent.set(value);
  }
  async previewOriginal() {
    await this.original(true);
  }
  async downloadOriginal() {
    await this.original(false);
  }
  private async original(preview: boolean) {
    if (this.pending() || !this.current() || !this.version()) return;
    if (this.transferLimited()) {
      this.failure.set(
        'This original exceeds the 128 MiB download limit. Its extracted text remains readable. Contact your administrator for an approved transfer.',
      );
      return;
    }
    if (preview && this.version()!.byte_size > maxInlineBytes) {
      this.failure.set(
        'This original exceeds the 16 MiB preview limit. Download it to open it with a compatible application.',
      );
      return;
    }
    await this.read(async (signal, current) => {
      const version = this.version()!,
        entry = this.target()!;
      const value: BinaryDownload = await this.clients
        .get()
        .documents.versionOriginal(this.facade.tenantId(), entry.id, version.source_version_id, {
          signal,
        });
      if (!current()) return;
      const servedType = (value.content_type ?? '').split(';')[0]!.trim().toLowerCase();
      const type = (version.media_type ?? '').toLowerCase();
      if (
        value.not_modified ||
        value.blob.size !== version.byte_size ||
        value.blob.size > maxOriginalBytes ||
        value.etag !== '"' + version.sha256 + '"'
      )
        throw Error();
      if (
        preview &&
        (!inlineTypes.has(type) ||
          (servedType !== 'application/octet-stream' && servedType !== type) ||
          value.blob.size > maxInlineBytes)
      ) {
        this.failure.set(
          'This file type cannot be previewed here. Download the original to open it with a compatible application.',
        );
        return;
      }
      if (
        preview &&
        !this.signature(type, new Uint8Array(await value.blob.slice(0, 16).arrayBuffer()))
      ) {
        if (current())
          this.failure.set(
            'This file type cannot be previewed here. Download the original to open it with a compatible application.',
          );
        return;
      }
      if (!current()) return;
      if (preview) this.clearPreview();
      const url = URL.createObjectURL(value.blob.slice(0, value.blob.size, type));
      if (preview) this.observedPreview.set({ url, type });
      else {
        const a = document.createElement('a');
        a.href = url;
        a.download = value.filename || version.filename || entry.name;
        a.click();
        setTimeout(() => URL.revokeObjectURL(url), 0);
      }
    });
  }
  private signature(type: string, bytes: Uint8Array) {
    const ascii = (start: number, end: number) => String.fromCharCode(...bytes.slice(start, end));
    if (type === 'application/pdf') return ascii(0, 5) === '%PDF-';
    if (type === 'image/png')
      return [137, 80, 78, 71, 13, 10, 26, 10].every((value, index) => bytes[index] === value);
    if (type === 'image/jpeg') return bytes[0] === 255 && bytes[1] === 216 && bytes[2] === 255;
    if (type === 'image/gif') return ['GIF87a', 'GIF89a'].includes(ascii(0, 6));
    return type === 'image/webp' && ascii(0, 4) === 'RIFF' && ascii(8, 12) === 'WEBP';
  }
  private async read(work: (signal: AbortSignal, current: () => boolean) => Promise<void>) {
    if (!this.current()) return;
    this.cancel();
    const sequence = this.sequence,
      controller = new AbortController();
    this.controller = controller;
    this.loading.set(true);
    this.failure.set('');
    const current = () =>
      sequence === this.sequence && !controller.signal.aborted && this.current();
    try {
      await work(controller.signal, current);
    } catch (error) {
      if (!current()) return;
      const status = error && typeof error === 'object' && 'status' in error ? error.status : null;
      if (status === 401 || status === 403) {
        this.observedVersion.set(null);
        this.observedParts.set(null);
        this.observedContent.set(null);
        this.clearPreview();
      }
      this.failure.set(
        status === 401 || status === 403
          ? 'Your current access does not allow opening this document.'
          : 'The document could not be opened. Close it and try again.',
      );
    } finally {
      if (current()) this.loading.set(false);
    }
  }
}
