// Copyright 2026 Firefly Software Foundation SPDX-License-Identifier: Apache-2.0
import { Component } from '@angular/core';
import { TestBed } from '@angular/core/testing';
import { KoinonShell } from '../organisms/shell';
@Component({
  imports: [KoinonShell],
  template: `<ffk-shell
    ><button ffkHeaderNotifications>Open notifications</button>
    <p>Knowledge content</p></ffk-shell
  >`,
})
class HeaderSlotHost {}
it('projects a host-provided notification trigger into header actions without moving page content', () => {
  const fixture = TestBed.createComponent(HeaderSlotHost);
  fixture.detectChanges();
  expect(
    fixture.nativeElement.querySelector('.header-actions [ffkHeaderNotifications]')?.textContent,
  ).toBe('Open notifications');
  expect(fixture.nativeElement.querySelector('main')?.textContent).toContain('Knowledge content');
  expect(fixture.nativeElement.querySelector('main')?.textContent).not.toContain(
    'Open notifications',
  );
});
