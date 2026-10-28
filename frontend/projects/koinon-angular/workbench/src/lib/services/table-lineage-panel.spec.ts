// Copyright 2026 Firefly Software Foundation
// SPDX-License-Identifier: Apache-2.0
import { signal } from '@angular/core';
import { TestBed } from '@angular/core/testing';
import { KoinonTableLineagePanel } from '../organisms/table-lineage-panel';
import { KoinonTableLineage } from './table-lineage';
import { KoinonI18n } from '../foundations/i18n';
import { KoinonClient, type KoinonTransport } from '@fireflyframework/koinon-sdk';
import { KoinonFacade } from '../koinon-facade';
import { KoinonClientContext } from './client-context';
const detail = { snapshot_id: 'past', status: 'not_recorded', snapshot_status: 'READY' };
function setup(value: Record<string, unknown> = detail) {
  const state = {
    target: signal({
      datasetId: 'dataset',
      tableId: 'table',
      datasetName: 'Sales',
      tableName: 'Orders',
    }),
    detail: signal(value),
    detailOpen: signal(true),
    history: signal(null),
    pending: signal(false),
    error: signal(''),
    isCurrent: signal(false),
    close: vi.fn(),
    back: vi.fn(),
  };
  TestBed.configureTestingModule({
    imports: [KoinonTableLineagePanel],
    providers: [{ provide: KoinonTableLineage, useValue: state }],
  });
  const fixture = TestBed.createComponent(KoinonTableLineagePanel);
  fixture.detectChanges();
  return { fixture, state };
}
it('explains missing historical origin without inventing an original or a current-version badge', () => {
  const { fixture } = setup();
  expect(fixture.nativeElement.textContent).toContain('cannot be inferred');
  expect(fixture.nativeElement.querySelector('.source')).toBeNull();
  expect(fixture.nativeElement.textContent).not.toContain('Current');
});
it('renders filenames and safe constructor fields as text without displaying arbitrary supplied parameters', () => {
  const { fixture } = setup({
    ...detail,
    status: 'recorded',
    artifact: {
      original_filename: '<img src=x onerror=alert(1)>.xlsx',
      byte_size: 42,
      admitted_at: '2026-10-27T10:00:00Z',
      file_format: 'xlsx',
      sha256: 'a'.repeat(64),
    },
    steps: [
      {
        id: 'step',
        ordinal: 1,
        kind: 'model_input',
        implementation: 'reader',
        recorded_at: '2026-10-27T10:00:00Z',
        parameters: {
          selected_model_id: 'recorded-model',
          instructions_sha256: 'b'.repeat(64),
          password: 'must-not-render',
          endpoint: 'must-not-render-endpoint',
        },
      },
    ],
  });
  const text = fixture.nativeElement.textContent;
  expect(text).toContain('<img src=x onerror=alert(1)>.xlsx');
  expect(text).toContain('recorded-model');
  expect(text).not.toContain('must-not-render');
  expect(fixture.nativeElement.querySelector('img,script,a')).toBeNull();
});
it('uses the viewer’s language while preserving recorded identities', () => {
  const { fixture } = setup();
  TestBed.inject(KoinonI18n).apply({
    locale: 'es-ES',
    time_zone: 'Europe/Madrid',
    response_language: 'es',
  });
  fixture.detectChanges();
  expect(fixture.nativeElement.textContent).toContain('Historial y trazabilidad');
  expect(fixture.nativeElement.textContent).toContain('no puede deducirse');
  expect(fixture.nativeElement.textContent).toContain('past');
});

it('loads source coordinates only after the selected-version disclosure is opened', async () => {
  let requests = 0;
  const transport: KoinonTransport = {
    request: async <T>() => {
      requests++;
      return {
        dataset_id: 'dataset',
        table_id: 'table',
        native_dataset_id: 'native-dataset',
        native_table_id: 'native-table',
        snapshot_id: 'past',
        status: 'not_recorded',
        index_base: 0,
      } as T;
    },
    stream: () => {
      throw Error('Unexpected inference');
    },
  };
  TestBed.configureTestingModule({
    providers: [
      {
        provide: KoinonFacade,
        useValue: {
          tenantId: signal('north'),
          workspaceId: signal('w'),
          projectId: signal('p'),
          context: signal({ subject: 'owner' }),
          permissions: signal(new Set(['catalog:read'])),
          authRequired: signal(false),
        },
      },
      {
        provide: KoinonClientContext,
        useValue: { revision: signal(0), get: () => new KoinonClient({ transport }) },
      },
    ],
  });
  const { fixture } = setup();
  expect(fixture.nativeElement.querySelector('ffk-table-coordinates')).toBeNull();
  expect(requests).toBe(0);
  const toggle = (
    Array.from(fixture.nativeElement.querySelectorAll('button')) as HTMLButtonElement[]
  ).find((button) => button.textContent?.includes('Source coordinates'));
  expect(toggle).toBeTruthy();
  toggle!.click();
  fixture.detectChanges();
  await vi.waitFor(() =>
    expect(fixture.nativeElement.textContent).toContain('Coordinates not recorded'),
  );
  expect(requests).toBe(1);
  expect(toggle!.getAttribute('aria-expanded')).toBe('true');
  toggle!.click();
  fixture.detectChanges();
  expect(fixture.nativeElement.querySelector('ffk-table-coordinates')).toBeNull();
});
