// Copyright 2026 Firefly Software Foundation
// SPDX-License-Identifier: Apache-2.0
import { Injectable, DestroyRef, computed, effect, inject, signal, untracked } from '@angular/core';
import type {
  ContextResponse,
  CoordinatePage,
  TableCoordinateManifest,
  TableCoordinateSelection,
  TableRowRangePage,
  TableColumnBindingPage,
} from '@fireflyframework/koinon-sdk';
import { KoinonFacade } from '../koinon-facade';
import { KoinonClientContext } from './client-context';

export interface CoordinateTarget {
  datasetId: string;
  tableId: string;
  snapshotId: string;
}
export type CoordinateView = 'rows' | 'columns' | 'cell';
interface Selection {
  target: CoordinateTarget;
  key: string;
  context: ContextResponse | null;
  tenantId: string;
}
const mismatch = 'The source coordinates do not match the selected version.';
const positive = (value: unknown) =>
  typeof value === 'number' && Number.isSafeInteger(value) && value >= 0;
@Injectable()
export class KoinonTableCoordinates {
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
  private readonly descriptor = signal<TableCoordinateManifest | null>(null);
  private readonly rowData = signal<TableRowRangePage | null>(null);
  private readonly columnData = signal<TableColumnBindingPage | null>(null);
  private readonly pointData = signal<TableCoordinateSelection | null>(null);
  private readonly failure = signal('');
  private readonly loading = signal(false);
  private readonly view = signal<CoordinateView | null>(null);
  private sequence = 0;
  private read?: AbortController;
  private lastRead: CoordinateView | 'manifest' = 'manifest';
  private lastPage = 1;
  private lastRow = '1';
  private lastColumn = '1';
  readonly target = computed(() =>
    this.current(this.selected()) ? this.selected()!.target : null,
  );
  readonly manifest = computed(() => (this.target() ? this.descriptor() : null));
  readonly rowsPage = computed(() => (this.target() ? this.rowData() : null));
  readonly columnsPage = computed(() => (this.target() ? this.columnData() : null));
  readonly selection = computed(() => (this.target() ? this.pointData() : null));
  readonly error = computed(() => (this.target() ? this.failure() : ''));
  readonly pending = computed(() => !!this.target() && this.loading());
  readonly tab = computed(() => (this.target() ? this.view() : null));
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
  private clearData() {
    this.descriptor.set(null);
    this.rowData.set(null);
    this.columnData.set(null);
    this.pointData.set(null);
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
    this.clearData();
    this.failure.set('');
    this.view.set(null);
  }
  async open(target: CoordinateTarget) {
    this.close();
    if (Object.values(target).some((id) => !id || id.length > 64)) return;
    this.selected.set({
      target: { ...target },
      key: this.key(),
      context: this.facade.context(),
      tenantId: this.facade.tenantId(),
    });
    if (!this.current(this.selected())) {
      this.close();
      return;
    }
    this.lastRead = 'manifest';
    await this.request(async (selected, signal) => {
      const t = selected.target;
      const result = await this.clients
        .get()
        .dataset.tableCoordinates(selected.tenantId, t.datasetId, t.tableId, t.snapshotId, {
          signal,
        });
      this.validateManifest(result, selected);
      return () => this.descriptor.set(result);
    });
  }
  async choose(view: CoordinateView) {
    if (!this.manifest() || this.manifest()!.status === 'not_recorded') return;
    this.view.set(view);
    this.failure.set('');
    if (view === 'rows') await this.readRows(1);
    else if (view === 'columns') await this.readColumns(1);
    else {
      this.cancel();
      this.pointData.set(null);
    }
  }
  async pageRows(page: number) {
    if (
      !this.pending() &&
      Number.isSafeInteger(page) &&
      page >= 1 &&
      page <= (this.rowsPage()?.pages ?? 0)
    )
      await this.readRows(page);
  }
  async pageColumns(page: number) {
    if (
      !this.pending() &&
      Number.isSafeInteger(page) &&
      page >= 1 &&
      page <= (this.columnsPage()?.pages ?? 0)
    )
      await this.readColumns(page);
  }
  private async readRows(page: number) {
    this.lastRead = 'rows';
    this.lastPage = page;
    this.rowData.set(null);
    await this.request(async (selected, signal) => {
      const t = selected.target;
      const result = await this.clients
        .get()
        .dataset.tableCoordinateRows(selected.tenantId, t.datasetId, t.tableId, t.snapshotId, {
          query: { page, page_size: 25 },
          signal,
        });
      this.validatePage(result, selected, page, result.items.length);
      let end = 0;
      if (
        result.items.some((row) => {
          const bad =
            !positive(row.output_start) ||
            !positive(row.count) ||
            row.count < 1 ||
            !positive(row.source_start) ||
            !positive(row.source_stride) ||
            row.source_stride < 1 ||
            row.output_start < end ||
            row.output_start + row.count > (result.manifest.row_count ?? 0);
          end = row.output_start + row.count;
          return bad;
        })
      )
        throw Error(mismatch);
      return () => this.rowData.set(result);
    });
  }
  private async readColumns(page: number) {
    this.lastRead = 'columns';
    this.lastPage = page;
    this.columnData.set(null);
    await this.request(async (selected, signal) => {
      const t = selected.target;
      const result = await this.clients
        .get()
        .dataset.tableCoordinateColumns(selected.tenantId, t.datasetId, t.tableId, t.snapshotId, {
          query: { page, page_size: 25 },
          signal,
        });
      this.validatePage(result, selected, page, result.items.length);
      let previous = -1;
      if (
        result.total > (result.manifest.column_count ?? 0) ||
        (result.manifest.status === 'complete' && result.total !== result.manifest.column_count) ||
        result.items.some((column) => {
          const bad =
            !positive(column.output_position) ||
            column.output_position <= previous ||
            column.output_position >= (result.manifest.column_count ?? 0);
          previous = column.output_position;
          return bad;
        })
      )
        throw Error(mismatch);
      return () => this.columnData.set(result);
    });
  }
  async find(row: string, column: string) {
    const manifest = this.manifest();
    if (!manifest || manifest.status === 'not_recorded') return;
    this.cancel();
    this.pointData.set(null);
    const r = Number(row),
      c = Number(column);
    if (
      !/^\d+$/.test(row) ||
      !/^\d+$/.test(column) ||
      !Number.isSafeInteger(r) ||
      !Number.isSafeInteger(c) ||
      r < 1 ||
      c < 1 ||
      r > (manifest.row_count ?? 0) ||
      c > (manifest.column_count ?? 0)
    ) {
      this.failure.set('Choose a row and column within this version.');
      return;
    }
    this.lastRead = 'cell';
    this.lastRow = row;
    this.lastColumn = column;
    await this.request(async (selected, signal) => {
      const t = selected.target;
      const result = await this.clients
        .get()
        .dataset.tableCoordinateCells(
          selected.tenantId,
          t.datasetId,
          t.tableId,
          { snapshot_id: t.snapshotId, cells: [{ row: r - 1, column: c - 1 }] },
          { signal },
        );
      this.validateManifest(result.manifest, selected, true);
      const cell = result.items[0];
      if (
        result.items.length !== 1 ||
        cell.output_row !== r - 1 ||
        cell.output_column !== c - 1 ||
        (cell.source_row !== null && !positive(cell.source_row)) ||
        (cell.source_column !== null && !positive(cell.source_column)) ||
        (result.manifest.status === 'complete' && cell.source_row === null) ||
        cell.header_cells.some((position) => !positive(position.row) || !positive(position.column))
      )
        throw Error(mismatch);
      return () => this.pointData.set(result);
    });
  }
  async retry() {
    const target = this.target();
    if (!target) return;
    if (!this.manifest() || this.lastRead === 'manifest') await this.open(target);
    else if (this.lastRead === 'rows') await this.readRows(this.lastPage);
    else if (this.lastRead === 'columns') await this.readColumns(this.lastPage);
    else await this.find(this.lastRow, this.lastColumn);
  }
  private validateManifest(row: TableCoordinateManifest, selected: Selection, compare = false) {
    const t = selected.target;
    if (
      !row ||
      row.dataset_id !== t.datasetId ||
      row.table_id !== t.tableId ||
      row.snapshot_id !== t.snapshotId ||
      (row.index_base !== undefined && row.index_base !== 0) ||
      !['complete', 'partial', 'not_recorded'].includes(row.status)
    )
      throw Error(mismatch);
    if (row.status === 'not_recorded') {
      if (
        [
          row.row_count,
          row.column_count,
          row.artifact_id,
          row.run_id,
          row.input_sha256,
          row.mapping_sha256,
          row.source_format,
          row.row_kind,
        ].some((value) => value != null)
      )
        throw Error(mismatch);
    } else if (
      !positive(row.row_count) ||
      !positive(row.column_count) ||
      !row.artifact_id ||
      !row.run_id ||
      !row.source_format ||
      !row.row_kind ||
      !/^[a-f0-9]{64}$/.test(row.input_sha256 ?? '') ||
      !/^[a-f0-9]{64}$/.test(row.mapping_sha256 ?? '') ||
      (row.status === 'partial') !== !!row.reason_code
    )
      throw Error(mismatch);
    const original = this.manifest();
    if (
      compare &&
      original &&
      (
        [
          'status',
          'mapping_sha256',
          'input_sha256',
          'native_dataset_id',
          'native_table_id',
          'artifact_id',
          'run_id',
          'row_count',
          'column_count',
        ] as const
      ).some((key) => row[key] !== original[key])
    )
      throw Error(mismatch);
  }
  private validatePage(result: CoordinatePage, selected: Selection, page: number, length: number) {
    this.validateManifest(result.manifest, selected, true);
    if (
      !positive(result.total) ||
      result.page !== page ||
      result.page_size !== 25 ||
      result.pages !== Math.ceil(result.total / 25) ||
      typeof result.has_next !== 'boolean' ||
      typeof result.has_previous !== 'boolean' ||
      result.has_next !== page * 25 < result.total ||
      result.has_previous !== page > 1 ||
      length !== Math.min(25, Math.max(0, result.total - (page - 1) * 25))
    )
      throw Error(mismatch);
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
      if (error instanceof Error && 'status' in error) {
        if (error.status === 401) this.facade.authRequired.set(true);
        else if (error.status === 403 || error.status === 404) this.clearData();
      }
      this.failure.set(
        error instanceof Error
          ? error.message
          : 'Source coordinates could not be loaded. Try again.',
      );
    } finally {
      if (sequence === this.sequence) this.loading.set(false);
    }
  }
}
