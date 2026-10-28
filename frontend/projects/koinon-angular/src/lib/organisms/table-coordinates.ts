// Copyright 2026 Firefly Software Foundation
// SPDX-License-Identifier: Apache-2.0
import {
  ChangeDetectionStrategy,
  Component,
  effect,
  inject,
  input,
  signal,
  untracked,
} from '@angular/core';
import type {
  CoordinateColumnBinding,
  CoordinateSourceCell,
  TableCoordinateManifest,
} from '@fireflyframework/koinon-sdk';
import { KoinonTableCoordinates, type CoordinateTarget } from '../services/table-coordinates';
import {
  coordinateFormat,
  coordinateNumber,
  coordinateRange,
  jsonPointer,
  sheetCell,
  sheetColumn,
} from '../services/coordinate-labels';
import { KoinonTextPipe, KoinonValuePipe } from '../foundations/i18n';
import { KoinonBadge } from '../atoms/badge';
import { KoinonButton } from '../atoms/button';
import { KoinonSkeleton } from '../atoms/skeleton';
import { KoinonPagination } from '../molecules/pagination';
@Component({
  selector: 'ffk-table-coordinates',
  imports: [
    KoinonTextPipe,
    KoinonValuePipe,
    KoinonBadge,
    KoinonButton,
    KoinonSkeleton,
    KoinonPagination,
  ],
  providers: [KoinonTableCoordinates],
  templateUrl: './table-coordinates.html',
  styleUrl: './table-coordinates.scss',
  changeDetection: ChangeDetectionStrategy.OnPush,
})
export class KoinonTableCoordinatesView {
  readonly target = input.required<CoordinateTarget>();
  readonly state = inject(KoinonTableCoordinates);
  readonly row = signal('1');
  readonly column = signal('1');
  readonly number = coordinateNumber;
  readonly range = coordinateRange;
  readonly pointer = jsonPointer;
  readonly format = coordinateFormat;
  constructor() {
    effect(() => {
      const target = this.target();
      untracked(() => {
        this.row.set('1');
        this.column.set('1');
        void this.state.open(target);
      });
    });
  }
  setPosition(kind: 'row' | 'column', event: Event) {
    if (event.target instanceof HTMLInputElement)
      (kind === 'row' ? this.row : this.column).set(event.target.value);
  }
  locate(event: Event) {
    event.preventDefault();
    void this.state.find(this.row(), this.column());
  }
  coverage(value: TableCoordinateManifest['status']) {
    return {
      complete: 'Complete map',
      partial: 'Partial map',
      not_recorded: 'Coordinates not recorded',
    }[value];
  }
  isJson(manifest: TableCoordinateManifest) {
    return ['json_array', 'jsonl_record', 'single_object'].includes(manifest.row_kind ?? '');
  }
  originalRows(manifest: TableCoordinateManifest) {
    return manifest.row_kind === 'sheet_row'
      ? 'Original sheet rows'
      : manifest.row_kind === 'json_array'
        ? 'Original array items'
        : 'Original records';
  }
  field(column: CoordinateColumnBinding, manifest: TableCoordinateManifest) {
    if (manifest.row_kind === 'sheet_row') return sheetColumn(column.source_field_index);
    return column.source_path.length
      ? this.isJson(manifest)
        ? jsonPointer(column.source_path)
        : column.source_path.join(' / ')
      : coordinateNumber(column.source_field_index);
  }
  headers(column: CoordinateColumnBinding | CoordinateSourceCell) {
    return column.header_cells
      .map((cell) => sheetCell(cell.row, cell.column))
      .filter((value) => value !== null)
      .join(', ');
  }
  location(cell: CoordinateSourceCell, manifest: TableCoordinateManifest) {
    if (cell.source_row === null) return null;
    if (manifest.row_kind === 'sheet_row')
      return cell.source_column === null ? null : sheetCell(cell.source_row, cell.source_column);
    if (this.isJson(manifest))
      return (
        jsonPointer([
          ...(manifest.source_path ?? []),
          ...(manifest.row_kind === 'json_array' ? [cell.source_row] : []),
          ...cell.source_path,
        ]) || '/'
      );
    return cell.source_path.length
      ? cell.source_path.join(' / ')
      : coordinateNumber(cell.source_column);
  }
  options(manifest: TableCoordinateManifest) {
    const labels: Record<string, string> = {
      header: 'Header detected',
      skip_rows: 'Skipped rows',
      delimiter: 'Field separator',
      input_records: 'Input records',
      output_records: 'Output records',
      newline_normalization: 'Newline normalization',
      value_basis: 'Value basis',
    };
    return (manifest.parser_decisions ?? []).flatMap((option) =>
      labels[option.name] ? [{ label: labels[option.name], value: option.value }] : [],
    );
  }
}
