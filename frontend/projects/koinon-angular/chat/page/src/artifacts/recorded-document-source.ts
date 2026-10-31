// Copyright 2026 Firefly Software Foundation
// SPDX-License-Identifier: Apache-2.0
import {
  ChangeDetectionStrategy,
  Component,
  EventEmitter,
  Input,
  OnChanges,
  OnDestroy,
  Output,
  PendingTasks,
  inject,
} from '@angular/core';
import {
  KoinonButton,
  KoinonIcon,
  KoinonSidePanel,
  KoinonSkeleton,
  KoinonTextPipe,
} from '@fireflyframework/koinon-angular';
import type { SourceReference } from '@fireflyframework/koinon-sdk';
import { KoinonRecordedDocumentSourceState } from './recorded-document-source-state';
import { registerKoinonSpanish } from '@fireflyframework/koinon-angular/workbench';
import { RECORDED_SOURCE_SPANISH } from './recorded-source-spanish';

registerKoinonSpanish(RECORDED_SOURCE_SPANISH);

@Component({
  selector: 'ffk-recorded-document-source',
  imports: [KoinonButton, KoinonIcon, KoinonSidePanel, KoinonSkeleton, KoinonTextPipe],
  providers: [KoinonRecordedDocumentSourceState],
  templateUrl: './recorded-document-source.html',
  styleUrl: './recorded-document-source.scss',
  changeDetection: ChangeDetectionStrategy.OnPush,
})
export class KoinonRecordedDocumentSource implements OnChanges, OnDestroy {
  @Input() open = false;
  @Input() source: SourceReference | null = null;
  @Output() closed = new EventEmitter<void>();
  readonly state = inject(KoinonRecordedDocumentSourceState);
  private readonly tasks = inject(PendingTasks);
  ngOnChanges() {
    if (this.open && this.source) this.tasks.run(() => this.state.open(this.source!));
    else this.state.clear();
  }
  retry() {
    const source = this.state.source();
    if (source) this.tasks.run(() => this.state.open(source));
  }
  close() {
    this.state.clear();
    this.closed.emit();
  }
  ngOnDestroy() {
    this.state.clear();
  }
}
