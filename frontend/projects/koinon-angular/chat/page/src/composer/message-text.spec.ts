// Copyright 2026 Firefly Software Foundation SPDX-License-Identifier: Apache-2.0
import { TestBed } from '@angular/core/testing';
import type { AttachmentHistorySummary } from '@fireflyframework/koinon-sdk';
import { KoinonMessageText } from './message-text';

it('keeps Attachment references interactive only in prose around fenced code', async () => {
  TestBed.configureTestingModule({ imports: [KoinonMessageText] });
  const fixture = TestBed.createComponent(KoinonMessageText);
  const file: AttachmentHistorySummary = {
    id: 'file-one',
    filename: 'Notes.txt',
    media_type: 'text/plain',
    kind: 'document',
    size_bytes: 10,
    sha256: 'a'.repeat(64),
    status: 'ready',
    revision: 1,
    expires_at: '2099-01-01T00:00:00Z',
    available: true,
  };
  const code = 'Attachment file-one: Notes.txt\n<img src=x onerror=alert(1)>\n';
  fixture.componentRef.setInput(
    'text',
    'Attachment file-one: Notes.txt\n```unknown\n' + code + '```\nAfter',
  );
  fixture.componentRef.setInput('references', [file]);
  fixture.detectChanges();
  await fixture.whenStable();
  fixture.detectChanges();
  const sources = fixture.nativeElement.querySelectorAll('button[title="Download source file"]');
  expect(sources).toHaveLength(1);
  expect(fixture.nativeElement.querySelector('pre').textContent).toBe(code);
  expect(fixture.nativeElement.querySelector('img,script')).toBeNull();
  const selected = vi.fn();
  fixture.componentInstance.sourceSelected.subscribe(selected);
  sources[0].click();
  expect(selected).toHaveBeenCalledExactlyOnceWith(file);
});
