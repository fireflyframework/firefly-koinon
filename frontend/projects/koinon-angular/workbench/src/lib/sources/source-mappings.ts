// Copyright 2026 Firefly Software Foundation SPDX-License-Identifier: Apache-2.0
import { Injectable, OnDestroy, computed, effect, inject, signal } from '@angular/core';
import type {
  SourceMappingValidationOutput,
  SourceMappingValidationItemPage,
  SourceRunOutput,
  SourceRunItemPage,
  HttpMethod,
  RequestOptions,
} from '@fireflyframework/koinon-sdk';
import {
  KoinonClientContext,
  KoinonFacade,
  organizationContextKey,
} from '@fireflyframework/koinon-angular/workbench/core';
import type {
  ControlReceipt,
  CursorPage,
  MappingPolicy,
  MappingSummary,
  PolicyReceipt,
  ReviewPage,
  SourceMapping,
} from './mapping-contracts';
interface Authority {
  generation: number;
  key: string;
  context: ReturnType<KoinonFacade['context']>;
}
interface PendingOperation {
  path: string;
  body: Record<string, unknown>;
  kind: 'review' | 'apply' | 'control';
  authority: Authority;
  mappingId?: string;
}
@Injectable()
export class KoinonSourceMappings implements OnDestroy {
  private readonly f = inject(KoinonFacade);
  private readonly clients = inject(KoinonClientContext);
  readonly identity = computed(() =>
    JSON.stringify([organizationContextKey(this.f, this.clients), this.f.authRequired()]),
  );
  private readonly authority = signal<Authority | null>(null);
  private alive = true;
  private sequence = 0;
  private generation = 0;
  private abort?: AbortController;
  private readonly rows = signal<CursorPage<MappingSummary>>({ items: [], next_cursor: null });
  private readonly mapping = signal<SourceMapping | null>(null);
  private readonly receipt = signal<PolicyReceipt | null>(null);
  private readonly preview = signal<ReviewPage | null>(null);
  private readonly pendingOperation = signal<PendingOperation | null>(null);
  private readonly prepared = signal<SourceMappingValidationOutput | null>(null);
  private readonly candidates = signal<SourceMappingValidationItemPage | null>(null);
  private selection: MappingPolicy | null = null;
  private readonly selectionCurrent = signal(false);
  private preparationOperation: { operationId: string; validationId?: string } | null = null;
  private readonly preparationUnknown = signal(false);
  private readonly runRows = signal<CursorPage<SourceRunOutput>>({ items: [], next_cursor: null });
  private readonly selectedRun = signal<SourceRunOutput | null>(null);
  private readonly itemRows = signal<SourceRunItemPage>({ items: [], next_cursor: null });
  readonly preparation = computed(() => (this.current() ? this.prepared() : null));
  readonly preparationItems = computed(() => (this.current() ? this.candidates() : null));
  readonly preparationUncertain = computed(() => this.current() && this.preparationUnknown());
  readonly runs = computed(() =>
    this.current() ? this.runRows() : { items: [], next_cursor: null },
  );
  readonly run = computed(() => (this.current() ? this.selectedRun() : null));
  readonly runItems = computed(() =>
    this.current() ? this.itemRows() : { items: [], next_cursor: null },
  );
  readonly canResumePreparation = computed(
    () =>
      this.selectionCurrent() &&
      !!this.preparation()?.continuation_token &&
      !this.loading() &&
      !this.uncertain() &&
      ['scanning', 'verifying', 'checking_changes'].includes(this.preparation()!.state),
  );
  readonly preparationComplete = computed(
    () =>
      this.selectionCurrent() &&
      this.preparation()?.state === 'complete' &&
      this.preparation()?.enumeration_complete &&
      !!this.preparation()?.manifest_sha256 &&
      Date.parse(this.preparation()!.expires_at) > this.clock(),
  );
  private readonly busy = signal(false);
  private readonly failure = signal('');
  private readonly message = signal('');
  readonly clock = signal(Date.now());
  private readonly clockTimer = setInterval(() => this.clock.set(Date.now()), 1000);
  readonly accessChanged = signal(0);
  readonly page = computed(() => (this.current() ? this.rows() : { items: [], next_cursor: null }));
  readonly detail = computed(() => (this.current() ? this.mapping() : null));
  readonly review = computed(() => (this.current() ? this.preview() : null));
  readonly reviewReceipt = computed(() => (this.current() ? this.receipt() : null));
  readonly loading = computed(() => this.current() && this.busy());
  readonly error = computed(() => (this.current() ? this.failure() : ''));
  readonly notice = computed(() => (this.current() ? this.message() : ''));
  readonly uncertain = computed(
    () => this.current() && (!!this.pendingOperation() || this.preparationUnknown()),
  );
  readonly pendingLabel = computed(() => {
    const operation = this.current() ? this.pendingOperation() : null;
    return operation?.kind === 'review'
      ? 'Preparing review…'
      : operation?.kind === 'apply'
        ? 'Approving synchronization…'
        : operation?.path.endsWith('/sync')
          ? 'Starting synchronization…'
          : operation
            ? 'Updating synchronization…'
            : 'Loading…';
  });
  readonly canApprove = computed(() => {
    const page = this.review(),
      receipt = this.reviewReceipt();
    return (
      !!page &&
      !!receipt &&
      !this.loading() &&
      !this.uncertain() &&
      page.can_apply &&
      page.enumeration_complete &&
      page.review_id === receipt.policy_id &&
      Date.parse(receipt.review_expires_at) > this.clock() &&
      page.review_digest === receipt.review_digest &&
      page.policy_revision === receipt.result_policy_revision &&
      Date.parse(page.expires_at) > this.clock()
    );
  });
  constructor() {
    effect(() => {
      this.identity();
      this.f.context();
      if (!this.current()) this.reset();
    });
  }
  generationVersion() {
    return this.generation;
  }
  private current(authority = this.authority()) {
    return (
      !!authority &&
      this.alive &&
      !this.f.authRequired() &&
      authority.generation === this.generation &&
      authority.key === this.identity() &&
      authority.context === this.f.context()
    );
  }
  private capture() {
    if (!this.current()) this.reset();
    const authority = {
      key: this.identity(),
      context: this.f.context(),
      generation: this.generation,
    };
    this.authority.set(authority);
    return authority;
  }
  private reset() {
    ++this.generation;
    ++this.sequence;
    this.abort?.abort();
    this.rows.set({ items: [], next_cursor: null });
    this.prepared.set(null);
    this.candidates.set(null);
    this.selection = null;
    this.selectionCurrent.set(false);
    this.preparationOperation = null;
    this.preparationUnknown.set(false);
    this.runRows.set({ items: [], next_cursor: null });
    this.selectedRun.set(null);
    this.itemRows.set({ items: [], next_cursor: null });
    this.mapping.set(null);
    this.receipt.set(null);
    this.preview.set(null);
    this.pendingOperation.set(null);
    this.busy.set(false);
    this.failure.set('');
    this.message.set('');
    this.authority.set(null);
  }
  private path(suffix: string) {
    return '/tenants/' + encodeURIComponent(this.f.tenantId()) + '/content-sources' + suffix;
  }
  private request<T>(method: HttpMethod, path: string, options: RequestOptions = {}) {
    const transport = this.clients.getTransport();
    if (!transport) throw Error('Source synchronization is unavailable.');
    return transport.request<T>(method, this.path(path), options);
  }
  invalidateReview() {
    this.receipt.set(null);
    this.preview.set(null);
    this.message.set('');
  }
  private fail(error: unknown) {
    const status = error instanceof Error && 'status' in error ? error.status : null;
    if (status === 401) {
      this.reset();
      this.accessChanged.update((value) => value + 1);
      this.f.authRequired.set(true);
      return;
    }
    if (status === 403) {
      this.reset();
      this.capture();
      this.accessChanged.update((value) => value + 1);
      this.failure.set('Access changed. Check your account and try again.');
      return;
    }
    if (status === 409) {
      this.invalidateReview();
      this.mapping.set(null);
      this.rows.set({ items: [], next_cursor: null });
      this.accessChanged.update((value) => value + 1);
      this.failure.set(
        'This synchronization changed elsewhere. Reload its current settings before continuing.',
      );
      return;
    }
    this.failure.set('Could not load synchronizations. Try again.');
  }
  async load(more = false) {
    if (this.loading()) return;
    const cursor = more ? this.page().next_cursor : null;
    if (more && !cursor) return;
    const authority = this.capture(),
      sequence = ++this.sequence;
    this.busy.set(true);
    this.failure.set('');
    try {
      const result = await this.request<CursorPage<MappingSummary>>('GET', '/mappings', {
        query: { limit: 25, ...(cursor ? { cursor } : {}) },
      });
      if (this.current(authority) && sequence === this.sequence)
        this.rows.set({
          ...result,
          items: more ? [...this.rows().items, ...result.items] : result.items,
        });
    } catch (error) {
      if (this.current(authority) && sequence === this.sequence) {
        this.rows.set({ items: [], next_cursor: null });
        this.fail(error);
      }
    } finally {
      if (this.current(authority) && sequence === this.sequence) this.busy.set(false);
    }
  }
  async open(id: string) {
    if (this.loading() || this.uncertain()) return null;
    const authority = this.capture(),
      sequence = ++this.sequence;
    this.mapping.set(null);
    this.invalidateReview();
    this.busy.set(true);
    this.failure.set('');
    try {
      const result = await this.request<SourceMapping>(
        'GET',
        '/mappings/' + encodeURIComponent(id),
      );
      if (this.current(authority) && sequence === this.sequence) {
        this.mapping.set(result);
        return result;
      }
      return null;
    } catch (error) {
      if (this.current(authority) && sequence === this.sequence) this.fail(error);
      return null;
    } finally {
      if (this.current(authority) && sequence === this.sequence) this.busy.set(false);
    }
  }
  async prepare(policy: MappingPolicy, validationId?: string) {
    if (this.loading() || this.uncertain()) return false;
    const detail = this.detail();
    this.invalidateReview();
    return this.mutate({
      kind: 'review',
      mappingId: detail?.id,
      path: detail ? '/mappings/' + encodeURIComponent(detail.id) + '/reviews' : '/mapping-reviews',
      body: {
        ...structuredClone(policy),
        ...(validationId ? { validation_id: validationId } : {}),
        operation_id: crypto.randomUUID(),
        ...(detail ? { expected_revision: detail.latest_review_revision } : {}),
      },
      authority: this.capture(),
    });
  }
  selectionChanged() {
    this.selection = null;
    this.selectionCurrent.set(false);
    this.invalidateReview();
    this.persistRecovery();
  }
  async beginPreparation(policy: MappingPolicy) {
    if (this.loading() || this.uncertain()) return false;
    if (
      this.preparation() &&
      !['abandoned', 'cleaning', 'expired'].includes(this.preparation()!.state)
    ) {
      this.failure.set('Abandon the current preparation before preparing another selection.');
      return false;
    }
    this.capture();
    this.selection = structuredClone(policy);
    this.selectionCurrent.set(true);
    this.invalidateReview();
    this.prepared.set(null);
    this.candidates.set(null);
    this.preparationOperation = { operationId: crypto.randomUUID() };
    const detail = this.detail();
    return this.preparationRequest('POST', '/mapping-validations', {
      ...policy,
      operation_id: this.preparationOperation.operationId,
      ...(detail
        ? { mapping_id: detail.id, expected_revision: detail.latest_review_revision }
        : {}),
    });
  }
  async resumePreparation() {
    if (!this.canResumePreparation()) return false;
    // One deliberate resume advances one bounded slice. Recovery never calls this method.
    const value = this.preparation()!;
    this.invalidateReview();
    return this.preparationRequest(
      'POST',
      '/mapping-validations/' + encodeURIComponent(value.validation_id) + '/continue',
      {
        expected_revision: value.revision,
        continuation_token: value.continuation_token,
      },
    );
  }
  async checkPreparation() {
    if (this.loading()) return false;
    const operation = this.preparationOperation;
    if (!operation) return false;
    const suffix = operation.validationId
      ? encodeURIComponent(operation.validationId)
      : 'operations/' + encodeURIComponent(operation.operationId);
    return this.preparationRequest('GET', '/mapping-validations/' + suffix);
  }
  async abandonPreparation() {
    const value = this.preparation();
    if (!value || this.loading() || this.uncertain()) return false;
    this.invalidateReview();
    this.candidates.set(null);
    return this.preparationRequest(
      'POST',
      '/mapping-validations/' + encodeURIComponent(value.validation_id) + '/abandon',
      { expected_revision: value.revision },
    );
  }
  async reviewPreparation() {
    if (!this.preparationComplete() || !this.selection) return false;
    return this.prepare(this.selection, this.preparation()!.validation_id);
  }
  private async preparationRequest(
    method: HttpMethod,
    path: string,
    body?: Record<string, unknown>,
  ) {
    const authority = this.capture();
    this.busy.set(true);
    this.failure.set('');
    this.persistRecovery();
    try {
      const result = await this.request<SourceMappingValidationOutput>(method, path, { body });
      if (!this.current(authority)) return false;
      if (
        this.preparationOperation?.validationId &&
        result.validation_id !== this.preparationOperation.validationId
      )
        throw Error('Preparation identity changed');
      this.prepared.set(result);
      this.candidates.set(null);
      this.preparationOperation = {
        operationId: this.preparationOperation!.operationId,
        validationId: result.validation_id,
      };
      this.preparationUnknown.set(false);
      this.persistRecovery();
      return true;
    } catch (error) {
      if (this.current(authority)) {
        const status = error instanceof Error && 'status' in error ? error.status : null;
        if (status === 401 || status === 403) this.fail(error);
        else if (status === 429 && path === '/mapping-validations') {
          this.preparationOperation = null;
          this.preparationUnknown.set(false);
          this.failure.set(
            'Preparation capacity is full. Check your existing preparation before trying again.',
          );
          this.persistRecovery();
        } else {
          this.preparationUnknown.set(true);
          this.candidates.set(null);
          this.invalidateReview();
          this.failure.set(
            status === 429
              ? 'Preparation capacity is full. Check your existing preparation before trying again.'
              : 'Preparation needs to be checked. Check status before resuming.',
          );
        }
      }
      return false;
    } finally {
      if (this.current(authority)) this.busy.set(false);
    }
  }
  async loadPreparationItems(more = false) {
    const value = this.preparation();
    if (!value || this.loading()) return;
    const cursor = more ? this.preparationItems()?.next_cursor : null;
    if (more && !cursor) return;
    const authority = this.capture();
    this.busy.set(true);
    this.candidates.set(null);
    try {
      const result = await this.request<SourceMappingValidationItemPage>(
        'GET',
        '/mapping-validations/' + encodeURIComponent(value.validation_id) + '/items',
        { query: { limit: 25, ...(cursor ? { cursor } : {}) } },
      );
      if (
        this.current(authority) &&
        result.validation_id === value.validation_id &&
        result.revision === value.revision
      )
        this.candidates.set(result);
    } catch (error) {
      if (this.current(authority)) this.fail(error);
    } finally {
      if (this.current(authority)) this.busy.set(false);
    }
  }
  private recoveryKey() {
    return organizationContextKey(this.f, this.clients);
  }
  private persistRecovery() {
    // Only input IDs/settings and operation identities survive reload. Never retain names,
    // review payloads, tokens, cursors, provider content, or a continuation token.
    try {
      const pending = this.pendingOperation();
      sessionStorage.setItem(
        'koinon-source-recovery',
        JSON.stringify({
          key: this.recoveryKey(),
          preparation: this.preparationOperation,
          selection: this.selection,
          mappingId: this.detail()?.id ?? pending?.mappingId,
          pending: pending
            ? {
                path: pending.path,
                kind: pending.kind,
                mappingId: pending.mappingId,
                operationId: pending.body['operation_id'],
              }
            : null,
          runId: this.run()?.id,
        }),
      );
    } catch {
      /* Storage may be unavailable; in-memory recovery still works. */
    }
  }
  preparedPolicy() {
    return this.current() && this.selectionCurrent() && this.selection
      ? structuredClone(this.selection)
      : null;
  }
  async restoreRecovery() {
    if (this.f.authRequired() || !this.f.context()?.subject || this.loading()) return;
    try {
      const raw = sessionStorage.getItem('koinon-source-recovery');
      if (!raw || raw.length > 65536) return;
      const saved = JSON.parse(raw);
      if (saved.key !== this.recoveryKey()) {
        sessionStorage.removeItem('koinon-source-recovery');
        return;
      }
      const authority = this.capture();
      if (saved.mappingId) await this.open(saved.mappingId);
      if (!this.current(authority)) return;
      this.preparationOperation = saved.preparation;
      this.selection = saved.selection;
      this.selectionCurrent.set(!!saved.selection);
      if (saved.pending) {
        this.pendingOperation.set({
          ...saved.pending,
          body: { operation_id: saved.pending.operationId },
          authority,
        });
        await this.checkOperation();
      } else if (this.preparationOperation) await this.checkPreparation();
      if (saved.runId && this.current(authority)) await this.openRun(saved.runId);
    } catch {
      /* An invalid retained identity never authorizes a mutation. */
    }
  }
  async loadRuns(more = false) {
    const mapping = this.detail();
    if (!mapping || this.loading()) return;
    const cursor = more ? this.runs().next_cursor : null;
    if (more && !cursor) return;
    const authority = this.capture();
    this.busy.set(true);
    this.runRows.set({ items: [], next_cursor: null });
    try {
      const result = await this.request<CursorPage<SourceRunOutput>>(
        'GET',
        '/mappings/' + encodeURIComponent(mapping.id) + '/runs',
        { query: { limit: 25, ...(cursor ? { cursor } : {}) } },
      );
      if (this.current(authority)) this.runRows.set(result);
    } catch (error) {
      if (this.current(authority)) this.fail(error);
    } finally {
      if (this.current(authority)) this.busy.set(false);
    }
  }
  async openRun(id: string, more = false) {
    if (this.loading()) return;
    const cursor = more ? this.runItems().next_cursor : null;
    const authority = this.capture();
    this.busy.set(true);
    this.selectedRun.set(null);
    this.itemRows.set({ items: [], next_cursor: null });
    try {
      const run = await this.request<SourceRunOutput>('GET', '/runs/' + encodeURIComponent(id));
      const items = await this.request<SourceRunItemPage>(
        'GET',
        '/runs/' + encodeURIComponent(id) + '/items',
        { query: { limit: 25, ...(cursor ? { cursor } : {}) } },
      );
      if (this.current(authority) && run.mapping_id === this.detail()?.id) {
        this.selectedRun.set(run);
        this.itemRows.set(items);
        this.persistRecovery();
      }
    } catch (error) {
      if (this.current(authority)) this.fail(error);
    } finally {
      if (this.current(authority)) this.busy.set(false);
    }
  }
  async runCommand(action: 'cancel' | 'retry') {
    const run = this.run(),
      mapping = this.detail();
    if (
      !run ||
      !mapping ||
      !run[action === 'cancel' ? 'can_cancel' : 'can_retry'] ||
      this.loading() ||
      this.uncertain()
    )
      return false;
    return this.mutate({
      kind: 'control',
      mappingId: mapping.id,
      path: '/runs/' + encodeURIComponent(run.id) + '/' + action,
      body: { expected_revision: run.control_revision, operation_id: crypto.randomUUID() },
      authority: this.capture(),
    });
  }
  async loadReview(more = false) {
    const receipt = this.reviewReceipt();
    if (!receipt || this.loading()) return;
    const cursor = more ? this.review()?.next_cursor : null;
    if (more && !cursor) return;
    const authority = this.capture(),
      sequence = ++this.sequence;
    this.busy.set(true);
    this.preview.set(null);
    try {
      const result = await this.request<ReviewPage>(
        'GET',
        '/mapping-reviews/' + encodeURIComponent(receipt.policy_id) + '/items',
        { query: { limit: 25, ...(cursor ? { cursor } : {}) } },
      );
      if (!this.current(authority) || sequence !== this.sequence) return;
      if (
        result.review_id !== receipt.policy_id ||
        result.review_digest !== receipt.review_digest ||
        result.policy_revision !== receipt.result_policy_revision
      ) {
        this.invalidateReview();
        this.failure.set('This preview has changed. Review the latest changes before starting.');
        return;
      }
      this.preview.set({
        ...result,
        items: result.items,
      });
    } catch (error) {
      if (this.current(authority) && sequence === this.sequence) {
        this.invalidateReview();
        this.fail(error);
      }
    } finally {
      if (this.current(authority) && sequence === this.sequence) this.busy.set(false);
    }
  }
  async approve() {
    if (!this.canApprove()) return false;
    const receipt = this.reviewReceipt()!;
    return this.mutate({
      kind: 'apply',
      mappingId: receipt.mapping_id,
      path: this.detail()
        ? '/mappings/' + encodeURIComponent(receipt.mapping_id) + '/apply'
        : '/mappings',
      body: {
        expected_revision: receipt.result_policy_revision,
        review_id: receipt.policy_id,
        review_digest: receipt.review_digest,
        operation_id: crypto.randomUUID(),
      },
      authority: this.capture(),
    });
  }
  async command(action: 'sync' | 'pause' | 'resume' | 'retire') {
    const detail = this.detail();
    if (
      !detail ||
      this.loading() ||
      this.uncertain() ||
      detail.control_revision === null ||
      !detail[('can_' + action) as 'can_sync' | 'can_pause' | 'can_resume' | 'can_retire']
    )
      return false;
    return this.mutate({
      kind: 'control',
      mappingId: detail.id,
      path: '/mappings/' + encodeURIComponent(detail.id) + '/' + action,
      body: { expected_revision: detail.control_revision, operation_id: crypto.randomUUID() },
      authority: this.capture(),
    });
  }
  async checkOperation() {
    if (this.preparationUnknown()) return this.checkPreparation();
    const pending = this.pendingOperation();
    if (!pending || this.loading() || !this.current(pending.authority)) return false;
    this.busy.set(true);
    try {
      const action = pending.kind === 'control' ? pending.path.split('/').at(-1)! : pending.kind;
      const result = await this.request<
        { kind: 'policy'; receipt: PolicyReceipt } | { kind: 'control'; receipt: ControlReceipt }
      >(
        'GET',
        (pending.mappingId ? '/mappings/' + encodeURIComponent(pending.mappingId) : '') +
          '/operations/' +
          encodeURIComponent(String(pending.body['operation_id'])),
        { query: { action } },
      );
      if (!this.current(pending.authority)) return false;
      if (
        result.receipt.operation_id !== pending.body['operation_id'] ||
        result.receipt.action !== action ||
        (pending.kind === 'control' ? result.kind !== 'control' : result.kind !== 'policy') ||
        (result.kind === 'policy' &&
          pending.mappingId &&
          result.receipt.mapping_id !== pending.mappingId)
      )
        throw Error('Operation receipt does not match the request');
      this.pendingOperation.set(null);
      this.failure.set('');
      this.busy.set(false);
      if (pending.kind === 'review' && result.kind === 'policy') {
        this.receipt.set(result.receipt);
        await this.loadReview();
        if (
          !this.current(pending.authority) ||
          this.reviewReceipt()?.policy_id !== result.receipt.policy_id ||
          !this.review()
        )
          return false;
      } else {
        if (pending.kind === 'apply') {
          this.preparationOperation = null;
          this.prepared.set(null);
          this.selection = null;
        }
        const refreshed = pending.mappingId ? await this.open(pending.mappingId) : null;
        if (
          !this.current(pending.authority) ||
          !refreshed ||
          refreshed.id !== pending.mappingId ||
          this.detail()?.id !== pending.mappingId
        )
          return false;
        this.message.set(
          pending.kind === 'apply'
            ? 'Synchronization approved. Start a sync when you are ready.'
            : 'Synchronization request accepted.',
        );
        if (result.kind === 'control' && result.receipt.run_id)
          await this.openRun(result.receipt.run_id);
      }
      this.persistRecovery();
      return true;
    } catch (error) {
      if (this.current(pending.authority)) {
        const status = error instanceof Error && 'status' in error ? error.status : null;
        if (status === 401 || status === 403) this.fail(error);
        else
          this.failure.set(
            'The request outcome is not available. Check again before starting another operation.',
          );
      }
      return false;
    } finally {
      if (this.current(pending.authority)) this.busy.set(false);
    }
  }
  private async mutate(operation: PendingOperation) {
    this.pendingOperation.set(operation);
    this.persistRecovery();
    this.busy.set(true);
    this.failure.set('');
    this.message.set('');
    try {
      const result = await this.request<PolicyReceipt | ControlReceipt>('POST', operation.path, {
        body: operation.body,
      });
      if (!this.current(operation.authority)) return false;
      this.pendingOperation.set(null);
      this.busy.set(false);
      if (operation.kind === 'review') {
        this.receipt.set(result as PolicyReceipt);
        await this.loadReview();
        return (
          this.current(operation.authority) &&
          !!this.review() &&
          this.reviewReceipt()?.policy_id === (result as PolicyReceipt).policy_id
        );
      }
      if (operation.kind === 'apply') {
        const receipt = result as PolicyReceipt;
        this.invalidateReview();
        const refreshed = await this.open(receipt.mapping_id);
        if (
          !this.current(operation.authority) ||
          !refreshed ||
          refreshed.id !== receipt.mapping_id ||
          this.detail()?.id !== receipt.mapping_id
        )
          return false;
        this.message.set('Synchronization approved. Start a sync when you are ready.');
        this.preparationOperation = null;
        this.prepared.set(null);
        this.selection = null;
        this.persistRecovery();
        return true;
      }
      const id = operation.mappingId;
      const refreshed = id ? await this.open(id) : null;
      if (
        !this.current(operation.authority) ||
        !refreshed ||
        refreshed.id !== id ||
        this.detail()?.id !== id
      )
        return false;
      this.message.set('Synchronization request accepted.');
      this.persistRecovery();
      const runId = (result as ControlReceipt).run_id;
      if (runId) await this.openRun(runId);
      return true;
    } catch (error) {
      if (this.current(operation.authority)) {
        const status = error instanceof Error && 'status' in error ? error.status : null;
        if (typeof status === 'number' && status >= 400 && status < 500) {
          this.pendingOperation.set(null);
          this.fail(error);
        } else
          this.failure.set(
            operation.kind === 'apply'
              ? 'Approval result is unknown. Check the request before starting a sync.'
              : operation.path.endsWith('/sync')
                ? 'Sync start result is unknown. Check the request before trying again.'
                : 'Checking whether the request completed…',
          );
      }
      return false;
    } finally {
      if (this.current(operation.authority)) this.busy.set(false);
    }
  }
  close() {
    try {
      sessionStorage.removeItem('koinon-source-recovery');
    } catch {
      /* optional storage */
    }
    this.reset();
  }
  ngOnDestroy() {
    this.alive = false;
    clearInterval(this.clockTimer);
    this.reset();
  }
}
