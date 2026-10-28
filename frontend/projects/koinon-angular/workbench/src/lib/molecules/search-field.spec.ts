// Copyright 2026 Firefly Software Foundation SPDX-License-Identifier: Apache-2.0
import { TestBed } from '@angular/core/testing';
import { KoinonSearchField } from './search-field';

describe('search field input', () => {
  it('waits for composition to finish before emitting or submitting a search', async () => {
    const fixture = TestBed.createComponent(KoinonSearchField);
    fixture.detectChanges();
    await fixture.whenStable();
    const field = fixture.componentInstance;
    const changes: string[] = [],
      searches: string[] = [];
    field.valueChange.subscribe((value) => changes.push(value));
    field.searchSubmitted.subscribe((value) => searches.push(value));
    const input = fixture.nativeElement.querySelector('input') as HTMLInputElement;
    input.dispatchEvent(new CompositionEvent('compositionstart', { bubbles: true }));
    input.value = '知';
    input.dispatchEvent(new InputEvent('input', { bubbles: true, isComposing: true }));
    fixture.nativeElement
      .querySelector('form')
      .dispatchEvent(new Event('submit', { bubbles: true, cancelable: true }));
    expect(changes).toEqual([]);
    expect(searches).toEqual([]);
    input.value = '知識';
    input.dispatchEvent(new CompositionEvent('compositionend', { bubbles: true }));
    fixture.detectChanges();
    expect(changes).toEqual(['知識']);
    fixture.nativeElement
      .querySelector('form')
      .dispatchEvent(new Event('submit', { bubbles: true, cancelable: true }));
    expect(searches).toEqual(['知識']);
  });
});
