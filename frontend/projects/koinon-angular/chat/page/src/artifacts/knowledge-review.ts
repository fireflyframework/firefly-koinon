// Copyright 2026 Firefly Software Foundation
// SPDX-License-Identifier: Apache-2.0
import { ChangeDetectionStrategy, Component, EventEmitter, Input, OnChanges, OnDestroy, Output, PendingTasks, ElementRef, Injector, ViewChild, afterNextRender, computed, effect, inject } from '@angular/core';
import { FormsModule } from '@angular/forms';
import { KoinonButton, KoinonDatePipe, KoinonFacade, KoinonFolderTree, KoinonSidePanel, KoinonSkeleton, KoinonTextPipe } from '@fireflyframework/koinon-angular';
import { registerKoinonSpanish } from '@fireflyframework/koinon-angular/workbench';
import type { ChatMessage, KnowledgeIntent, ResourceKind } from '@fireflyframework/koinon-sdk';
import { KoinonKnowledgeIntents } from '../services/knowledge-intents';
import type { ConversationSelection } from '../services/artifact-selections';
import { KNOWLEDGE_SPANISH } from './knowledge-spanish';

registerKoinonSpanish(KNOWLEDGE_SPANISH);

@Component({
  selector: 'ffk-knowledge-review',
  imports: [FormsModule, KoinonButton, KoinonDatePipe, KoinonFolderTree, KoinonSidePanel, KoinonSkeleton, KoinonTextPipe],
  providers: [KoinonKnowledgeIntents],
  templateUrl: './knowledge-review.html',
  styleUrl: './knowledge-review.scss',
  changeDetection: ChangeDetectionStrategy.OnPush,
})
export class KoinonKnowledgeReview implements OnChanges, OnDestroy {
  @Input() open = false;
  @Input() workspaceId = '';
  @Input() selection: ConversationSelection | null = null;
  @Input() message: ChatMessage | null = null;
  @Output() closed = new EventEmitter<void>();
  @Output() resourceRequested = new EventEmitter<string>();
  readonly s = inject(KoinonKnowledgeIntents);
  readonly f = inject(KoinonFacade);
  private readonly tasks = inject(PendingTasks);
  private readonly injector = inject(Injector);
  @ViewChild('reviewRegion') private reviewRegion?: ElementRef<HTMLElement>;
  @ViewChild('titleField') private titleField?: ElementRef<HTMLInputElement>;
  @ViewChild('outcome') private outcome?: ElementRef<HTMLElement>;
  private focus(target: 'review' | 'edit' | 'outcome') {
    afterNextRender(() => {
      if (this.open) (target === 'review' ? this.reviewRegion : target === 'edit' ? this.titleField : this.outcome)?.nativeElement.focus();
    }, { injector: this.injector });
  }
  private scope = '';
  private context = this.f.context();
  readonly folderKinds: ResourceKind[] = ['collection', 'corpus'];
  readonly entries = computed(() => [...new Map([
    ...(this.f.context()?.workspaces ?? []), ...this.f.entries(),
  ].filter((entry) => entry.tenant_id === this.f.tenantId()).map((entry) => [entry.id, entry])).values()]);
  readonly loadChildren = (id: string, page = 1) => this.f.loadChildren(id, page);
  constructor() {
    effect(() => {
      if (this.open && this.scope && (this.scope !== this.s.scopeKey() || this.context !== this.f.context())) {
        this.s.reset();
        this.closed.emit();
      }
    });
  }
  ngOnChanges() {
    if (!this.open) { this.s.suspend(); return; }
    if (!this.selection || this.message?.role !== 'assistant' || this.message.status !== 'completed' ||
        this.selection.message_ids.length !== 1 || this.selection.message_ids[0] !== this.message.id) {
      this.s.reset(); this.closed.emit(); return;
    }
    this.scope = this.s.scopeKey();
    this.context = this.f.context();
    this.s.configure(this.selection, this.message.text, this.workspaceId);
  }
  destinationName() {
    return this.entries().find((entry) => entry.id === this.s.destination())?.name ?? '';
  }
  choose(id: string) {
    if (this.s.pending()) return;
    const entry = this.entries().find((row) => row.id === id);
    if (entry && this.folderKinds.includes(entry.kind) && entry.status !== 'archived') {
      this.s.destination.set(id);
      this.s.consent.set(false);
    }
  }
  preview() { this.tasks.run(async () => { await this.s.preview(); if (this.s.stage() === 'review') this.focus('review'); }); }
  confirm() { this.tasks.run(async () => { await this.s.confirm(); this.focus(this.s.stage() === 'edit' ? 'edit' : 'outcome'); }); }
  refresh() { this.tasks.run(async () => { await this.s.refresh(); this.focus(this.s.stage() === 'review' ? 'review' : this.s.stage() === 'edit' ? 'edit' : 'outcome'); }); }
  cancel() { this.tasks.run(async () => { await this.s.cancel(); this.focus(this.s.stage() === 'edit' ? 'edit' : 'outcome'); }); }
  edit() { this.s.edit(); this.focus('edit'); }
  evidenceTitle(item: KnowledgeIntent['evidence'][number]) {
    return 'source' in item
      ? item.source.title : 'Selected conversation text';
  }
  evidenceQuote(item: KnowledgeIntent['evidence'][number]) {
    return 'source' in item ? item.source.quote ?? '' : item.text;
  }
  remembered(item: KnowledgeIntent['evidence'][number]) {
    return ('source' in item) && item.basis === 'remembered_context';
  }
  resource() {
    const receipt = this.s.receipt();
    if (receipt) { this.resourceRequested.emit(receipt.item_id); this.close(); }
  }
  close() { this.s.suspend(); this.closed.emit(); }
  ngOnDestroy() { this.s.reset(); }
}
