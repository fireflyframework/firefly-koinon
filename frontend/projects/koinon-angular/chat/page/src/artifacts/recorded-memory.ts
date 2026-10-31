// Copyright 2026 Firefly Software Foundation
// SPDX-License-Identifier: Apache-2.0
import { ChangeDetectionStrategy, Component, EventEmitter, Input, Output } from '@angular/core';
import {
  KoinonButton,
  KoinonDatePipe,
  KoinonTextPipe,
  KoinonValuePipe,
} from '@fireflyframework/koinon-angular';
import type { MemoryReceipt, MemoryTurnReference } from '@fireflyframework/koinon-sdk';

@Component({
  selector: 'ffk-recorded-memory',
  imports: [KoinonButton, KoinonDatePipe, KoinonTextPipe, KoinonValuePipe],
  templateUrl: './recorded-memory.html',
  styleUrl: './recorded-memory.scss',
  changeDetection: ChangeDetectionStrategy.OnPush,
})
export class KoinonRecordedMemory {
  @Input({ required: true }) receipt!: MemoryReceipt;
  @Output() conversationRequested = new EventEmitter<string>();
  availability(value: MemoryTurnReference['availability']) {
    return {
      available: 'Available conversation',
      archived: 'Archived conversation',
      deleted: 'Deleted conversation',
      moved: 'Conversation moved',
      memory_disabled: 'Memory disabled',
      changed: 'Conversation changed',
      unverified: 'Context not verified',
    }[value ?? 'unverified'];
  }
}
