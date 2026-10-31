// Copyright 2026 Firefly Software Foundation
// SPDX-License-Identifier: Apache-2.0
import { TestBed } from '@angular/core/testing';
import type { MemoryReceipt } from '@fireflyframework/koinon-sdk';
import { KoinonRecordedMemory } from '../../../../chat/page/src/artifacts/recorded-memory';

const receipt: MemoryReceipt = {
  validation_mode: 'historical_replay',
  generation_id: 'generation',
  mode: 'personal_project',
  scope_sha256: 'a'.repeat(64),
  manifest_sha256: 'b'.repeat(64),
  organization_policy_revision: 7,
  effective_policy: {
    allow_project_memory: true,
    max_history_messages: 30,
    max_history_tokens: 4096,
    max_project_memory_messages: 12,
  },
  dependency_count: 1,
  context_available: false,
  unavailable_dependency_count: 1,
  created_at: '2026-10-30T12:00:00Z',
  turns: [
    {
      run_id: 'run',
      thread_id: 'original',
      conversation_title: 'Service ownership',
      user_created_at: '2026-10-29T12:00:00Z',
      user_message_id: 'question',
      user_sha256: 'c'.repeat(64),
      answer_message_id: 'answer',
      answer_sha256: 'd'.repeat(64),
      answer_included: true,
      availability: 'deleted',
    },
  ],
};
it('separates recorded memory from source evidence and never offers a deleted chat', async () => {
  const fixture = TestBed.createComponent(KoinonRecordedMemory);
  fixture.componentRef.setInput('receipt', receipt);
  fixture.detectChanges();
  await fixture.whenStable();
  const text = fixture.nativeElement.textContent;
  expect(text).toContain('Service ownership');
  expect(text).toContain('Deleted conversation');
  expect(text).toContain('Question and answer were included');
  expect(text).toContain(
    'Conversation context is separate from the sources used to verify this answer.',
  );
  expect(text).toContain('Some recorded context is no longer available for reuse.');
  expect(fixture.nativeElement.querySelector('button')).toBeNull();
});
it('opens only an available recorded conversation through its explicit action', () => {
  const fixture = TestBed.createComponent(KoinonRecordedMemory);
  fixture.componentRef.setInput('receipt', {
    ...receipt,
    context_available: true,
    turns: [{ ...receipt.turns![0], availability: 'available' }],
  });
  fixture.detectChanges();
  const open = vi.fn();
  fixture.componentInstance.conversationRequested.subscribe(open);
  (fixture.nativeElement.querySelector('button') as HTMLButtonElement).click();
  expect(open).toHaveBeenCalledExactlyOnceWith('original');
});
