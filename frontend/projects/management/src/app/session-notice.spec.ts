// Copyright 2026 Firefly Software Foundation
// SPDX-License-Identifier: Apache-2.0
import { signal } from '@angular/core';
import { TestBed } from '@angular/core/testing';
import type { KoinonWorkbench } from '@fireflyframework/koinon-angular/workbench';
import { SessionNotice } from './session-notice';
import { SessionService } from './session.service';

async function setup(surface = 'account') {
  const monitor = {
    remaining: signal<number | null>(60),
    renewing: signal(false),
    message: signal(''),
    canRenew: () => true,
    renew: vi.fn(),
    draft: { track: vi.fn() },
  };
  const workbench = {
    dialog: signal(null),
    f: { authRequired: signal(false), context: signal({ subject: 'alice' }) },
    i18n: { preferences: signal({ locale: 'en' }) },
  };
  TestBed.configureTestingModule({
    providers: [{ provide: SessionService, useValue: { monitor: async () => monitor } }],
  });
  const fixture = TestBed.createComponent(SessionNotice);
  fixture.componentRef.setInput('workbench', workbench as unknown as KoinonWorkbench);
  fixture.componentRef.setInput('surface', surface);
  fixture.detectChanges();
  await fixture.whenStable();
  fixture.detectChanges();
  return { fixture, monitor, workbench };
}

it('keeps healthy and unknown sessions absent and reveals account details only on demand', async () => {
  const { fixture, monitor } = await setup();
  const trigger = fixture.nativeElement.querySelector(
    'button[aria-controls="session-details"]',
  ) as HTMLButtonElement;
  expect(trigger?.textContent).toContain('Session');
  expect(fixture.nativeElement.textContent).not.toContain('Renew session');
  trigger.click();
  fixture.detectChanges();
  expect(fixture.nativeElement.textContent).toContain('Renew session');
  expect(fixture.nativeElement.querySelector('[role="timer"]')?.getAttribute('aria-live')).toBe(
    'off',
  );
  fixture.nativeElement.dispatchEvent(
    new KeyboardEvent('keydown', { key: 'Escape', bubbles: true }),
  );
  fixture.detectChanges();
  expect(trigger.getAttribute('aria-expanded')).toBe('false');
  for (const remaining of [28800, null]) {
    monitor.remaining.set(remaining);
    fixture.detectChanges();
    expect(fixture.nativeElement.querySelector('button')).toBe(null);
  }
});

it('uses a compact dialog safety row without a countdown and never submits renewal', async () => {
  const { fixture, monitor } = await setup('dialog');
  expect(fixture.nativeElement.querySelector('.notice.compact')).not.toBe(null);
  expect(fixture.nativeElement.querySelector('[role="timer"]')).toBe(null);
  const renew = fixture.nativeElement.querySelector('button') as HTMLButtonElement;
  expect(renew.type).toBe('button');
  renew.click();
  expect(monitor.renew).toHaveBeenCalledOnce();
});

it('leaves the authentication surface with its existing single sign-in action', async () => {
  const { fixture, workbench } = await setup('auth');
  workbench.f.authRequired.set(true);
  fixture.detectChanges();
  expect(fixture.nativeElement.textContent).toContain('Your session has ended.');
  expect(fixture.nativeElement.querySelector('button')).toBe(null);
});
