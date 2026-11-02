// Copyright 2026 Firefly Software Foundation
// SPDX-License-Identifier: Apache-2.0
import { TestBed } from '@angular/core/testing';
import { KoinonKnowledgeOverview } from './knowledge-overview';

it('offers only the current permitted tasks and does not emit a denied target', () => {
  const fixture = TestBed.createComponent(KoinonKnowledgeOverview);
  fixture.componentRef.setInput('sections', ['providers']);
  const requests: string[] = [];
  fixture.componentInstance.sectionRequested.subscribe((section) => requests.push(section));
  fixture.detectChanges();
  const root = fixture.nativeElement as HTMLElement;
  expect(root.querySelectorAll('.knowledge-task')).toHaveLength(1);
  expect(root.textContent).toContain('Manage connections');
  expect(root.textContent).not.toContain('Configure assistant');
  fixture.componentInstance.open('agents');
  expect(requests).toEqual([]);
  root.querySelector<HTMLButtonElement>('button')!.click();
  expect(requests).toEqual(['providers']);
});

it('distinguishes saved connection counts from recorded checks without reporting overall availability', () => {
  const fixture = TestBed.createComponent(KoinonKnowledgeOverview);
  fixture.componentRef.setInput('sections', ['providers', 'models']);
  fixture.componentRef.setInput('connections', { saved: 2, checked: 0 });
  fixture.detectChanges();
  const root = fixture.nativeElement as HTMLElement;
  const observations = root.querySelector('dl')!;
  expect([...observations.querySelectorAll('dd')].map((value) => value.textContent)).toEqual([
    '2',
    '0',
  ]);
  expect(root.textContent).not.toContain('Healthy');
  expect(root.textContent).toContain('Saved settings do not confirm');
  fixture.componentRef.setInput('connections', null);
  fixture.detectChanges();
  expect(root.querySelector('dl')).toBeNull();
});
