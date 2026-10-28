// Copyright 2026 Firefly Software Foundation
// SPDX-License-Identifier: Apache-2.0
import { DOCUMENT } from '@angular/common';
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
  effect,
  inject,
  signal,
} from '@angular/core';
import { FormsModule } from '@angular/forms';
import {
  KoinonButton,
  KoinonDatePipe,
  KoinonFacade,
  KoinonSidePanel,
  KoinonSkeleton,
  KoinonTextPipe,
} from '@fireflyframework/koinon-angular';
import type { Share } from '@fireflyframework/koinon-sdk';
import { KoinonKnowledgeArtifacts } from '../services/knowledge-artifacts';
import type { ConversationSelection } from '../services/artifact-selections';
@Component({
  selector: 'ffk-share-review',
  imports: [
    FormsModule,
    KoinonButton,
    KoinonDatePipe,
    KoinonSidePanel,
    KoinonSkeleton,
    KoinonTextPipe,
  ],
  providers: [KoinonKnowledgeArtifacts],
  templateUrl: './share-review.html',
  styleUrl: './artifact-panels.scss',
  changeDetection: ChangeDetectionStrategy.OnPush,
})
export class KoinonShareReview implements OnChanges, OnDestroy {
  @Input() open = false;
  @Input() selection: ConversationSelection | null = null;
  @Input() managementBaseUrl = '';
  @Output() closed = new EventEmitter<void>();
  @Output() shareCreated = new EventEmitter<Share>();
  readonly state = inject(KoinonKnowledgeArtifacts);
  private readonly tasks = inject(PendingTasks);
  private readonly document = inject(DOCUMENT);
  private readonly facade = inject(KoinonFacade);
  private scope = '';
  hours = 24;
  readonly copied = signal(false);
  readonly localError = signal('');
  constructor() {
    effect(() => {
      if (this.scope && this.scope !== this.state.scopeKey()) this.closed.emit();
    });
  }
  ngOnChanges(changes: SimpleChanges) {
    if (changes['open'] || changes['selection']) {
      this.state.reset();
      this.scope = this.state.scopeKey();
    }
    this.copied.set(false);
    this.localError.set('');
  }
  ngOnDestroy() {
    this.state.reset();
  }
  review() {
    const selection = this.selection;
    if (selection) this.tasks.run(() => this.state.reviewShare(selection).then(() => undefined));
  }
  create() {
    if (!Number.isInteger(this.hours) || this.hours < 1 || this.hours > 168) return;
    this.tasks.run(async () => {
      const value = await this.state.createShare(this.hours);
      if (value) this.shareCreated.emit(value);
    });
  }
  revoke() {
    this.tasks.run(() => this.state.revokeShare().then(() => undefined));
    this.copied.set(false);
  }
  link() {
    const share = this.state.shareRecord();
    if (!share || share.status !== 'active' || !this.managementBaseUrl) return '';
    try {
      const url = new URL(this.managementBaseUrl);
      if (
        !['http:', 'https:'].includes(url.protocol) ||
        url.username ||
        url.password ||
        url.search ||
        url.hash
      )
        return '';
      url.hash = new URLSearchParams({
        share: share.id,
        tenant: this.facade.tenantId(),
      }).toString();
      return url.href;
    } catch {
      return '';
    }
  }
  copy() {
    const link = this.link();
    if (!link) return;
    this.localError.set('');
    this.tasks.run(async () => {
      try {
        const clipboard = this.document.defaultView?.navigator.clipboard;
        if (!clipboard) throw Error('Clipboard unavailable');
        await clipboard.writeText(link);
        this.copied.set(true);
      } catch {
        this.localError.set('The link could not be copied. Select it and copy it manually.');
      }
    });
  }
  close() {
    this.state.reset();
    this.closed.emit();
  }
}
