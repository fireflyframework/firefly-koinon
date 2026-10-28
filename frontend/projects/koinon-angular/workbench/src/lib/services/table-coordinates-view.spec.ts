// Copyright 2026 Firefly Software Foundation
// SPDX-License-Identifier: Apache-2.0
import { signal } from '@angular/core';
import { TestBed, type ComponentFixture } from '@angular/core/testing';
import {
  KoinonClient,
  type KoinonTransport,
  type RequestOptions,
} from '@fireflyframework/koinon-sdk';
import { KoinonTableCoordinatesView } from '../organisms/table-coordinates';
import { KoinonFacade } from '../koinon-facade';
import { KoinonClientContext } from './client-context';
import { KoinonI18n } from '../foundations/i18n';
const target = { datasetId: 'dataset', tableId: 'table', snapshotId: 'selected' };
const manifest = {
  dataset_id: 'dataset',
  table_id: 'table',
  native_dataset_id: 'native-dataset',
  native_table_id: 'native-table',
  snapshot_id: 'selected',
  status: 'complete',
  index_base: 0,
  row_count: 2,
  column_count: 2,
  artifact_id: 'artifact',
  run_id: 'run',
  input_sha256: 'a'.repeat(64),
  mapping_sha256: 'b'.repeat(64),
  source_format: 'excel',
  source_variant: 'xlsx',
  row_kind: 'sheet_row',
  source_sheet: 'Orders',
  source_path: [],
  parser_decisions: [],
  dependencies: [],
  rejected_source_rows: [],
};
async function setup(mode: 'complete' | 'not_recorded' | 'json' | 'jsonl' | 'empty' = 'complete') {
  const calls: { path: string; options?: RequestOptions }[] = [];
  const value =
    mode === 'not_recorded'
      ? {
          dataset_id: 'dataset',
          table_id: 'table',
          native_dataset_id: 'native-dataset',
          native_table_id: 'native-table',
          snapshot_id: 'selected',
          status: 'not_recorded',
          index_base: 0,
        }
      : mode === 'json' || mode === 'jsonl'
        ? {
            ...manifest,
            source_format: mode === 'jsonl' ? 'jsonl' : 'json',
            source_variant: mode === 'jsonl' ? 'jsonl_record' : 'json_array',
            row_kind: mode === 'jsonl' ? 'jsonl_record' : 'json_array',
            source_sheet: null,
            source_path: mode === 'jsonl' ? [] : ['a/b'],
          }
        : mode === 'empty'
          ? { ...manifest, row_count: 0 }
          : manifest;
  const transport: KoinonTransport = {
    request: async <T>(_method: unknown, path: string, options?: RequestOptions) => {
      calls.push({ path, options });
      return (
        path.endsWith('/cells')
          ? {
              manifest: value,
              items: [
                {
                  output_row: 0,
                  output_column: 1,
                  source_row: mode === 'json' || mode === 'jsonl' ? 0 : 4,
                  source_column: mode === 'json' || mode === 'jsonl' ? null : 6,
                  source_path: mode === 'json' || mode === 'jsonl' ? ['amount'] : [],
                  header_cells: mode === 'json' || mode === 'jsonl' ? [] : [{ row: 3, column: 6 }],
                  source_type: null,
                },
              ],
            }
          : value
      ) as T;
    },
    stream: () => {
      throw Error('Unexpected inference');
    },
  };
  const facade = {
    tenantId: signal('north'),
    workspaceId: signal('w'),
    projectId: signal('p'),
    context: signal({ subject: 'owner' }),
    permissions: signal(new Set(['catalog:read'])),
    authRequired: signal(false),
  };
  TestBed.configureTestingModule({
    imports: [KoinonTableCoordinatesView],
    providers: [
      { provide: KoinonFacade, useValue: facade },
      {
        provide: KoinonClientContext,
        useValue: { revision: signal(0), get: () => new KoinonClient({ transport }) },
      },
    ],
  });
  const fixture = TestBed.createComponent(KoinonTableCoordinatesView);
  fixture.componentRef.setInput('target', target);
  fixture.detectChanges();
  await fixture.whenStable();
  await vi.waitFor(() => expect(fixture.componentInstance.state.manifest()).not.toBeNull());
  fixture.detectChanges();
  return { fixture, calls, facade };
}
it('loads the manifest through the SDK and keeps technical facts closed by default', async () => {
  const { fixture, calls } = await setup();
  expect(calls).toHaveLength(1);
  expect(fixture.nativeElement.textContent).toContain('Excel workbook');
  expect(fixture.nativeElement.textContent).toContain('Complete map');
  expect(fixture.nativeElement.querySelector('details').open).toBe(false);
});
it('locates an exact source cell with human indices and recorded header provenance, without values', async () => {
  const { fixture, calls } = await setup();
  const buttons = Array.from(
    fixture.nativeElement.querySelectorAll('button'),
  ) as HTMLButtonElement[];
  buttons.find((button) => button.textContent?.includes('Locate a cell'))!.click();
  fixture.detectChanges();
  const column = fixture.nativeElement.querySelector('input[name="column"]') as HTMLInputElement;
  column.value = '2';
  column.dispatchEvent(new Event('input'));
  fixture.nativeElement
    .querySelector('form')
    .dispatchEvent(new Event('submit', { cancelable: true }));
  await fixture.whenStable();
  await vi.waitFor(() => expect(fixture.componentInstance.state.selection()).not.toBeNull());
  fixture.detectChanges();
  expect(calls.at(-1)?.options?.body).toEqual({
    snapshot_id: 'selected',
    cells: [{ row: 0, column: 1 }],
  });
  expect(fixture.nativeElement.textContent).toContain('G5');
  expect(fixture.nativeElement.textContent).toContain('G4');
  expect(fixture.nativeElement.querySelector('img,iframe')).toBeNull();
});
it('preserves unknown mapping coverage without claiming current coordinates', async () => {
  const { fixture, calls } = await setup('not_recorded');
  expect(fixture.nativeElement.textContent).toContain('Coordinates not recorded');
  expect(fixture.nativeElement.querySelector('form')).toBeNull();
  expect(calls).toHaveLength(1);
});
it('explains one-based UI and original JSON indexing in Spanish', async () => {
  const { fixture } = await setup('json');
  TestBed.inject(KoinonI18n).apply({ locale: 'es-ES', time_zone: 'UTC', response_language: 'es' });
  fixture.detectChanges();
  expect(fixture.nativeElement.textContent).toContain('comienzan en 1');
  expect(fixture.nativeElement.textContent).toContain('comienzan en 0');
});

async function locate(fixture: ComponentFixture<KoinonTableCoordinatesView>) {
  const buttons = Array.from(
    fixture.nativeElement.querySelectorAll('button'),
  ) as HTMLButtonElement[];
  buttons.find((button) => button.textContent?.includes('Locate a cell'))!.click();
  fixture.detectChanges();
  const column = fixture.nativeElement.querySelector('input[name="column"]') as HTMLInputElement;
  column.value = '2';
  column.dispatchEvent(new Event('input'));
  fixture.nativeElement
    .querySelector('form')
    .dispatchEvent(new Event('submit', { cancelable: true }));
  await vi.waitFor(() => expect(fixture.componentInstance.state.selection()).not.toBeNull());
  fixture.detectChanges();
}
it('keeps the original JSONL record identity alongside its relative field path', async () => {
  const { fixture } = await setup('jsonl');
  await locate(fixture);
  expect(fixture.nativeElement.querySelector('.location')?.textContent).toContain('/amount');
  expect(fixture.nativeElement.querySelector('.location')?.textContent).toContain(
    'Original record 1',
  );
});
it('shows the exact selected-array JSON pointer rather than a guessed flattened field', async () => {
  const { fixture } = await setup('json');
  await locate(fixture);
  expect(fixture.nativeElement.querySelector('.location')?.textContent).toContain('/a~1b/0/amount');
});
it('keeps a record field identity instead of presenting the record number as a cell', async () => {
  const { fixture } = await setup();
  const manifest = fixture.componentInstance.state.manifest()!;
  expect(
    fixture.componentInstance.location(
      {
        output_row: 0,
        output_column: 1,
        source_row: 4,
        source_column: 1,
        source_path: ['amount'],
        header_cells: [],
        source_type: null,
      },
      { ...manifest, row_kind: 'record', source_format: 'csv' },
    ),
  ).toBe('amount');
});

it('shows an empty state instead of a 1–0 range or an impossible cell form', async () => {
  const { fixture, calls } = await setup('empty');
  const buttons = Array.from(
    fixture.nativeElement.querySelectorAll('button'),
  ) as HTMLButtonElement[];
  buttons.find((button) => button.textContent?.includes('Locate a cell'))!.click();
  fixture.detectChanges();
  expect(fixture.nativeElement.querySelector('form')).toBeNull();
  expect(fixture.nativeElement.textContent).toContain('This version has no cells to locate.');
  expect(fixture.nativeElement.textContent).not.toContain('1–0');
  expect(calls).toHaveLength(1);
});
