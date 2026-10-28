// Copyright 2026 Firefly Software Foundation
// SPDX-License-Identifier: Apache-2.0
import { DOCUMENT } from '@angular/common';
import {
  ChangeDetectionStrategy,
  Component,
  ElementRef,
  EventEmitter,
  Input,
  OnChanges,
  OnDestroy,
  Output,
  PendingTasks,
  effect,
  inject,
  signal,
} from '@angular/core';
import { FormsModule } from '@angular/forms';
import {
  KoinonButton,
  KoinonDatePipe,
  KoinonValuePipe,
  KoinonSidePanel,
  KoinonSkeleton,
  KoinonTextPipe,
} from '@fireflyframework/koinon-angular';
import type { Export, ExportReviewRequest } from '@fireflyframework/koinon-sdk';
import { KoinonKnowledgeArtifacts } from '../services/knowledge-artifacts';
import type { ExportSelection } from '../services/artifact-selections';
@Component({
  selector: 'ffk-export-dialog',
  imports: [
    FormsModule,
    KoinonButton,
    KoinonDatePipe,
    KoinonValuePipe,
    KoinonSidePanel,
    KoinonSkeleton,
    KoinonTextPipe,
  ],
  providers: [KoinonKnowledgeArtifacts],
  templateUrl: './export-dialog.html',
  styleUrl: './artifact-panels.scss',
  changeDetection: ChangeDetectionStrategy.OnPush,
})
export class KoinonExportDialog implements OnChanges, OnDestroy {
  @Input() open = false;
  @Input() selection: ExportSelection | null = null;
  @Output() closed = new EventEmitter<void>();
  @Output() exportCreated = new EventEmitter<Export>();
  readonly state = inject(KoinonKnowledgeArtifacts);
  private readonly tasks = inject(PendingTasks);
  private readonly document = inject(DOCUMENT);
  private readonly host = inject<ElementRef<HTMLElement>>(ElementRef);
  private scope = '';
  readonly downloaded = signal('');
  readonly localError = signal('');
  conversationFormat: 'markdown' | 'json' = 'markdown';
  resultFormat: 'parquet' | 'csv' | 'jsonl' = 'parquet';
  includeEvidence = true;
  csvMode: 'spreadsheet_safe' | 'exact' = 'spreadsheet_safe';
  constructor() {
    effect(() => {
      if (this.scope && this.scope !== this.state.scopeKey()) this.closed.emit();
    });
  }
  ngOnChanges() {
    this.state.reset();
    this.scope = this.state.scopeKey();
    this.downloaded.set('');
    this.localError.set('');
  }
  ngOnDestroy() {
    this.state.reset();
  }
  changed() {
    this.state.reset();
    this.scope = this.state.scopeKey();
    this.downloaded.set('');
    this.localError.set('');
  }
  review() {
    const selection = this.selection;
    if (!selection || this.state.pending()) return;
    const body: ExportReviewRequest =
      selection.kind === 'conversation'
        ? { ...selection, format: this.conversationFormat, include_evidence: this.includeEvidence }
        : { ...selection, format: this.resultFormat, csv_mode: this.csvMode };
    this.tasks.run(() => this.state.reviewExport(body).then(() => undefined));
  }
  create() {
    this.tasks.run(async () => {
      const value = await this.state.createExport();
      if (value) this.exportCreated.emit(value);
    });
  }
  download() {
    this.localError.set('');
    this.tasks.run(async () => {
      const result = await this.state.downloadExport();
      if (!result || !this.document.defaultView) return;
      let url = '';
      try {
        url = URL.createObjectURL(result.blob);
        const anchor = this.document.createElement('a');
        anchor.href = url;
        anchor.download = result.filename ?? 'knowledge-export';
        this.host.nativeElement.append(anchor);
        anchor.click();
        anchor.remove();
        this.downloaded.set(anchor.download);
      } catch {
        this.localError.set('Your browser could not start the download. Try again.');
      } finally {
        if (url) setTimeout(() => URL.revokeObjectURL(url), 1000);
      }
    });
  }
  cancel() {
    this.tasks.run(() => this.state.cancelExport().then(() => undefined));
  }
  close() {
    this.state.reset();
    this.closed.emit();
  }
}
