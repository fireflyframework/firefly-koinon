// Copyright 2026 Firefly Software Foundation
// SPDX-License-Identifier: Apache-2.0
import { computed, signal } from '@angular/core';
import type {
  FileBatchItemView,
  FileBatchPage,
  FileBatchView,
  FileRecoveryView,
  KoinonClient,
  StagedFileReceipt,
} from '@fireflyframework/koinon-sdk';
import {
  retainedUploadActions,
  sameRetainedUploadScope,
  type RetainedUploadOperation,
  type RetainedUploadRequest,
  type RetainedUploadScope,
} from './library-retained-uploads-contract';
import { isProcessingRecovery } from './library-upload-recovery-messages';
import { RetainedUploadJournal } from './library-retained-uploads-journal';
interface Review {
  request: RetainedUploadRequest;
  observedRevision: number;
  replay: boolean;
}
interface View {
  rows: FileBatchView[];
  total: number;
  page: number;
  selected: FileBatchView | null;
  items: FileBatchItemView[];
  pending: RetainedUploadRequest[];
  review: Review | null;
  recovery: Record<string, FileRecoveryView>;
  receipts: Record<string, { value: StagedFileReceipt; observedAt: string }>;
  busy: boolean;
  error: string;
  notice: string;
  denied: boolean;
  journalError: boolean;
}
const empty = (): View => ({
  rows: [],
  total: 0,
  page: 1,
  selected: null,
  items: [],
  pending: [],
  review: null,
  recovery: {},
  receipts: {},
  busy: false,
  error: '',
  notice: '',
  denied: false,
  journalError: false,
});
interface Ports {
  scope(): RetainedUploadScope;
  client(): KoinonClient;
  journal: RetainedUploadJournal;
  access(batch: FileBatchView): { read: boolean; write: boolean };
  denied?(status: 401 | 403): void;
}
interface Session {
  scope: RetainedUploadScope;
  client: KoinonClient;
  abort: AbortController;
}
const sameDestination = (a: FileBatchView, b: FileBatchView) =>
  a.id === b.id &&
  a.tenant_id === b.tenant_id &&
  a.destination.workspace_id === b.destination.workspace_id &&
  a.destination.project_id === b.destination.project_id &&
  a.destination.parent_id === b.destination.parent_id;
export class RetainedUploadsState {
  private readonly state = signal<View>(empty());
  private scope: RetainedUploadScope;
  private session: Session | null = null;
  private alive = true;
  readonly view = computed(() =>
    this.alive && sameRetainedUploadScope(this.scope, this.ports.scope()) ? this.state() : empty(),
  );
  constructor(private readonly ports: Ports) {
    this.scope = ports.scope();
  }
  syncScope() {
    const scope = this.ports.scope();
    if (sameRetainedUploadScope(scope, this.scope)) return;
    this.session?.abort.abort();
    this.session = null;
    this.scope = scope;
    this.state.set(empty());
  }
  private current(s: Session) {
    return (
      this.alive &&
      this.session === s &&
      !s.abort.signal.aborted &&
      sameRetainedUploadScope(s.scope, this.ports.scope())
    );
  }
  private check(s: Session) {
    if (!this.current(s)) throw new DOMException('Scope changed', 'AbortError');
  }
  private set(s: Session, value: Partial<View>) {
    if (this.current(s)) this.state.update((v) => ({ ...v, ...value }));
  }
  private options(s: Session) {
    this.check(s);
    return { signal: s.abort.signal };
  }
  private batch(s: Session, row: FileBatchView, id?: string) {
    this.check(s);
    if (
      row.tenant_id !== s.scope.tenantId ||
      !row.id ||
      (id && row.id !== id) ||
      !Number.isSafeInteger(row.revision) ||
      row.revision < 1 ||
      !Number.isSafeInteger(row.total_items) ||
      row.total_items < 1 ||
      row.total_items > 100 ||
      !this.ports.access(row).read
    )
      throw Error('Batch scope could not be verified');
  }
  private async run(work: (s: Session) => Promise<void>) {
    this.syncScope();
    if (!this.alive || this.session || !this.scope.allowed || this.state().denied) return;
    const s: Session = {
      scope: { ...this.scope },
      client: this.ports.client(),
      abort: new AbortController(),
    };
    this.session = s;
    this.set(s, { busy: true, error: '', notice: '' });
    try {
      await work(s);
    } catch (error) {
      if (!this.current(s)) return;
      const status = error instanceof Error && 'status' in error ? error.status : null;
      const code = error instanceof Error && 'code' in error ? error.code : null;
      if (status === 401 || status === 403) {
        this.set(s, {
          ...empty(),
          denied: true,
          error:
            'Current upload access could not be verified. Refresh your account access before continuing.',
        });
        this.ports.denied?.(status);
      } else
        this.set(s, {
          error:
            code === 'BULK_UPLOAD_ACTIVE'
              ? 'The original transfer is still active. Wait, then inspect the batch again.'
              : code === 'BULK_UPLOAD_PENDING'
                ? 'No verified retained original was found. Nothing was uploaded again.'
                : code === 'BULK_REVISION_CONFLICT'
                  ? 'The batch changed. Inspect its current state before another action.'
                  : 'The upload result could not be confirmed. Inspect the current batch before deciding what to do next.',
        });
    } finally {
      if (this.session === s) {
        this.set(s, { busy: false });
        this.session = null;
      }
    }
  }
  async load(page = 1) {
    if (!Number.isSafeInteger(page) || page < 1) return;
    return this.run(async (s) => {
      const result: FileBatchPage = await s.client.fileBatches.list(
        s.scope.tenantId,
        { page, page_size: 25 },
        this.options(s),
      );
      this.check(s);
      if (
        result.page !== page ||
        result.page_size !== 25 ||
        !Number.isSafeInteger(result.total) ||
        result.total < 0 ||
        result.items.length > 25 ||
        new Set(result.items.map((b) => b.id)).size !== result.items.length
      )
        throw Error('Invalid retained batch page');
      for (const row of result.items) this.batch(s, row);
      this.set(s, { rows: result.items, total: result.total, page });
    });
  }
  private async read(s: Session, id: string) {
    const batch = await s.client.fileBatches.get(s.scope.tenantId, id, this.options(s));
    this.batch(s, batch, id);
    const items: FileBatchItemView[] = [];
    for (let page = 1; page <= 2; page++) {
      const result = await s.client.fileBatches.items(
        s.scope.tenantId,
        id,
        { page, page_size: 50 },
        this.options(s),
      );
      this.check(s);
      if (
        result.page !== page ||
        result.page_size !== 50 ||
        result.total !== batch.total_items ||
        result.items.length > 50 ||
        !result.items.length
      )
        throw Error('Incomplete retained items');
      items.push(...result.items);
      if (items.length >= result.total) break;
    }
    const fresh = await s.client.fileBatches.get(s.scope.tenantId, id, this.options(s));
    this.batch(s, fresh, id);
    if (
      !sameDestination(batch, fresh) ||
      batch.revision !== fresh.revision ||
      items.length !== batch.total_items ||
      new Set(items.map((i) => i.id)).size !== items.length
    )
      throw Error('Batch changed during inspection');
    return { batch: fresh, items };
  }
  private admit(s: Session, batch: FileBatchView, items: FileBatchItemView[]) {
    this.batch(s, batch);
    let pending: RetainedUploadRequest[];
    let journalError = false;
    try {
      pending = this.ports.journal.forBatch(s.scope.subject, s.scope.tenantId, batch.id);
      if (
        pending.some(
          (action) => action.itemId !== null && !items.some((item) => item.id === action.itemId),
        )
      )
        throw Error('Saved item is outside current batch');
      for (const action of pending) {
        const item = items.find((i) => i.id === action.itemId);
        const observed =
          action.operation === 'cancel'
            ? batch.cancellation_requested
            : action.operation === 'recover_original'
              ? item?.status === 'staged'
              : action.operation === 'reconcile'
                ? item?.status === 'succeeded'
                : action.operation === 'submit' &&
                  items.length > 0 &&
                  items.every((i) => !!i.job_id) &&
                  batch.status !== 'staging';
        if (observed) this.ports.journal.clear(action);
      }
      pending = this.ports.journal.forBatch(s.scope.subject, s.scope.tenantId, batch.id);
    } catch {
      journalError = true;
      pending = [];
    }
    this.set(s, {
      selected: batch,
      items,
      pending,
      journalError,
      review: null,
      recovery: {},
      receipts: {},
      ...(journalError
        ? {
            error:
              'Saved upload actions could not be verified. Session storage is required before making changes.',
          }
        : {}),
    });
  }
  async select(id: string) {
    return this.run(async (s) => {
      const { batch, items } = await this.read(s, id);
      this.admit(s, batch, items);
    });
  }
  closeDetails() {
    if (!this.view().busy)
      this.state.update((v) => ({
        ...v,
        selected: null,
        items: [],
        pending: [],
        review: null,
        recovery: {},
        receipts: {},
        journalError: false,
      }));
  }
  closeReview() {
    if (!this.view().busy) this.state.update((v) => ({ ...v, review: null }));
  }
  canAct(operation: RetainedUploadOperation, itemId?: string) {
    const v = this.view();
    return (
      !!v.selected &&
      !v.denied &&
      !v.busy &&
      !v.journalError &&
      this.ports.access(v.selected).write &&
      (isProcessingRecovery(operation)
        ? !!itemId &&
          v.recovery[itemId]?.operation === operation &&
          v.recovery[itemId]?.batch_revision === v.selected.revision
        : retainedUploadActions(v.selected, v.items, itemId).includes(operation)) &&
      !v.pending.some((p) => p.operation === operation && p.itemId === (itemId ?? null))
    );
  }
  async review(operation: RetainedUploadOperation, itemId?: string) {
    const selected = this.view().selected;
    if (!selected || !this.canAct(operation, itemId)) return;
    return this.run(async (s) => {
      const { batch, items } = await this.read(s, selected.id);
      this.admit(s, batch, items);
      const descriptor =
        isProcessingRecovery(operation) && itemId
          ? await this.recoveryDescriptor(s, batch, items, itemId)
          : null;
      if (
        !this.ports.access(batch).write ||
        (isProcessingRecovery(operation)
          ? descriptor?.operation !== operation
          : !retainedUploadActions(batch, items, itemId).includes(operation)) ||
        this.state().journalError
      )
        return;
      this.set(s, {
        ...(descriptor && itemId ? { recovery: { [itemId]: descriptor } } : {}),
        review: {
          request: {
            subject: s.scope.subject,
            tenantId: s.scope.tenantId,
            batchId: batch.id,
            itemId: itemId ?? null,
            operation,
            expectedRevision: batch.revision,
            key: crypto.randomUUID(),
          },
          observedRevision: batch.revision,
          replay: false,
        },
      });
    });
  }
  async reviewSaved(action: RetainedUploadRequest) {
    const selected = this.view().selected;
    if (!selected || action.batchId !== selected.id) return;
    return this.run(async (s) => {
      const { batch, items } = await this.read(s, selected.id);
      this.admit(s, batch, items);
      const saved = this.state().pending.find((request) => request.key === action.key);
      if (!this.ports.access(batch).write || this.state().journalError || !saved) return;
      this.set(s, { review: { request: saved, observedRevision: batch.revision, replay: true } });
    });
  }
  async confirm() {
    const review = this.view().review;
    if (!review) return;
    return this.run(async (s) => {
      const { batch, items } = await this.read(s, review.request.batchId);
      this.admit(s, batch, items);
      this.check(s);
      const action = review.request;
      if (
        action.subject !== s.scope.subject ||
        action.tenantId !== s.scope.tenantId ||
        !this.ports.access(batch).write ||
        this.state().journalError
      )
        return;
      const descriptor =
        !review.replay && isProcessingRecovery(action.operation) && action.itemId
          ? await this.recoveryDescriptor(s, batch, items, action.itemId)
          : null;
      if (
        batch.revision !== review.observedRevision ||
        (!review.replay &&
          (isProcessingRecovery(action.operation)
            ? descriptor?.operation !== action.operation
            : !retainedUploadActions(batch, items, action.itemId ?? undefined).includes(
                action.operation,
              )))
      ) {
        this.set(s, {
          error: 'The batch changed. Inspect its current state before another action.',
        });
        return;
      }
      this.ports.journal.put(action);
      this.set(s, {
        pending: this.ports.journal.forBatch(s.scope.subject, s.scope.tenantId, batch.id),
        review: null,
      });
      const api = s.client.fileBatches,
        body = { expected_revision: action.expectedRevision };
      let result: FileBatchView;
      if (action.operation === 'submit')
        result = await api.submit(s.scope.tenantId, batch.id, body, action.key, this.options(s));
      else if (action.operation === 'cancel')
        result = await api.cancel(s.scope.tenantId, batch.id, body, action.key, this.options(s));
      else if (action.operation === 'recover_original')
        result = await api.recoverOriginal(
          s.scope.tenantId,
          batch.id,
          action.itemId!,
          body,
          action.key,
          this.options(s),
        );
      else if (isProcessingRecovery(action.operation))
        result = await api.recoverProcessing(
          s.scope.tenantId,
          batch.id,
          action.itemId!,
          { ...body, operation: action.operation },
          action.key,
          this.options(s),
        );
      else
        result = await api.reconcile(
          s.scope.tenantId,
          batch.id,
          action.itemId!,
          body,
          action.key,
          this.options(s),
        );
      this.batch(s, result, batch.id);
      if (!sameDestination(batch, result)) throw Error('Batch destination changed');
      this.ports.journal.clear(action);
      this.set(s, {
        selected: result,
        pending: this.ports.journal.forBatch(s.scope.subject, s.scope.tenantId, batch.id),
        recovery: {},
        notice:
          action.operation === 'recover_original'
            ? 'Original check completed. Inspect the current receipt state before submitting for processing.'
            : 'Action acknowledged. Review the current recorded state; processing completion is a separate result.',
      });
      try {
        const observed = await this.read(s, batch.id);
        this.admit(s, observed.batch, observed.items);
      } catch (error) {
        const status = error instanceof Error && 'status' in error ? error.status : null;
        if (status === 401 || status === 403) throw error;
        this.set(s, {
          items: [],
          receipts: {},
          notice: '',
          error:
            'The action was acknowledged, but the current status could not be refreshed. Inspect the upload again; do not repeat the action.',
        });
      }
    });
  }
  canInspectRecovery(itemId: string) {
    const v = this.view();
    return (
      !!v.selected &&
      !v.busy &&
      !v.denied &&
      this.ports.access(v.selected).write &&
      v.items.some((item) => item.id === itemId && ['failed', 'reconciling'].includes(item.status))
    );
  }
  private async recoveryDescriptor(
    s: Session,
    batch: FileBatchView,
    items: FileBatchItemView[],
    itemId: string,
  ) {
    if (!this.ports.access(batch).write || !items.some((item) => item.id === itemId))
      throw Error('Recovery scope could not be verified');
    const result = await s.client.fileBatches.processingRecovery(
      s.scope.tenantId,
      batch.id,
      itemId,
      this.options(s),
    );
    this.check(s);
    if (
      !this.ports.access(batch).write ||
      result.batch_id !== batch.id ||
      result.item_id !== itemId ||
      result.batch_revision !== batch.revision ||
      !Number.isSafeInteger(result.attempts) ||
      result.attempts < 0 ||
      !Number.isSafeInteger(result.max_attempts) ||
      result.max_attempts < 1 ||
      result.attempts > result.max_attempts ||
      !['absent', 'admitted', 'prepared', 'committed', 'unknown', 'not_checked'].includes(
        result.native_state,
      ) ||
      !['queued', 'running', 'succeeded', 'failed', 'cancelled', 'unknown'].includes(
        result.job_status,
      ) ||
      !['verified', 'unavailable', 'not_checked'].includes(result.original_receipt_state) ||
      (result.operation !== null && !isProcessingRecovery(result.operation)) ||
      (result.operation !== null &&
        (result.job_status !== 'failed' ||
          (
            {
              retry_processing: 'absent',
              finalize_publication: 'prepared',
              acknowledge_commit: 'committed',
            } as const
          )[result.operation] !== result.native_state))
    )
      throw Error('Recovery observation could not be verified');
    return result;
  }
  async inspectRecovery(itemId: string) {
    const selected = this.view().selected;
    if (!selected || !this.canInspectRecovery(itemId)) return;
    return this.run(async (s) => {
      const { batch, items } = await this.read(s, selected.id);
      this.admit(s, batch, items);
      const result = await this.recoveryDescriptor(s, batch, items, itemId);
      this.set(s, { recovery: { [itemId]: result } });
    });
  }
  async verifyReceipt(itemId: string) {
    const selected = this.view().selected;
    if (!selected) return;
    return this.run(async (s) => {
      const { batch, items } = await this.read(s, selected.id);
      this.admit(s, batch, items);
      const item = items.find((i) => i.id === itemId);
      if (!item || item.status === 'awaiting_upload') return;
      const receipt = await s.client.fileBatches.receipt(
        s.scope.tenantId,
        batch.id,
        itemId,
        this.options(s),
      );
      this.check(s);
      if (
        !this.ports.access(batch).read ||
        receipt.batch_id !== batch.id ||
        receipt.item_id !== itemId ||
        receipt.sha256 !== item.sha256 ||
        receipt.size_bytes !== item.size_bytes ||
        receipt.status !== 'staged'
      )
        throw Error('Receipt differs from current item');
      this.set(s, {
        receipts: { [itemId]: { value: receipt, observedAt: new Date().toISOString() } },
        notice:
          'The retained original was verified. This does not establish processing or search availability.',
      });
    });
  }
  dispose() {
    this.alive = false;
    this.session?.abort.abort();
    this.session = null;
    this.state.set(empty());
  }
}
