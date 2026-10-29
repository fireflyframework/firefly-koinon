// Copyright 2026 Firefly Software Foundation SPDX-License-Identifier: Apache-2.0
import { TestBed } from '@angular/core/testing';
import { KoinonShell } from './shell';

it('renders the selected organization in both selectors when the authorized list first appears', async () => {
  const fixture = TestBed.createComponent(KoinonShell);
  fixture.componentRef.setInput('organizations', [
    { id: 'north', name: 'North' },
    { id: 'south', name: 'South' },
  ]);
  fixture.componentRef.setInput('tenantId', 'south');
  await fixture.whenStable();
  const root = fixture.nativeElement as HTMLElement;
  expect(root.querySelector('select')?.value).toBe('south');
  fixture.componentInstance.toggleNavigation();
  await fixture.whenStable();
  const selectors = [...root.querySelectorAll('select')];
  expect(selectors.length).toBe(2);
  for (const select of selectors) expect(select.value).toBe('south');
});
