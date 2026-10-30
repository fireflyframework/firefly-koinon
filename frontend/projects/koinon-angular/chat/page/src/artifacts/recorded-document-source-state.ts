// Copyright 2026 Firefly Software Foundation
// SPDX-License-Identifier: Apache-2.0
import { Injectable, OnDestroy, effect, inject, signal } from '@angular/core';
import { KoinonClientContext, KoinonFacade } from '@fireflyframework/koinon-angular';
import {
  KoinonError,
  type DocumentPartContent,
  type SourceReference,
} from '@fireflyframework/koinon-sdk';

export function hasRecordedDocumentIdentity(source: SourceReference) {
  return (
    source.kind === 'document' &&
    !!(
      source.source_version_id ||
      source.extraction_id ||
      source.source_part_id ||
      source.source_part_sha256 ||
      source.page_basis ||
      source.recorded_page != null ||
      source.used_revision?.startsWith('source-part-sha256:')
    )
  );
}

@Injectable()
export class KoinonRecordedDocumentSourceState implements OnDestroy {
  private readonly clients = inject(KoinonClientContext);
  private readonly facade = inject(KoinonFacade);
  private context = this.facade.context();
  private key = this.scopeKey();
  private epoch = 0;
  private controller: AbortController | null = null;
  readonly source = signal<SourceReference | null>(null);
  readonly content = signal<DocumentPartContent | null>(null);
  readonly pending = signal(false);
  readonly error = signal('');

  constructor() {
    effect(() => {
      if (this.key !== this.scopeKey() || this.context !== this.facade.context()) this.clear();
    });
  }
  private scopeKey() {
    return [
      this.clients.revision(),
      this.facade.context()?.subject ?? '',
      this.facade.tenantId(),
      this.facade.workspaceId(),
      this.facade.projectId(),
      this.facade.authRequired(),
      [...this.facade.permissions()].sort().join(','),
    ].join('|');
  }
  clear() {
    this.controller?.abort();
    this.controller = null;
    ++this.epoch;
    this.context = this.facade.context();
    this.key = this.scopeKey();
    this.source.set(null);
    this.content.set(null);
    this.pending.set(false);
    this.error.set('');
  }
  ngOnDestroy() {
    this.clear();
  }

  async open(reference: SourceReference) {
    this.clear();
    const source = Object.freeze({ ...reference });
    this.source.set(source);
    if (
      source.kind !== 'document' ||
      !source.asset_id ||
      !source.source_version_id ||
      !source.extraction_id ||
      !source.source_part_id ||
      !source.source_part_sha256 ||
      !/^[a-f0-9]{64}$/.test(source.source_part_sha256) ||
      source.page_basis !== 'recorded_loader' ||
      source.used_revision !== 'source-part-sha256:' + source.source_part_sha256
    ) {
      this.error.set('The recorded source identity is incomplete.');
      return;
    }
    const tenant = this.facade.tenantId();
    if (!tenant || this.facade.authRequired() || !this.facade.permissions().has('catalog:read')) {
      this.error.set('Your current access does not allow opening this source.');
      return;
    }
    const controller = new AbortController(),
      epoch = this.epoch;
    const current = () =>
      epoch === this.epoch &&
      !controller.signal.aborted &&
      this.context === this.facade.context() &&
      this.key === this.scopeKey();
    this.controller = controller;
    this.pending.set(true);
    try {
      const value = await this.clients
        .get()
        .documents.part(
          tenant,
          source.asset_id,
          source.source_version_id,
          source.extraction_id,
          source.source_part_id,
          { signal: controller.signal },
        );
      if (!current()) return;
      const bytes = typeof value.text === 'string' ? new TextEncoder().encode(value.text) : null;
      if (
        value.document_id !== source.asset_id ||
        (source.source_id && value.catalog_source_id !== source.source_id) ||
        value.source_version_id !== source.source_version_id ||
        value.extraction_id !== source.extraction_id ||
        value.source_part_id !== source.source_part_id ||
        value.sha256 !== source.source_part_sha256 ||
        !['chunk', 'page'].includes(value.kind) ||
        value.page_basis !== source.page_basis ||
        (source.recorded_page != null && value.recorded_page !== source.recorded_page) ||
        !bytes ||
        bytes.byteLength > 1048576 ||
        (source.quote && !value.text.includes(source.quote))
      )
        throw Error('The source does not match the recorded answer.');
      const digest = Array.from(new Uint8Array(await crypto.subtle.digest('SHA-256', bytes)))
        .map((value) => value.toString(16).padStart(2, '0'))
        .join('');
      if (!current()) return;
      if (digest !== source.source_part_sha256)
        throw Error('The source does not match the recorded answer.');
      this.content.set(value);
    } catch (error) {
      if (!current()) return;
      if (error instanceof KoinonError && error.status === 401) this.facade.authRequired.set(true);
      this.error.set(
        error instanceof KoinonError && error.status === 403
          ? 'Your current access does not allow opening this source.'
          : error instanceof KoinonError && error.status === 404
            ? 'The recorded source is no longer available.'
            : error instanceof Error &&
                error.message === 'The source does not match the recorded answer.'
              ? error.message
              : 'The recorded source could not be loaded. Try again.',
      );
    } finally {
      if (current()) this.pending.set(false);
    }
  }
}
