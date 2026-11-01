// Copyright 2026 Firefly Software Foundation SPDX-License-Identifier: Apache-2.0
import { TestBed } from '@angular/core/testing';
import { KoinonNotificationTrigger } from '../../../../communications/notification-trigger';
it('announces the actual unread count while keeping a bounded visual badge', () => {
  const fixture = TestBed.createComponent(KoinonNotificationTrigger);
  fixture.componentRef.setInput('unread', 101);
  fixture.detectChanges();
  const button = fixture.nativeElement.querySelector('button') as HTMLButtonElement;
  expect(button.getAttribute('aria-label')).toBe('Notifications, 101 unread');
  expect(fixture.nativeElement.querySelector('.count')?.textContent).toBe('99+');
  let opens = 0;
  fixture.componentInstance.opened.subscribe(() => opens++);
  button.click();
  expect(opens).toBe(1);
});
it('does not invent a count while notification state is unavailable', () => {
  const fixture = TestBed.createComponent(KoinonNotificationTrigger);
  fixture.detectChanges();
  expect(fixture.nativeElement.querySelector('.count')).toBeNull();
  expect(fixture.nativeElement.querySelector('button')?.getAttribute('aria-label')).toBe(
    'Notifications',
  );
});
