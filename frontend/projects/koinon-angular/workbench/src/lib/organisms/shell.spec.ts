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

it('uses the canonical compact wordmark while preserving custom logos and the full desktop family', async () => {
  const fixture = TestBed.createComponent(KoinonShell);
  await fixture.whenStable();
  fixture.componentInstance.compact.set(false);
  await fixture.whenStable();
  const image = () => (fixture.nativeElement as HTMLElement).querySelector('.brand img');
  expect(image()?.getAttribute('src')).toContain('/logos/firefly-koinon-lockup-color.svg');
  fixture.componentInstance.compact.set(true);
  fixture.componentRef.setInput('theme', 'dark');
  await fixture.whenStable();
  expect(image()?.getAttribute('src')).toContain('/logos/koinon-wordmark-reversed.svg');
  const custom = 'https://company.example/logos/firefly-koinon-lockup-reversed.svg';
  fixture.componentRef.setInput('brandLogo', custom);
  await fixture.whenStable();
  expect(image()?.getAttribute('src')).toBe(custom);
});

it('retains Foundation attribution and adds the canonical product credit only for custom identity', async () => {
  const fixture = TestBed.createComponent(KoinonShell);
  await fixture.whenStable();
  const root = fixture.nativeElement as HTMLElement;
  expect(root.querySelector('footer')?.textContent).toContain('Firefly Software Foundation');
  expect(root.querySelector('ffk-powered-by')).toBeNull();
  fixture.componentRef.setInput('customBrand', true);
  fixture.componentRef.setInput('theme', 'dark');
  fixture.componentRef.setInput('brandBase', '/embedded/brand');
  await fixture.whenStable();
  expect(root.querySelector('ffk-powered-by img')?.getAttribute('src')).toBe('/embedded/brand/logos/koinon-wordmark-reversed.svg');
  fixture.componentRef.setInput('customBrand', false);
  await fixture.whenStable();
  expect(root.querySelector('ffk-powered-by')).toBeNull();
});
