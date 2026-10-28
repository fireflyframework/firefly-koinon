// Copyright 2026 Firefly Software Foundation
// SPDX-License-Identifier: Apache-2.0
import { TestBed } from '@angular/core/testing';
import type { AttachmentHistorySummary } from '@fireflyframework/koinon-sdk';
import { KoinonMessageText } from '../../../../chat/page/src/composer/message-text';
const file: AttachmentHistorySummary = {
  id: 'known-id',
  filename: 'Notes.txt',
  media_type: 'text/plain',
  kind: 'document',
  size_bytes: 5,
  sha256: 'a'.repeat(64),
  status: 'ready',
  revision: 1,
  expires_at: '2099-01-01T00:00:00Z',
  available: true,
};
async function mount(text: string, reference = file) {
  TestBed.configureTestingModule({ imports: [KoinonMessageText] });
  const fixture = TestBed.createComponent(KoinonMessageText);
  fixture.componentRef.setInput('text', text);
  fixture.componentRef.setInput('references', [reference]);
  fixture.detectChanges();
  await fixture.whenStable();
  return fixture;
}
it('formats only a verified source label while preserving business UUIDs', async () => {
  const fixture = await mount(
    'Invoice 00000000-0000-0000-0000-000000000001. Source: Attachment known-id: Notes.txt.',
  );
  expect(fixture.nativeElement.textContent).toBe(
    'Invoice 00000000-0000-0000-0000-000000000001. Source: Notes.txt.',
  );
  let selected: AttachmentHistorySummary | undefined;
  fixture.componentInstance.sourceSelected.subscribe((value) => (selected = value));
  fixture.nativeElement.querySelector('button').click();
  expect(selected).toEqual(file);
});
it('leaves unknown identities and mismatched filenames unchanged', async () => {
  const text = 'Attachment other-id: Notes.txt. Attachment known-id: Different.txt.';
  const fixture = await mount(text);
  expect(fixture.nativeElement.textContent).toBe(text);
  expect(fixture.nativeElement.querySelector('button')).toBeNull();
});
it('shows an expired source name without enabling original-file access', async () => {
  const fixture = await mount('Attachment known-id: Notes.txt', {
    ...file,
    available: false,
    status: 'expired',
  });
  expect(fixture.nativeElement.querySelector('button').disabled).toBe(true);
  expect(fixture.nativeElement.textContent).toBe('Notes.txt');
});
it('renders filenames as text and never interprets them as HTML', async () => {
  const filename = '<img src=x onerror=alert(1)>';
  const fixture = await mount('Attachment known-id: ' + filename, { ...file, filename });
  expect(fixture.nativeElement.querySelector('img')).toBeNull();
  expect(fixture.nativeElement.querySelector('button').textContent).toBe(filename);
});
