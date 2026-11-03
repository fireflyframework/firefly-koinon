// Copyright 2026 Firefly Software Foundation
// SPDX-License-Identifier: Apache-2.0
import { TestBed } from '@angular/core/testing';
import { expect, it } from 'vitest';
import { KoinonBadge } from './badge';
import { statusTone } from './badge';
import { Component } from '@angular/core';

it.each([
  ['succeeded', 'ready'], ['failed', 'error'], ['unknown', 'attention'],
  ['reconciling', 'attention'], ['processing', 'processing'], ['staged', 'neutral'],
  ['cancelled', 'attention'], ['queued', 'processing'],
])('gives %s its shared semantic tone', (status, tone) => expect(statusTone(status)).toBe(tone));

it.each(['ready', 'error', 'attention', 'processing'] as const)('pairs %s with a decorative status icon', tone => {
  const fixture = TestBed.createComponent(KoinonBadge);
  fixture.componentRef.setInput('tone', tone);
  fixture.detectChanges();
  const icon = fixture.nativeElement.querySelector('ffk-icon svg');
  expect(icon?.getAttribute('aria-hidden')).toBe('true');
  expect(fixture.nativeElement.querySelector('span')?.classList.contains(tone)).toBe(true);
});

@Component({ imports: [KoinonBadge], template: `<ffk-badge tone="error">Processing failed</ffk-badge>` })
class BadgeHost {}
it('retains accessible text beside a decorative failure icon', () => {
  const fixture = TestBed.createComponent(BadgeHost);
  fixture.detectChanges();
  const badge = fixture.nativeElement.querySelector('ffk-badge');
  expect({ text: badge.textContent.trim(), tone: badge.querySelector('span').className,
    iconHidden: badge.querySelector('svg').getAttribute('aria-hidden'),
    duplicateAnnouncement: badge.getAttribute('role') }).toEqual({
      text: 'Processing failed', tone: 'error', iconHidden: 'true', duplicateAnnouncement: null,
    });
});
