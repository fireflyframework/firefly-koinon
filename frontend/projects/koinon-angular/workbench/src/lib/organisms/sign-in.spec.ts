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

it('uses scoped self-hosted decorative artwork and keeps sign-in available when the image fails', async () => {
  const fixture = TestBed.createComponent(KoinonSignIn);
  fixture.componentRef.setInput('brandBase', '/embedded/brand');
  await fixture.whenStable();
  const root = fixture.nativeElement as HTMLElement,
    image = root.querySelector<HTMLImageElement>('.auth-scene')!;
  expect(image.getAttribute('src')).toBe('/embedded/brand/illustrations/knowledge-library.webp');
  expect(image.alt).toBe('');
  expect(image.getAttribute('aria-hidden')).toBe('true');
  image.dispatchEvent(new Event('error'));
  await fixture.whenStable();
  expect(root.querySelector('.auth-scene')).toBeNull();
  expect(root.querySelector<HTMLButtonElement>('.login-panel button')?.disabled).toBe(false);
});

it('uses the reversed native symbol in dark mode while preserving custom assistant artwork',async()=>{
 const fixture=TestBed.createComponent(KoinonSignIn);fixture.componentRef.setInput('theme','dark');fixture.componentRef.setInput('symbol','/assets/brand/logos/koinon-symbol-color.svg');await fixture.whenStable();const image=()=> (fixture.nativeElement as HTMLElement).querySelector('.login-panel img');expect(image()?.getAttribute('src')).toBe('/assets/brand/logos/koinon-symbol-reversed.svg');fixture.componentRef.setInput('symbol','data:image/png;base64,custom');await fixture.whenStable();expect(image()?.getAttribute('src')).toBe('data:image/png;base64,custom');
});
