// Copyright 2026 Firefly Software Foundation
// SPDX-License-Identifier: Apache-2.0
import { TestBed } from '@angular/core/testing';
import type { CatalogEntry } from '@fireflyframework/koinon-sdk';
import { KoinonResourceList } from './resource-list';

function render(kind: CatalogEntry['kind'], status: string) {
  const fixture = TestBed.createComponent(KoinonResourceList);
  fixture.componentRef.setInput('items', [
    {
      id: 'asset',
      tenant_id: 'tenant',
      name: 'Reviewed resource',
      kind,
      status,
      description: '',
      metadata: {},
      created_at: '2026-11-02T00:00:00Z',
    },
  ]);
  fixture.detectChanges();
  return fixture.nativeElement.querySelector('.name-wrap') as HTMLElement;
}

it.each(['source', 'document', 'dataset', 'table'] as const)(
  'delegates %s ingestion state to observed availability instead of catalog pending',
  (kind) => {
    expect(render(kind, 'pending').querySelector(':scope > ffk-badge')).toBeNull();
  },
);
it.each(['source', 'document', 'dataset', 'table'] as const)(
  'keeps archived %s lifecycle visible independently of availability',
  (kind) => {
    expect(render(kind, 'archived').querySelector(':scope > ffk-badge')?.textContent).toContain(
      'Archived',
    );
  },
);
it('retains folder catalog status', () => {
  expect(
    render('collection', 'pending').querySelector(':scope > ffk-badge')?.textContent,
  ).toContain('Pending');
});
