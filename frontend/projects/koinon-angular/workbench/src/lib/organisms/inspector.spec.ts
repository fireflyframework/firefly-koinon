// Copyright 2026 Firefly Software Foundation SPDX-License-Identifier: Apache-2.0
import { TestBed, DeferBlockState } from '@angular/core/testing';
import { KoinonInspector } from './inspector';
it('keeps source attribution and table lineage actions intact after deferred rendering', async () => {
  const fixture = TestBed.createComponent(KoinonInspector);
  fixture.componentRef.setInput('entry', {
    id: 'dataset1',
    tenant_id: 'north',
    workspace_id: 'workspace1',
    kind: 'dataset',
    name: 'Sales data',
    description: 'Verified source',
    status: 'ready',
    created_at: '2026-10-30T10:00:00Z',
    created_by: 'private-subject',
    metadata: {},
  });
  fixture.componentRef.setInput('actors', { 'private-subject': { display_name: 'Sam' } });
  fixture.componentRef.setInput('schema', {
    tables: [{ id: 'table1', name: 'Sales', columns: [] }],
  });
  fixture.detectChanges();
  for (const block of await fixture.getDeferBlocks()) await block.render(DeferBlockState.Complete);
  fixture.detectChanges();
  expect(fixture.nativeElement.textContent).toContain('Sam');
  expect(fixture.nativeElement.textContent).not.toContain('private-subject');
  const emitted: unknown[] = [];
  fixture.componentInstance.tableHistoryRequested.subscribe((value) => emitted.push(value));
  const action = fixture.nativeElement.querySelector(
    'button[aria-label="History & lineage, Sales"]',
  ) as HTMLButtonElement;
  expect(action).not.toBeNull();
  action.click();
  expect(emitted).toEqual([{ id: 'table1', name: 'Sales' }]);
});
