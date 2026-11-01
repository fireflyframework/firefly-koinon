// Copyright 2026 Firefly Software Foundation SPDX-License-Identifier: Apache-2.0
import { Component } from '@angular/core';
import { TestBed } from '@angular/core/testing';
import { KoinonButton } from '../atoms/button';
@Component({
  imports: [KoinonButton],
  template: `<ffk-button variant="back" icon="chevron-left">Back to people</ffk-button>
    <h2>Choose access</h2>`,
})
class BackNavigationHost {}
it('aligns page-back content with the heading edge without reducing its touch target', () => {
  const fixture = TestBed.createComponent(BackNavigationHost);
  fixture.detectChanges();
  const button = fixture.nativeElement.querySelector('button') as HTMLButtonElement;
  const style = getComputedStyle(button);
  expect(parseFloat(style.paddingInline)).toBe(0);
  expect(style.borderWidth).toBe('0px');
  expect(parseInt(style.minHeight, 10)).toBeGreaterThanOrEqual(40);
  expect(button.type).toBe('button');
  expect(button.textContent).toContain('Back to people');
});
