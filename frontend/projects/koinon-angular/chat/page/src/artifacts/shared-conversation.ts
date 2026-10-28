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
  SimpleChanges,
  computed,
  effect,
  inject,
  signal,
} from '@angular/core';
import {
  KoinonButton,
  KoinonDatePipe,
  KoinonSkeleton,
  KoinonTextPipe,
} from '@fireflyframework/koinon-angular';
import type {
  ConversationMessage,
  Presentation,
  SourceReference,
} from '@fireflyframework/koinon-sdk';
import { KoinonKnowledgeArtifacts } from '../services/knowledge-artifacts';
import { KoinonSourceDrawer } from './source-drawer';
export interface SharedConversationActions {
  closed: () => void;
  resourceRequested: (source: SourceReference) => void;
}
let nextHeading = 0;
@Component({
  selector: 'ffk-shared-conversation',
  imports: [KoinonButton, KoinonDatePipe, KoinonSkeleton, KoinonTextPipe, KoinonSourceDrawer],
  providers: [KoinonKnowledgeArtifacts],
  templateUrl: './shared-conversation.html',
  styleUrl: './shared-conversation.scss',
  changeDetection: ChangeDetectionStrategy.OnPush,
})
export class KoinonSharedConversation implements OnChanges, OnDestroy {
  @Input() shareId = '';
  @Input() actions?: SharedConversationActions;
  @Output() closed = new EventEmitter<void>();
  @Output() resourceRequested = new EventEmitter<SourceReference>();
  readonly state = inject(KoinonKnowledgeArtifacts);
  readonly headingId = 'ffk-shared-conversation-' + ++nextHeading;
  readonly sourcePanel = signal(false);
  private readonly tasks = inject(PendingTasks);
  private scope = '';
  constructor() {
    effect(() => {
      if (this.scope && this.scope !== this.state.scopeKey()) this.close();
    });
  }
  ngOnChanges(changes: SimpleChanges) {
    if (changes['shareId']) {
      this.state.reset();
      this.scope = this.state.scopeKey();
      this.sourcePanel.set(false);
      if (this.shareId) this.load();
    }
  }
  ngOnDestroy() {
    this.state.reset();
  }
  load() {
    const id = this.shareId;
    if (id) this.tasks.run(() => this.state.readShare(id).then(() => undefined));
  }
  close() {
    this.sourcePanel.set(false);
    this.state.reset();
    this.scope = '';
    this.closed.emit();
    this.actions?.closed();
  }
  resource(source: SourceReference) {
    this.resourceRequested.emit(source);
    this.actions?.resourceRequested(source);
  }
  readonly manifest = computed(() => {
    const value = this.state.sharedConversation();
    return value
      ? {
          revision: value.share.revision,
          sources: value.sources,
          complete: value.source_manifest_complete,
          omissions: [],
        }
      : null;
  });
  presentation(message: ConversationMessage): Presentation | undefined {
    const value = message.presentation;
    return value?.locale && value.time_zone && value.response_language
      ? {
          locale: value.locale,
          time_zone: value.time_zone,
          response_language: value.response_language,
        }
      : undefined;
  }
  errorTitle() {
    const code = this.state.failureCode();
    return code === 'SHARE_EXPIRED'
      ? 'This share has expired.'
      : code === 'SHARE_REVOKED'
        ? 'This share was revoked.'
        : this.state.failureStatus() === 403
          ? 'Your account cannot open this share.'
          : 'This share could not be opened.';
  }
}
