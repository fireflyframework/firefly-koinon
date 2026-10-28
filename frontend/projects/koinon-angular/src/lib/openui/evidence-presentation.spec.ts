// Copyright 2026 Firefly Software Foundation
// SPDX-License-Identifier: Apache-2.0
import { TestBed } from '@angular/core/testing';
import { KoinonEvidence } from '../../../chat/evidence/src/openui/evidence-renderer';
import { KoinonEvidenceContext } from '../../../chat/evidence/src/openui/evidence-context';
import type { Json } from '@fireflyframework/koinon-sdk';

it('keeps technical evidence in Audit and avoids empty or failed primary result cards', () => {
  TestBed.configureTestingModule({ imports: [KoinonEvidence], providers: [KoinonEvidenceContext] });
  const component = TestBed.createComponent(KoinonEvidence).componentInstance;
  const context = TestBed.inject(KoinonEvidenceContext);
  component.result.set({
    id: 'schema',
    run_id: 'run',
    kind: 'schema',
    data: { tables: [] },
  });
  expect(component.visible()).toBe(false);
  context.mode.set('audit');
  expect(component.visible()).toBe(true);
  context.mode.set('answer');
  component.result.set({
    id: 'query',
    run_id: 'run',
    kind: 'query',
    data: { query_id: 'q', execution_status: 'OK', preview: [] },
  });
  expect(component.visible()).toBe(false);
  component.result.set({
    id: 'query',
    run_id: 'run',
    kind: 'query',
    data: { query_id: 'q', execution_status: 'FAILED', preview: [{ count: 1 }] },
  });
  expect(component.visible()).toBe(false);
  component.result.set({
    id: 'query',
    run_id: 'run',
    kind: 'query',
    data: { query_id: 'q', execution_status: 'OK', preview: [{ count: 1 }] },
  });
  expect(component.visible()).toBe(true);
});

it('offers an optional chart only for a bounded finite numeric series and preserves exact numeric strings', () => {
  TestBed.configureTestingModule({ imports: [KoinonEvidence], providers: [KoinonEvidenceContext] });
  const component = TestBed.createComponent(KoinonEvidence).componentInstance;
  const rows = (preview: Record<string, Json>[]) =>
    component.result.set({
      id: 'result',
      run_id: 'run',
      kind: 'query',
      data: { query_id: 'query', execution_status: 'OK', preview },
    });
  rows([{ region: 'North', count: '9007199254740993' }]);
  expect(component.canChart()).toBe(false);
  expect(component.query()?.preview?.[0]['count']).toBe('9007199254740993');
  rows([
    { region: 'North', count: 18 },
    { region: 'South', count: 12 },
  ]);
  expect(component.canChart()).toBe(true);
  expect(component.selectedQueryView()).toBe('table');
  rows([{ count: Number.POSITIVE_INFINITY }]);
  expect(component.canChart()).toBe(false);
  rows(Array.from({ length: 101 }, (_, count) => ({ count })));
  expect(component.canChart()).toBe(false);
  rows([]);
  expect(component.canChart()).toBe(false);
});
