// Copyright 2026 Firefly Software Foundation
// SPDX-License-Identifier: Apache-2.0
import { Injectable, OnDestroy, computed, effect, inject, signal } from '@angular/core';
import { KoinonClientContext, KoinonFacade } from '@fireflyframework/koinon-angular';
import {
  KoinonError,
  type KnowledgeIntent,
  type KnowledgeIntentInput,
  type KnowledgeCommitReceipt,
} from '@fireflyframework/koinon-sdk';
import type { ConversationSelection } from './artifact-selections';
import { canCurateKnowledge } from './knowledge-permissions';

type Stage = 'edit' | 'review' | 'pending' | 'saved' | 'cancelled';
type Operation = 'preview' | 'confirm' | 'refresh' | 'cancel';

@Injectable()
export class KoinonKnowledgeIntents implements OnDestroy {
  private readonly clients = inject(KoinonClientContext);
  private readonly facade = inject(KoinonFacade);
  private epoch = 0;
  private controller?: AbortController;
  private readonly selection = signal<ConversationSelection | null>(null);
  private seed = '';
  private readonly workspace = signal('');
  private key = this.scopeKey();
  private context = this.facade.context();
  private confirmationKey = '';
  readonly title = signal('');
  readonly body = signal('');
  readonly destination = signal('');
  readonly publication = signal<'draft' | 'published'>('draft');
  readonly consent = signal(false);
  readonly stage = signal<Stage>('edit');
  readonly pending = signal(false);
  readonly error = signal('');
  readonly intent = signal<KnowledgeIntent | null>(null);
  readonly receipt = signal<KnowledgeCommitReceipt | null>(null);
  readonly canWrite = computed(() => canCurateKnowledge(this.facade, this.workspace() || this.facade.workspaceId()));
  readonly canPreview = computed(() => Boolean(
    this.selection() && this.stage() === 'edit' && this.canWrite() && !this.pending() && this.destination() &&
    this.title().trim() && Array.from(this.title().trim()).length <= 255 &&
    this.body().trim() && new TextEncoder().encode(this.body().trim()).length <= 262144,
  ));
  readonly canConfirm = computed(() => Boolean(
    this.key === this.scopeKey() && this.context === this.facade.context() &&
    this.stage() === 'review' && this.intent()?.status === 'preview' && this.canWrite() &&
    !this.pending() && (!this.intent()?.remembered_context_present || this.consent()),
  ));
  constructor() {
    effect(() => {
      if (this.key !== this.scopeKey() || this.context !== this.facade.context()) this.reset();
    });
  }
  scopeKey() {
    return JSON.stringify([
      this.clients.revision(), this.facade.context()?.subject, this.facade.tenantId(),
      this.facade.workspaceId(), this.facade.projectId(),
      [...this.facade.permissions()].sort(), this.facade.authRequired(),
    ]);
  }
  reset() {
    this.controller?.abort();
    this.controller = undefined;
    ++this.epoch;
    this.selection.set(null);
    this.seed = '';
    this.workspace.set('');
    this.confirmationKey = '';
    this.key = this.scopeKey();
    this.context = this.facade.context();
    this.title.set('');
    this.body.set('');
    this.destination.set('');
    this.publication.set('draft');
    this.consent.set(false);
    this.stage.set('edit');
    this.pending.set(false);
    this.error.set('');
    this.intent.set(null);
    this.receipt.set(null);
  }
  configure(selection: ConversationSelection, text: string, workspaceId = '') {
    if (this.stage() === 'pending' && this.key === this.scopeKey() &&
        this.context === this.facade.context() && this.seed === text && this.workspace() === workspaceId &&
        this.selection()?.thread_id === selection.thread_id &&
        this.selection()?.message_ids[0] === selection.message_ids[0]) return;
    this.reset();
    if (!selection.thread_id || selection.message_ids.length !== 1 || !selection.message_ids[0]) return;
    this.selection.set({ thread_id: selection.thread_id, message_ids: [...selection.message_ids] });
    this.seed = text;
    this.workspace.set(workspaceId);
    this.body.set(text);
    const folder = this.facade.entries().find((entry) => entry.id === this.facade.parentId());
    if (folder && ['collection', 'corpus'].includes(folder.kind) && folder.status !== 'archived')
      this.destination.set(folder.id);
  }
  suspend() {
    this.controller?.abort();
    this.controller = undefined;
    ++this.epoch;
    this.pending.set(false);
    this.consent.set(false);
    if (this.stage() !== 'pending') this.reset();
  }
  edit() {
    if (this.pending() || this.stage() === 'pending') return;
    this.intent.set(null);
    this.receipt.set(null);
    this.consent.set(false);
    this.confirmationKey = '';
    this.error.set('');
    this.stage.set('edit');
  }
  private valid(value: KnowledgeIntent, previous?: KnowledgeIntent) {
    if (!value.id || value.tenant_id !== this.facade.tenantId() ||
        value.owner_subject !== this.facade.context()?.subject ||
        !Number.isSafeInteger(value.revision) || value.revision < 1 ||
        !/^[a-f0-9]{64}$/.test(value.authorization_digest) || !value.target_item_id ||
        !['create_draft', 'create_published'].includes(value.action) ||
        !value.after?.title?.trim() || !value.after.body?.trim() || !value.destination?.id ||
        !Array.isArray(value.evidence) || !value.evidence.length ||
        !Number.isFinite(Date.parse(value.expires_at)) ||
        previous && (value.id !== previous.id || value.target_item_id !== previous.target_item_id ||
          value.destination.id !== previous.destination.id || value.action !== previous.action))
      throw Error('The review response did not match this proposal. Review it again.');
    return value;
  }
  private checkedReceipt(value: KnowledgeCommitReceipt, review: KnowledgeIntent) {
    if (value.intent_id !== review.id || value.intent_revision !== review.revision ||
        value.authorization_digest !== review.authorization_digest ||
        value.item_id !== review.target_item_id || value.action !== review.action ||
        !Number.isSafeInteger(value.version) || value.version < 1 ||
        (review.action === 'create_draft' ? value.serving_version != null : value.serving_version !== value.version))
      throw Error('The saved outcome could not be verified. Check its status.');
    return value;
  }
  private async perform<T>(operation: Operation, run: (tenant: string, signal: AbortSignal) => Promise<T>, apply: (value: T) => void) {
    if (!this.canWrite() || this.pending() || !this.selection() || this.key !== this.scopeKey() ||
        this.context !== this.facade.context()) return null;
    const epoch = this.epoch, key = this.key, context = this.context, selection = this.selection();
    const controller = new AbortController();
    this.controller = controller;
    this.pending.set(true);
    this.error.set('');
    const current = () => epoch === this.epoch && key === this.scopeKey() &&
      context === this.facade.context() && selection === this.selection() && !controller.signal.aborted;
    try {
      const value = await run(this.facade.tenantId(), controller.signal);
      if (!current()) return null;
      apply(value);
      return value;
    } catch (error) {
      if (!current()) return null;
      this.consent.set(false);
      if (error instanceof KoinonError && [401, 403, 409].includes(error.status)) {
        this.intent.set(null);
        this.stage.set('edit');
        this.confirmationKey = '';
        if (error.status === 401) this.facade.authRequired.set(true);
        this.error.set(error.status === 409
          ? 'This review changed or expired. Review the proposal again before confirming.'
          : 'Your current access does not allow this proposal. Check your organization and permissions.');
      } else {
        if (operation === 'confirm' || operation === 'cancel') this.stage.set('pending');
        this.error.set(operation === 'confirm' || operation === 'cancel'
          ? 'The decision could not be verified. Check its status before continuing.'
          : error instanceof Error ? error.message : 'The proposal could not be reviewed. Try again.');
      }
      return null;
    } finally {
      if (current()) { this.pending.set(false); this.controller = undefined; }
    }
  }
  preview() {
    const selection = this.selection();
    if (!this.canPreview() || !selection) return Promise.resolve(null);
    const input: KnowledgeIntentInput = {
      action: this.publication() === 'published' ? 'create_published' : 'create_draft',
      destination_id: this.destination(),
      content: { title: this.title().trim(), body: this.body().trim() },
      origin: { kind: 'conversation', thread_id: selection.thread_id, message_ids: [...selection.message_ids] },
    };
    this.intent.set(null);
    this.receipt.set(null);
    this.consent.set(false);
    return this.perform('preview', (tenant, signal) => this.clients.get().knowledgeIntents.preview(tenant, input, { signal }), (raw) => {
      const value = this.valid(raw);
      if (value.status !== 'preview' || value.action !== input.action ||
          value.destination.id !== input.destination_id || value.after.title !== input.content.title ||
          value.after.body !== input.content.body)
        throw Error('The review response did not match this proposal. Review it again.');
      this.intent.set(value);
      this.confirmationKey = crypto.randomUUID();
      this.stage.set('review');
    });
  }
  confirm() {
    const review = this.intent();
    if (!review || !this.canConfirm()) return Promise.resolve(null);
    if (Date.parse(review.expires_at) <= Date.now()) {
      this.edit(); this.error.set('This review expired. Review the proposal again.');
      return Promise.resolve(null);
    }
    const consent = this.consent();
    this.stage.set('pending');
    return this.perform('confirm', (tenant, signal) => this.clients.get().knowledgeIntents.confirm(tenant, review.id, {
      confirm: true, expected_revision: review.revision, authorization_digest: review.authorization_digest,
      ...(review.remembered_context_present && consent ? { include_remembered_context: true } : {}),
    }, this.confirmationKey, { signal }), (outcome) => {
      if ('receipt' in outcome) {
        this.receipt.set(this.checkedReceipt(outcome.receipt, review));
        this.stage.set('saved');
      } else if (outcome.intent_id !== review.id || !outcome.operation_id)
        throw Error('The saved outcome could not be verified. Check its status.');
    });
  }
  refresh() {
    const review = this.intent();
    if (!review || this.stage() !== 'pending') return Promise.resolve(null);
    this.consent.set(false);
    return this.perform('refresh', (tenant, signal) => this.clients.get().knowledgeIntents.get(tenant, review.id, { signal }), (raw) => {
      const value = this.valid(raw, review);
      this.intent.set(value);
      if (value.status === 'committed' && value.receipt) {
        this.receipt.set(this.checkedReceipt(value.receipt, value));
        this.stage.set('saved');
      } else if (value.status === 'preview') {
        if (value.revision !== review.revision || value.authorization_digest !== review.authorization_digest)
          this.confirmationKey = crypto.randomUUID();
        this.stage.set('review');
      } else if (value.status === 'cancelled') this.stage.set('cancelled');
      else if (value.status === 'stale') {
        this.edit(); this.error.set('This review changed or expired. Review the proposal again before confirming.');
      } else if (!['committing', 'unresolved'].includes(value.status))
        throw Error('The saved outcome could not be verified. Check its status.');
    });
  }
  cancel() {
    const review = this.intent();
    if (!review || this.stage() !== 'review') return Promise.resolve(null);
    this.consent.set(false);
    return this.perform('cancel', (tenant, signal) => this.clients.get().knowledgeIntents.cancel(tenant, review.id, review.revision, { signal }), (raw) => {
      const value = this.valid(raw, review);
      if (value.status !== 'cancelled' || value.revision !== review.revision + 1)
        throw Error('The decision could not be verified. Check its status before continuing.');
      this.intent.set(value);
      this.stage.set('cancelled');
    });
  }
  ngOnDestroy() { this.reset(); }
}
