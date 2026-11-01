// Copyright 2026 Firefly Software Foundation
// SPDX-License-Identifier: Apache-2.0
import { TestBed } from '@angular/core/testing';
import { KoinonSignIn } from './sign-in';
it('keeps authentication and theme controls available after the lazy sign-in screen loads', async () => {
  const fixture = TestBed.createComponent(KoinonSignIn);
  fixture.componentRef.setInput('customBrand', true);
  fixture.componentRef.setInput('productName', 'Northstar');
  fixture.componentRef.setInput('sessionEnded', true);
  const login = vi.fn(),
    theme = vi.fn();
  fixture.componentInstance.authenticationRequired.subscribe(login);
  fixture.componentInstance.themeChanged.subscribe(theme);
  await fixture.whenStable();
  const root = fixture.nativeElement as HTMLElement;
  expect(root.querySelector('h2')?.textContent).toBe('Welcome to Northstar');
  expect(root.querySelectorAll('ffk-powered-by').length).toBe(2);
  expect(root.querySelector('[role=status]')?.textContent).toContain('Your session has ended');
  root.querySelector<HTMLButtonElement>('.login-panel button')?.click();
  root.querySelector<HTMLButtonElement>('header button')?.click();
  expect(login).toHaveBeenCalledOnce();
  expect(theme).toHaveBeenCalledWith('dark');
});
