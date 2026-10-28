// Copyright 2026 Firefly Software Foundation
// SPDX-License-Identifier: Apache-2.0
import { Injectable, OnDestroy, effect, inject, signal } from '@angular/core';
import { KoinonClientContext, KoinonFacade } from '@fireflyframework/koinon-angular';
import {
  KoinonError,
  type BinaryDownload,
  type Export,
  type ExportReview,
  type ExportReviewRequest,
  type Share,
  type ShareReview,
  type SharedConversation,
  type MessageSelection,
  type EvidenceManifest,
  type ConversationMessage,
  type SourceReference,
} from '@fireflyframework/koinon-sdk';

@Injectable()
export class KoinonKnowledgeArtifacts implements OnDestroy {
  private readonly clients = inject(KoinonClientContext);
  private readonly facade = inject(KoinonFacade);
  private contextRef = this.facade.context();
  private epoch = 0;
  private key = this.contextKey();
  private controller: AbortController | null = null;
  readonly pending = signal(false);
  readonly error = signal('');
  readonly failureCode = signal('');
  readonly failureStatus = signal<number | null>(null);
  readonly sharedConversation = signal<SharedConversation | null>(null);
  readonly exportReview = signal<ExportReview | null>(null);
  readonly exportRecord = signal<Export | null>(null);
  readonly shareReview = signal<ShareReview | null>(null);
  readonly shareRecord = signal<Share | null>(null);
  readonly manifest = signal<EvidenceManifest | null>(null);
  constructor() {
    effect(() => {
      const key = this.contextKey(),
        context = this.facade.context();
      if (this.key !== key || this.contextRef !== context) this.reset();
    });
  }
  private contextKey() {
    return [
      this.clients.revision(),
      this.facade.context()?.subject ?? '',
      this.facade.tenantId(),
      this.facade.workspaceId(),
      this.facade.projectId(),
      [...this.facade.permissions()].sort().join(','),
      this.facade.authRequired(),
    ].join('|');
  }
  scopeKey() {
    return this.contextKey();
  }
  reset() {
    this.controller?.abort();
    this.controller = null;
    ++this.epoch;
    this.key = this.contextKey();
    this.contextRef = this.facade.context();
    this.pending.set(false);
    this.error.set('');
    this.failureCode.set('');
    this.failureStatus.set(null);
    this.sharedConversation.set(null);
    this.exportReview.set(null);
    this.exportRecord.set(null);
    this.shareReview.set(null);
    this.shareRecord.set(null);
    this.manifest.set(null);
  }
  ngOnDestroy() {
    this.reset();
  }
  private async perform<T>(
    operation: (tenant: string, signal: AbortSignal) => Promise<T>,
    apply: (value: T) => void,
  ): Promise<T | null> {
    if (this.key !== this.contextKey() || this.contextRef !== this.facade.context()) this.reset();
    const tenant = this.facade.tenantId();
    if (!tenant || this.facade.authRequired() || this.pending()) return null;
    const context = this.contextRef,
      epoch = this.epoch,
      key = this.key,
      controller = new AbortController();
    this.controller = controller;
    this.pending.set(true);
    this.error.set('');
    this.failureCode.set('');
    this.failureStatus.set(null);
    try {
      const value = await operation(tenant, controller.signal);
      if (
        epoch !== this.epoch ||
        key !== this.contextKey() ||
        context !== this.facade.context() ||
        controller.signal.aborted
      )
        return null;
      apply(value);
      return value;
    } catch (error) {
      if (
        epoch !== this.epoch ||
        key !== this.contextKey() ||
        context !== this.facade.context() ||
        controller.signal.aborted
      )
        return null;
      if (error instanceof KoinonError && error.status === 401) this.facade.authRequired.set(true);
      this.failureCode.set(error instanceof KoinonError ? error.code : '');
      this.failureStatus.set(error instanceof KoinonError ? error.status : null);
      this.error.set(
        error instanceof Error ? error.message : 'This request could not be completed.',
      );
      if (error instanceof KoinonError && error.status === 409) {
        this.exportReview.set(null);
        this.shareReview.set(null);
      }
      return null;
    } finally {
      if (epoch === this.epoch && key === this.contextKey() && context === this.facade.context()) {
        this.pending.set(false);
        this.controller = null;
      }
    }
  }
  private selectedMessages(
    body: MessageSelection,
    messages: ConversationMessage[] | undefined,
    count: number,
  ) {
    if (
      !Array.isArray(messages) ||
      messages.length !== count ||
      count !== body.message_ids.length ||
      new Set(messages.map((message) => message.id)).size !== count ||
      messages.some(
        (message) => !body.message_ids.includes(message.id) || typeof message.text !== 'string',
      )
    )
      throw Error('The selected messages were not returned for review. Try again.');
  }
  private selectedSources(sources: SourceReference[] | undefined, count: number) {
    if (
      !Array.isArray(sources) ||
      sources.length !== count ||
      new Set(sources.map((source) => source.id)).size !== count
    )
      throw Error('The source review response is incomplete. Try again.');
  }
  reviewExport(body: ExportReviewRequest) {
    if (this.pending()) return Promise.resolve(null);
    this.exportReview.set(null);
    this.exportRecord.set(null);
    return this.perform(
      (tenant, signal) => this.clients.get().exports.review(tenant, body, { signal }),
      (value) => {
        if (
          value.kind !== body.kind ||
          value.format !== body.format ||
          !value.id ||
          !value.revision
        )
          throw Error('The export review response is incomplete.');
        if (body.kind === 'conversation')
          this.selectedMessages(body, value.messages, value.message_count);
        else if (
          !value.result ||
          value.result.byte_size <= 0 ||
          value.result.query_id !== body.query_id ||
          value.result.asset_id !== body.dataset_id
        )
          throw Error('The stored result review response is incomplete.');
        this.selectedSources(value.sources, value.source_count);
        this.exportReview.set(value);
      },
    );
  }
  createExport() {
    const review = this.exportReview();
    if (!review) return Promise.resolve(null);
    return this.perform(
      (tenant, signal) =>
        this.clients
          .get()
          .exports.create(
            tenant,
            { review_id: review.id, expected_revision: review.revision },
            { signal },
          ),
      (value) => {
        this.exportRecord.set(value);
        this.exportReview.set(null);
      },
    );
  }
  downloadExport(): Promise<BinaryDownload | null> {
    const record = this.exportRecord();
    if (!record || record.status !== 'ready') return Promise.resolve(null);
    return this.perform(
      (tenant, signal) => this.clients.get().exports.download(tenant, record.id, { signal }),
      () => undefined,
    );
  }
  cancelExport() {
    const record = this.exportRecord();
    if (!record) return Promise.resolve(null);
    return this.perform(
      (tenant, signal) => this.clients.get().exports.cancel(tenant, record.id, { signal }),
      () => this.exportRecord.set({ ...record, status: 'cancelled' }),
    );
  }
  reviewShare(body: MessageSelection) {
    if (this.pending()) return Promise.resolve(null);
    this.shareReview.set(null);
    this.shareRecord.set(null);
    return this.perform(
      (tenant, signal) => this.clients.get().shares.review(tenant, body, { signal }),
      (value) => {
        this.selectedMessages(body, value.messages, value.message_count);
        this.selectedSources(value.sources, value.source_count);
        if (
          !value.source_manifest_complete ||
          value.messages.some((message) => message.private_derived)
        )
          throw Error('This selection cannot be shared safely. Review its source provenance.');
        this.shareReview.set(value);
      },
    );
  }
  createShare(hours: number) {
    const review = this.shareReview();
    if (!review) return Promise.resolve(null);
    return this.perform(
      (tenant, signal) =>
        this.clients.get().shares.create(
          tenant,
          {
            review_id: review.id,
            expected_revision: review.revision,
            expires_in_hours: hours,
            recipient_policy: 'organization_current_acl',
          },
          { signal },
        ),
      (value) => {
        this.shareRecord.set(value);
        this.shareReview.set(null);
      },
    );
  }
  revokeShare() {
    const record = this.shareRecord();
    if (!record) return Promise.resolve(null);
    return this.perform(
      (tenant, signal) => this.clients.get().shares.revoke(tenant, record.id, { signal }),
      () => this.shareRecord.set({ ...record, status: 'revoked' }),
    );
  }
  readShare(identifier: string) {
    this.sharedConversation.set(null);
    return this.perform(
      (tenant, signal) => this.clients.get().shares.get(tenant, identifier, { signal }),
      (value) => {
        if (
          value.share.id !== identifier ||
          !Array.isArray(value.messages) ||
          !Array.isArray(value.sources)
        )
          throw Error('The shared snapshot response is incomplete. Try again.');
        this.sharedConversation.set(value);
      },
    );
  }
  sources(body: MessageSelection) {
    if (this.pending()) return Promise.resolve(null);
    this.manifest.set(null);
    return this.perform(
      (tenant, signal) => this.clients.get().evidence.conversation(tenant, body, { signal }),
      (value) => this.manifest.set(value),
    );
  }
}
