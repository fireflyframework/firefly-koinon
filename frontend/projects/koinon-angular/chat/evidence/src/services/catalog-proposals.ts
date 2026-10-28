// Copyright 2026 Firefly Software Foundation
// SPDX-License-Identifier: Apache-2.0
import { Injectable, OnDestroy, computed, effect, inject, signal, untracked } from '@angular/core';
import { KoinonClientContext, KoinonFacade } from '@fireflyframework/koinon-angular';
import {
  KoinonError,
  type CatalogEntry,
  type CatalogProposal,
  type ContextResponse,
} from '@fireflyframework/koinon-sdk';
interface Selection {
  runId: string;
  resultId: string;
}
interface Snapshot extends Selection {
  key: string;
  context: ContextResponse | null;
}
interface Review extends Snapshot {
  value: CatalogProposal;
  asset: CatalogEntry;
  fresh: boolean;
}
interface Failure extends Snapshot {
  message: string;
  status: number | null;
  code: string;
}
@Injectable()
export class KoinonCatalogProposals implements OnDestroy {
  private readonly facade = inject(KoinonFacade);
  private readonly clients = inject(KoinonClientContext);
  private readonly selection = signal<Selection>({ runId: '', resultId: '' });
  readonly canRead = computed(() =>
    Boolean(
      this.facade.tenantId() &&
      this.facade.context()?.subject &&
      !this.facade.authRequired() &&
      this.facade.permissions().has('chat:use') &&
      this.facade.permissions().has('catalog:read'),
    ),
  );
  readonly requiresSignIn = computed(() => this.facade.authRequired());
  readonly scopeKey = computed(() =>
    JSON.stringify([
      this.facade.tenantId(),
      this.facade.workspaceId(),
      this.facade.projectId(),
      this.facade.context()?.subject,
      this.clients.revision(),
      [...this.facade.permissions()].sort(),
      this.facade.authRequired(),
    ]),
  );
  private readonly reviewed = signal<Review | null>(null);
  private readonly reading = signal<Snapshot | null>(null);
  private readonly failure = signal<Failure | null>(null);
  private readonly obsolete = signal('');
  private readonly target = computed(() =>
    JSON.stringify([
      this.facade.tenantId(),
      this.facade.context()?.subject,
      this.clients.revision(),
      this.selection().runId,
      this.selection().resultId,
    ]),
  );
  readonly proposal = computed(() => {
    const reviewed = this.reviewed();
    return reviewed && this.current(reviewed) ? reviewed.value : null;
  });
  readonly asset = computed(() => {
    const reviewed = this.reviewed();
    return reviewed && this.current(reviewed) ? reviewed.asset : null;
  });
  readonly pending = computed(() => {
    const reading = this.reading();
    return Boolean(reading && this.current(reading));
  });
  readonly error = computed(() => {
    const failure = this.failure();
    return failure && this.current(failure) ? failure.message : '';
  });
  readonly failureCode = computed(() => {
    const failure = this.failure();
    return failure && this.current(failure) ? failure.code : '';
  });
  readonly requiresNewProposal = computed(() =>
    Boolean(this.obsolete() && this.obsolete() === this.target()),
  );
  readonly canCancel = computed(() => {
    const reviewed = this.reviewed();
    return Boolean(
      reviewed &&
      this.current(reviewed) &&
      reviewed.fresh &&
      reviewed.value.status === 'pending' &&
      !this.pending(),
    );
  });
  readonly canEdit = computed(() => this.facade.permissions().has('catalog:write'));
  readonly canApply = computed(
    () => this.canCancel() && this.canEdit() && !this.requiresNewProposal(),
  );
  private controller?: AbortController;
  private epoch = 0;
  private disposed = false;
  private bound: { key: string; context: ContextResponse | null };
  constructor() {
    this.bound = { key: this.scopeKey(), context: this.facade.context() };
    effect(() => {
      const key = this.scopeKey(),
        context = this.facade.context();
      if (this.bound.key !== key || this.bound.context !== context) untracked(() => this.reset());
    });
  }
  reset() {
    ++this.epoch;
    this.controller?.abort();
    this.controller = undefined;
    this.reviewed.set(null);
    this.reading.set(null);
    this.failure.set(null);
    this.bound = { key: this.scopeKey(), context: this.facade.context() };
  }
  private snapshot(): Snapshot {
    return { ...this.selection(), key: this.scopeKey(), context: this.facade.context() };
  }
  private current(snapshot: Snapshot) {
    const selection = this.selection();
    return (
      !this.disposed &&
      this.canRead() &&
      snapshot.key === this.scopeKey() &&
      snapshot.context === this.facade.context() &&
      snapshot.runId === selection.runId &&
      snapshot.resultId === selection.resultId
    );
  }
  private inScope(asset: CatalogEntry) {
    return (
      asset.tenant_id === this.facade.tenantId() &&
      ['document', 'dataset'].includes(asset.kind) &&
      asset.status !== 'archived' &&
      (!this.facade.workspaceId() || asset.workspace_id === this.facade.workspaceId()) &&
      (!this.facade.projectId() || asset.project_id === this.facade.projectId())
    );
  }
  private validate(value: CatalogProposal, snapshot: Snapshot) {
    const keys = Object.keys(value.changes ?? {});
    if (
      value.id !== snapshot.resultId ||
      value.run_id !== snapshot.runId ||
      (value.kind ?? 'catalog') !== 'catalog' ||
      !['pending', 'applied', 'cancelled'].includes(value.status) ||
      !Number.isSafeInteger(value.revision) ||
      value.revision < 1 ||
      !value.asset_id ||
      typeof value.before?.name !== 'string' ||
      typeof value.before?.description !== 'string' ||
      !keys.length ||
      keys.some((key) => !['name', 'description'].includes(key)) ||
      keys.some((key) => typeof value.changes[key as 'name' | 'description'] !== 'string') ||
      (value.changes.name !== undefined &&
        (!value.changes.name?.trim() || Array.from(value.changes.name).length > 255)) ||
      (value.changes.description !== undefined &&
        Array.from(value.changes.description ?? '').length > 4000)
    )
      throw Error('The proposal response did not match this review. Refresh before continuing.');
    return value;
  }
  private fail(error: unknown, snapshot: Snapshot) {
    if (error instanceof KoinonError && error.status === 401) this.facade.authRequired.set(true);
    const status = error instanceof KoinonError ? error.status : null,
      code = error instanceof KoinonError ? error.code : '';
    if (code === 'PROPOSAL_RESOURCE_CHANGED') this.obsolete.set(this.target());
    if (status === 401 || status === 403) this.reviewed.set(null);
    this.failure.set({
      ...snapshot,
      message: error instanceof Error ? error.message : 'The proposal could not be loaded.',
      status,
      code,
    });
  }
  async load(runId: string, resultId: string): Promise<CatalogProposal | null> {
    this.selection.set({ runId, resultId });
    this.reset();
    if (
      this.disposed ||
      !this.canRead() ||
      !runId ||
      !resultId ||
      runId.length > 128 ||
      resultId.length > 128
    )
      return null;
    const snapshot = this.snapshot(),
      epoch = this.epoch,
      controller = new AbortController();
    this.controller = controller;
    this.reading.set(snapshot);
    try {
      const client = this.clients.get(),
        tenant = this.facade.tenantId();
      const value = this.validate(
        await client.chat.proposals.get(tenant, runId, resultId, { signal: controller.signal }),
        snapshot,
      );
      if (epoch !== this.epoch || !this.current(snapshot) || controller.signal.aborted) return null;
      const asset = await client.catalog.get(tenant, value.asset_id, { signal: controller.signal });
      if (epoch !== this.epoch || !this.current(snapshot) || controller.signal.aborted) return null;
      if (!this.inScope(asset)) throw Error('This proposal resource is outside the current scope.');
      this.reviewed.set({ ...snapshot, value, asset, fresh: true });
      return value;
    } catch (error) {
      if (epoch === this.epoch && this.current(snapshot) && !controller.signal.aborted)
        this.fail(error, snapshot);
      return null;
    } finally {
      if (epoch === this.epoch) this.reading.set(null);
    }
  }
  async apply(): Promise<CatalogProposal | null> {
    return this.mutate('apply');
  }
  async cancel(): Promise<CatalogProposal | null> {
    return this.mutate('cancel');
  }
  private async mutate(action: 'apply' | 'cancel'): Promise<CatalogProposal | null> {
    const reviewed = this.reviewed();
    if (!reviewed || !(action === 'apply' ? this.canApply() : this.canCancel())) return null;
    const epoch = this.epoch,
      snapshot = this.snapshot(),
      controller = new AbortController(),
      target = this.facade.tenantId();
    this.controller = controller;
    this.reading.set(snapshot);
    this.failure.set(null);
    this.reviewed.set({ ...reviewed, fresh: false });
    try {
      const proposals = this.clients.get().chat.proposals;
      const value = this.validate(
        await (action === 'apply'
          ? proposals.confirm(
              target,
              snapshot.runId,
              snapshot.resultId,
              { expected_revision: reviewed.value.revision, confirm: true },
              { signal: controller.signal },
            )
          : proposals.cancel(
              target,
              snapshot.runId,
              snapshot.resultId,
              { expected_revision: reviewed.value.revision },
              { signal: controller.signal },
            )),
        snapshot,
      );
      if (epoch !== this.epoch || !this.current(snapshot) || controller.signal.aborted) return null;
      if (
        value.asset_id !== reviewed.asset.id ||
        value.status !== (action === 'apply' ? 'applied' : 'cancelled') ||
        value.revision <= reviewed.value.revision
      )
        throw Error('Refresh the proposal to verify the recorded outcome.');
      this.reviewed.set({ ...snapshot, value, asset: reviewed.asset, fresh: true });
      return value;
    } catch (error) {
      if (epoch === this.epoch && this.current(snapshot) && !controller.signal.aborted)
        this.fail(error, snapshot);
      return null;
    } finally {
      if (epoch === this.epoch) this.reading.set(null);
    }
  }
  ngOnDestroy() {
    this.disposed = true;
    this.reset();
  }
}
