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
  effect,
  inject,
  signal,
} from '@angular/core';
import {
  KoinonButton,
  KoinonSidePanel,
  KoinonSkeleton,
  KoinonTextPipe,
} from '@fireflyframework/koinon-angular';
import type { EvidenceManifest, SourceReference } from '@fireflyframework/koinon-sdk';
import { KoinonKnowledgeArtifacts } from '../services/knowledge-artifacts';
import type { ConversationSelection } from '../services/artifact-selections';
import { KoinonRecordedDocumentSource } from './recorded-document-source';
import { hasRecordedDocumentIdentity } from './recorded-document-source-state';
@Component({
  selector: 'ffk-source-drawer',
  imports: [
    KoinonButton,
    KoinonSidePanel,
    KoinonSkeleton,
    KoinonTextPipe,
    KoinonRecordedDocumentSource,
  ],
  providers: [KoinonKnowledgeArtifacts],
  templateUrl: './source-drawer.html',
  styleUrl: './artifact-panels.scss',
  changeDetection: ChangeDetectionStrategy.OnPush,
})
export class KoinonSourceDrawer implements OnChanges, OnDestroy {
  @Input() open = false;
  @Input() selection: ConversationSelection | null = null;
  @Input() manifest: EvidenceManifest | null = null;
  @Output() closed = new EventEmitter<void>();
  @Output() resourceRequested = new EventEmitter<SourceReference>();
  readonly state = inject(KoinonKnowledgeArtifacts);
  readonly recordedSource = signal<SourceReference | null>(null);
  private readonly tasks = inject(PendingTasks);
  private scope = '';
  constructor() {
    effect(() => {
      if (this.scope && this.scope !== this.state.scopeKey()) this.closed.emit();
    });
  }

  ngOnChanges() {
    this.recordedSource.set(null);
    this.state.reset();
    this.scope = this.state.scopeKey();
    if (this.open && !this.manifest && this.selection) this.load();
  }
  ngOnDestroy() {
    this.state.reset();
  }
  sources() {
    return this.scope === this.state.scopeKey() ? (this.manifest ?? this.state.manifest()) : null;
  }
  load() {
    const selection = this.selection;
    if (selection) this.tasks.run(() => this.state.sources(selection).then(() => undefined));
  }
  close() {
    this.recordedSource.set(null);
    this.state.reset();
    this.closed.emit();
  }
  resource(source: SourceReference) {
    if (this.state.pending()) return;
    if (hasRecordedDocumentIdentity(source)) this.recordedSource.set({ ...source });
    else this.resourceRequested.emit(source);
  }
  availability(source: SourceReference) {
    return source.availability === 'available'
      ? 'Available'
      : source.availability === 'changed'
        ? 'Source has changed'
        : 'Revision not verified';
  }
}
