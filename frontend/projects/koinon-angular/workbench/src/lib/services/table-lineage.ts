// Copyright 2026 Firefly Software Foundation
// SPDX-License-Identifier: Apache-2.0
import { Injectable, computed, effect, inject, signal, untracked, DestroyRef } from '@angular/core';
import type {
  ContextResponse,
  TableProvenance,
  TableSnapshotPage,
} from '@fireflyframework/koinon-sdk';
import { KoinonFacade } from '../koinon-facade';
import { KoinonClientContext } from './client-context';

export interface TableLineageTarget {
  datasetId: string;
  tableId: string;
  datasetName: string;
  tableName: string;
  snapshotId?: string;
}
interface Selection {
  target: TableLineageTarget;
  key: string;
  context: ContextResponse | null;
}
@Injectable()
export class KoinonTableLineage {
  private readonly facade = inject(KoinonFacade);
  private readonly clients = inject(KoinonClientContext);
  private readonly selected = signal<Selection | null>(null);
  private readonly key = computed(() =>
    JSON.stringify([
      this.facade.tenantId(),
      this.facade.workspaceId(),
      this.facade.projectId(),
      this.facade.context()?.subject,
      this.clients.revision(),
      this.facade.authRequired(),
      this.facade.permissions().has('catalog:read'),
    ]),
  );
  private readonly page = signal<TableSnapshotPage | null>(null);
  private readonly version = signal<TableProvenance | null>(null);
  private readonly failure = signal('');
  private readonly loading = signal(false);
  private readonly showingVersion = signal(false);
  private sequence = 0;
  private read?: AbortController;
  private lastVersion = '';
  private lastPage = 1;
  readonly target = computed(() =>
    this.current(this.selected()) ? this.selected()!.target : null,
  );
  readonly history = computed(() => (this.target() ? this.page() : null));
  readonly detail = computed(() => (this.target() ? this.version() : null));
  readonly error = computed(() => (this.target() ? this.failure() : ''));
  readonly pending = computed(() => !!this.target() && this.loading());
  readonly detailOpen = computed(() => !!this.target() && this.showingVersion());
  readonly isCurrent = computed(
    () => !!this.detail() && this.detail()!.snapshot_id === this.history()?.current_snapshot_id,
  );
  constructor() {
    effect(() => {
      this.key();
      this.facade.context();
      const selected = untracked(this.selected);
      if (selected && !this.current(selected)) untracked(() => this.close());
    });
    inject(DestroyRef).onDestroy(() => this.cancel());
  }
  private current(selected: Selection | null): selected is Selection {
    return (
      !!selected &&
      selected === this.selected() &&
      selected.key === this.key() &&
      selected.context === this.facade.context() &&
      !!selected.context?.subject &&
      this.facade.permissions().has('catalog:read') &&
      !this.facade.authRequired()
    );
  }
  private cancel() {
    this.sequence++;
    this.read?.abort();
    this.read = undefined;
    this.loading.set(false);
  }
  close() {
    this.cancel();
    this.selected.set(null);
    this.page.set(null);
    this.version.set(null);
    this.failure.set('');
    this.showingVersion.set(false);
    this.lastVersion = '';
  }
  async open(target: TableLineageTarget) {
    this.close();
    this.selected.set({ target: { ...target }, key: this.key(), context: this.facade.context() });
    if (!this.current(this.selected())) {
      this.close();
      return;
    }
    await this.load(1);
    if (target.snapshotId && this.target()) await this.selectVersion(target.snapshotId);
  }
  async goToPage(page: number) {
    if (
      this.pending() ||
      !Number.isInteger(page) ||
      page < 1 ||
      page > (this.history()?.pages ?? 0)
    )
      return;
    this.showingVersion.set(false);
    await this.load(page);
  }
  back() {
    this.cancel();
    this.showingVersion.set(false);
    this.version.set(null);
    this.failure.set('');
  }
  async retry() {
    if (this.detailOpen()) await this.selectVersion(this.lastVersion);
    else await this.load(this.lastPage);
  }
  async selectVersion(snapshotId: string) {
    if (!snapshotId || snapshotId.length > 64) return;
    this.lastVersion = snapshotId;
    this.showingVersion.set(true);
    this.version.set(null);
    await this.request(async (selected, signal) => {
      const { datasetId, tableId } = selected.target;
      const result = await this.clients
        .get()
        .dataset.tableProvenance(this.facade.tenantId(), datasetId, tableId, snapshotId, {
          signal,
        });
      if (
        result.dataset_id !== datasetId ||
        result.table_id !== tableId ||
        result.snapshot_id !== snapshotId ||
        !['recorded', 'not_recorded'].includes(result.status) ||
        result.level !== 'file_section' ||
        (result.status === 'recorded' &&
          (!result.artifact || !result.run_id || !result.steps?.length))
      )
        throw Error('The provenance response does not match the requested version.');
      return () => this.version.set(result);
    });
  }
  private async load(page: number) {
    this.lastPage = page;
    this.version.set(null);
    this.page.set(null);
    await this.request(async (selected, signal) => {
      const { datasetId, tableId } = selected.target;
      const result = await this.clients
        .get()
        .dataset.tableSnapshots(this.facade.tenantId(), datasetId, tableId, {
          query: { page, page_size: 25 },
          signal,
        });
      if (
        result.page !== page ||
        result.page_size !== 25 ||
        !Number.isSafeInteger(result.total) ||
        result.total < 0 ||
        result.pages !== Math.ceil(result.total / 25) ||
        result.items.length > 25 ||
        new Set(result.items.map((item) => item.snapshot_id)).size !== result.items.length ||
        result.items.some((item) => item.dataset_id !== datasetId || item.table_id !== tableId)
      )
        throw Error('The version history does not match the requested table or page.');
      return () => this.page.set(result);
    });
  }
  private async request(read: (selected: Selection, signal: AbortSignal) => Promise<() => void>) {
    const selected = this.selected();
    if (!this.current(selected)) return;
    this.cancel();
    const sequence = this.sequence,
      controller = new AbortController();
    this.read = controller;
    this.loading.set(true);
    this.failure.set('');
    try {
      const apply = await read(selected, controller.signal);
      if (sequence === this.sequence && this.current(selected) && !controller.signal.aborted)
        apply();
    } catch (error) {
      if (sequence !== this.sequence || !this.current(selected) || controller.signal.aborted)
        return;
      if (error instanceof Error && 'status' in error && error.status === 401)
        this.facade.authRequired.set(true);
      this.failure.set(
        error instanceof Error ? error.message : 'Version history could not be loaded. Try again.',
      );
    } finally {
      if (sequence === this.sequence) this.loading.set(false);
    }
  }
}
