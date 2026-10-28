// Copyright 2026 Firefly Software Foundation
// SPDX-License-Identifier: Apache-2.0
import { Injectable, OnDestroy, computed, effect, inject, signal } from '@angular/core';
import { KoinonClientContext, KoinonFacade } from '@fireflyframework/koinon-angular';
import {
  KoinonError,
  type AnswerAudit,
  type ChatMessage,
  type EvidenceManifest,
  type EvidenceResult,
  type OpenUIArtifact,
  type Page,
  type ToolActivity,
} from '@fireflyframework/koinon-sdk';
import type { EvidenceResolver } from '@fireflyframework/koinon-angular/chat/evidence';
interface AuditSelection {
  threadId: string;
  messageId: string;
  runId: string;
  final: boolean;
}
@Injectable()
export class KoinonAnswerAuditState implements OnDestroy {
  private readonly clients = inject(KoinonClientContext);
  private readonly facade = inject(KoinonFacade);
  private boundContext = this.facade.context();
  private selection: AuditSelection | null = null;
  private scope = '';
  private epoch = 0;
  private resultVersion = 0;
  private auditAbort: AbortController | null = null;
  private activityAbort: AbortController | null = null;
  private manifestAbort: AbortController | null = null;
  private resultAbort: AbortController | null = null;
  readonly audit = signal<AnswerAudit | null>(null);
  readonly auditPending = signal(false);
  readonly auditError = signal('');
  readonly sources = computed(() => {
    const audit = this.audit(),
      manifest = this.manifest();
    return this.selection?.runId ? (audit?.sources ?? []) : (manifest?.sources ?? []);
  });
  readonly activity = signal<Page<ToolActivity> | null>(null);
  readonly activityPending = signal(false);
  readonly activityError = signal('');
  readonly manifest = signal<EvidenceManifest | null>(null);
  readonly manifestPending = signal(false);
  readonly manifestError = signal('');
  readonly selected = signal<ToolActivity | null>(null);
  readonly result = signal<EvidenceResult | null>(null);
  readonly resultPending = signal(false);
  readonly resultError = signal('');
  readonly contextKey = signal('');
  readonly canReadSources = computed(
    () => !this.facade.authRequired() && this.facade.permissions().has('evidence:read'),
  );
  readonly artifact = computed<OpenUIArtifact | null>(() => {
    const row = this.selected(),
      runId = this.selection?.runId;
    if (!row?.result_id || !runId) return null;
    return {
      id: 'audit-' + row.call_id,
      kind: 'openui',
      run_id: runId,
      complete: true,
      language:
        'root = KnowledgeAnswer([evidence])\nevidence = Evidence(' +
        JSON.stringify(row.result_id) +
        ', "auto")',
    };
  });
  constructor() {
    effect(() => {
      const key = this.scopeKey(),
        context = this.facade.context();
      if (this.scope && (this.scope !== key || this.boundContext !== context)) this.clear();
    });
  }
  scopeKey() {
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
  contextSnapshot() {
    return this.facade.context();
  }
  private current(epoch: number, controller: AbortController) {
    return (
      epoch === this.epoch &&
      this.boundContext === this.facade.context() &&
      this.scope === this.scopeKey() &&
      !controller.signal.aborted
    );
  }
  clear() {
    this.auditAbort?.abort();
    this.activityAbort?.abort();
    this.manifestAbort?.abort();
    this.resultAbort?.abort();
    ++this.epoch;
    this.selection = null;
    this.scope = '';
    this.boundContext = this.facade.context();
    this.audit.set(null);
    this.auditPending.set(false);
    this.auditError.set('');
    this.activity.set(null);
    this.manifest.set(null);
    this.selected.set(null);
    this.result.set(null);
    this.activityPending.set(false);
    this.manifestPending.set(false);
    this.resultPending.set(false);
    this.activityError.set('');
    this.manifestError.set('');
    this.resultError.set('');
    this.contextKey.set('');
  }
  ngOnDestroy() {
    this.clear();
  }
  async open(threadId: string, message: ChatMessage) {
    this.clear();
    if (!threadId || !message.id || !this.facade.tenantId() || this.facade.authRequired()) return;
    this.scope = this.scopeKey();
    this.selection = {
      threadId,
      messageId: message.id,
      runId: message.run_id ?? '',
      final: ['completed', 'failed', 'cancelled'].includes(message.status),
    };
    this.contextKey.set(
      this.scope +
        '|' +
        threadId +
        '|' +
        message.id +
        '|' +
        this.selection.runId +
        '|' +
        this.epoch,
    );
    if (this.selection.runId) await Promise.all([this.loadAudit(), this.loadActivity(1)]);
    else await this.loadManifest();
  }
  private failure(error: unknown, fallback: string) {
    if (error instanceof KoinonError && error.status === 401) this.facade.authRequired.set(true);
    return error instanceof Error ? error.message : fallback;
  }
  async loadAudit() {
    const selection = this.selection,
      tenant = this.facade.tenantId();
    if (
      !selection?.runId ||
      !tenant ||
      this.facade.authRequired() ||
      this.scope !== this.scopeKey() ||
      this.boundContext !== this.facade.context()
    )
      return;
    this.auditAbort?.abort();
    const controller = new AbortController(),
      epoch = this.epoch;
    this.auditAbort = controller;
    this.auditPending.set(true);
    this.auditError.set('');
    try {
      const value = await this.clients
        .get()
        .chat.audit(tenant, selection.runId, { signal: controller.signal });
      if (!this.current(epoch, controller)) return;
      if (
        value.run_id !== selection.runId ||
        !['recorded', 'not_recorded'].includes(value.provenance_status) ||
        [
          value.generations,
          value.sources,
          value.private_files,
          value.native_reads,
          value.sql_attempts,
        ].some((rows) => rows !== undefined && !Array.isArray(rows))
      )
        throw Error('The recorded answer audit is incomplete. Try again.');
      this.audit.set(value);
    } catch (error) {
      if (this.current(epoch, controller))
        this.auditError.set(this.failure(error, 'Recorded answer provenance could not be loaded.'));
    } finally {
      if (this.auditAbort === controller && epoch === this.epoch) this.auditPending.set(false);
    }
  }
  async loadActivity(page = 1) {
    const selection = this.selection,
      tenant = this.facade.tenantId();
    if (
      !selection?.runId ||
      !tenant ||
      this.scope !== this.scopeKey() ||
      this.boundContext !== this.facade.context() ||
      !Number.isInteger(page) ||
      page < 1
    )
      return;
    this.activityAbort?.abort();
    this.closeResult();
    const controller = new AbortController(),
      epoch = this.epoch;
    this.activityAbort = controller;
    this.activityPending.set(true);
    this.activityError.set('');
    try {
      const value = await this.clients.get().chat.activities(tenant, selection.runId, {
        query: { page, page_size: 25 },
        signal: controller.signal,
      });
      if (!this.current(epoch, controller)) return;
      if (
        !Array.isArray(value.items) ||
        value.page !== page ||
        value.page_size !== 25 ||
        !Number.isInteger(value.total) ||
        !Number.isInteger(value.pages) ||
        value.total! < 0 ||
        value.pages !== Math.ceil(value.total! / 25) ||
        new Set(value.items.map((row) => row.call_id)).size !== value.items.length
      )
        throw Error('The recorded activity page is incomplete. Try again.');
      this.activity.set(value);
    } catch (error) {
      if (this.current(epoch, controller))
        this.activityError.set(this.failure(error, 'Recorded activity could not be loaded.'));
    } finally {
      if (this.activityAbort === controller && epoch === this.epoch)
        this.activityPending.set(false);
    }
  }
  async loadManifest() {
    const selection = this.selection,
      tenant = this.facade.tenantId();
    if (
      !selection?.final ||
      !!selection.runId ||
      !tenant ||
      !this.canReadSources() ||
      this.scope !== this.scopeKey() ||
      this.boundContext !== this.facade.context()
    )
      return;
    this.manifestAbort?.abort();
    const controller = new AbortController(),
      epoch = this.epoch;
    this.manifestAbort = controller;
    this.manifestPending.set(true);
    this.manifestError.set('');
    try {
      const value = await this.clients
        .get()
        .evidence.conversation(
          tenant,
          { thread_id: selection.threadId, message_ids: [selection.messageId] },
          { signal: controller.signal },
        );
      if (!this.current(epoch, controller)) return;
      if (!value.revision || !Array.isArray(value.sources))
        throw Error('The recorded source manifest is incomplete. Try again.');
      this.manifest.set(value);
    } catch (error) {
      if (this.current(epoch, controller))
        this.manifestError.set(this.failure(error, 'Recorded sources could not be loaded.'));
    } finally {
      if (this.manifestAbort === controller && epoch === this.epoch)
        this.manifestPending.set(false);
    }
  }
  closeResult() {
    this.resultAbort?.abort();
    this.selected.set(null);
    this.result.set(null);
    this.resultError.set('');
    this.resultPending.set(false);
  }
  selectResult(row: ToolActivity) {
    const actual = this.activity()?.items.find(
      (item) => item.call_id === row.call_id && item.result_id === row.result_id,
    );
    if (
      !actual?.result_id ||
      !this.selection?.runId ||
      this.activityPending() ||
      this.scope !== this.scopeKey() ||
      this.boundContext !== this.facade.context()
    )
      return;
    this.closeResult();
    this.selected.set({ ...actual });
    this.contextKey.set(
      this.scope +
        '|' +
        this.selection.threadId +
        '|' +
        this.selection.messageId +
        '|' +
        this.selection.runId +
        '|' +
        this.epoch +
        '|' +
        ++this.resultVersion,
    );
  }
  retryResult() {
    const row = this.selected();
    if (row) this.selectResult(row);
  }
  readonly resolve: EvidenceResolver = async (runId, resultId, externalSignal) => {
    const selection = this.selection,
      row = this.selected();
    if (
      !selection ||
      selection.runId !== runId ||
      !row ||
      row.result_id !== resultId ||
      !this.activity()?.items.some(
        (item) => item.call_id === row.call_id && item.result_id === resultId,
      ) ||
      this.scope !== this.scopeKey() ||
      this.boundContext !== this.facade.context()
    )
      throw Error('Select a recorded tool result before opening it.');
    this.resultAbort?.abort();
    const controller = new AbortController(),
      epoch = this.epoch,
      view = this.contextKey();
    this.resultAbort = controller;
    const abort = () => controller.abort();
    if (externalSignal?.aborted) abort();
    else externalSignal?.addEventListener('abort', abort, { once: true });
    this.resultPending.set(true);
    this.resultError.set('');
    try {
      if (controller.signal.aborted)
        throw new DOMException('Evidence request was cancelled', 'AbortError');
      const value = await this.clients
        .get()
        .chat.result(this.facade.tenantId(), runId, resultId, { signal: controller.signal });
      if (!this.current(epoch, controller) || view !== this.contextKey())
        throw new DOMException('The answer context changed', 'AbortError');
      if (value.id !== resultId || value.run_id !== runId)
        throw Error('This result belongs to a different answer.');
      this.result.set(value);
      return value;
    } catch (error) {
      if (this.current(epoch, controller) && view === this.contextKey())
        this.resultError.set(this.failure(error, 'This recorded result could not be loaded.'));
      throw error;
    } finally {
      externalSignal?.removeEventListener('abort', abort);
      if (this.resultAbort === controller && epoch === this.epoch) this.resultPending.set(false);
    }
  };
}
