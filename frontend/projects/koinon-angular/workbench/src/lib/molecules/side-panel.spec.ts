// Copyright 2026 Firefly Software Foundation
// SPDX-License-Identifier: Apache-2.0
import { TestBed } from '@angular/core/testing';
import { KoinonSidePanel } from './side-panel';
it('keeps a controlled labeled panel and emits the Escape dismissal intent', () => {
  TestBed.configureTestingModule({ imports: [KoinonSidePanel] });
  const fixture = TestBed.createComponent(KoinonSidePanel);
  fixture.componentRef.setInput('heading', 'Recorded activity');
  fixture.componentRef.setInput('open', true);
  fixture.detectChanges();
  const dialog: HTMLDialogElement = fixture.nativeElement.querySelector('dialog');
  expect(dialog.open).toBe(true);
  expect(dialog.getAttribute('aria-labelledby')).toBeTruthy();
  const closed = vi.fn();
  fixture.componentInstance.closed.subscribe(closed);
  dialog.dispatchEvent(new Event('cancel', { cancelable: true }));
  expect(closed).toHaveBeenCalledOnce();
  fixture.componentRef.setInput('open', false);
  fixture.detectChanges();
  expect(dialog.open).toBe(false);
  fixture.destroy();
});
