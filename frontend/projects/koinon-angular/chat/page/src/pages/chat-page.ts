// Copyright 2026 Firefly Software Foundation
// SPDX-License-Identifier: Apache-2.0
import { registerKoinonSpanish } from '@fireflyframework/koinon-angular/workbench';
import { CHAT_SPANISH } from './chat-spanish';
import { KoinonTextPipe, KoinonDatePipe, KoinonI18n } from '@fireflyframework/koinon-angular';
import { A11yModule } from '@angular/cdk/a11y';
import {
  Component,
  ChangeDetectionStrategy,
  EventEmitter,
  Output,
  Input,
  PendingTasks,
  OnInit,
  AfterViewInit,
  OnDestroy,
  ViewChild,
  ElementRef,
  Injector,
  afterNextRender,
  effect,
  computed,
  inject,
  signal,
} from '@angular/core';
import type { Citation, ChatThread, ChatFolder } from '@fireflyframework/koinon-sdk';
import {
  KoinonAssistant,
  KoinonFacade,
  KoinonClientContext,
  KoinonButton,
  KoinonBadge,
  KoinonIcon,
  KoinonSkeleton,
} from '@fireflyframework/koinon-angular';
import { KoinonEvidenceGroups } from '@fireflyframework/koinon-angular';
import { KoinonOpenUiArtifact } from '@fireflyframework/koinon-angular/chat/evidence';
import { KoinonConversationSidebar } from '../conversation-sidebar/conversation-sidebar';
import { KoinonChatAttachments } from '../services/chat-attachments';
import { KoinonMessageText } from '../composer/message-text';
import { KoinonChatComposer } from '../composer/chat-composer';
import { KoinonExportDialog } from '../artifacts/export-dialog';
import { KoinonShareReview } from '../artifacts/share-review';
import { KoinonAnswerAudit } from '../artifacts/answer-audit';
import type { ConversationSelection, ExportSelection } from '../services/artifact-selections';

registerKoinonSpanish(CHAT_SPANISH);

@Component({
  selector: 'ffk-chat-page',
  providers: [KoinonChatAttachments, KoinonEvidenceGroups],
  imports: [
    KoinonTextPipe,
    A11yModule,
    KoinonDatePipe,
    KoinonButton,
    KoinonBadge,
    KoinonIcon,
    KoinonSkeleton,
    KoinonOpenUiArtifact,
    KoinonChatComposer,
    KoinonMessageText,
    KoinonConversationSidebar,
    KoinonExportDialog,
    KoinonShareReview,
    KoinonAnswerAudit,
  ],
  templateUrl: './chat-page.html',
  styleUrl: './chat-page.scss',
  host: { '[class.chat-compact]': 'compact()' },
  changeDetection: ChangeDetectionStrategy.OnPush,
})
export class KoinonChatPage implements OnInit, AfterViewInit, OnDestroy {
  @Input() actions?: {
    agentId?: () => string;
    avatar?: () => string;
    displayName?: () => string;
    brandBase?: () => string;
    assistantName?: () => string;
    brandSymbol?: () => string;
    locale?: () => string;
    managementBaseUrl?: () => string;
    newConversation?: () => boolean;
    setup: () => void;
    citation: (citation: Citation) => void;
    resource: (id: string) => void;
  };
  @Output() setupRequested = new EventEmitter<void>();
  @Output() citationSelected = new EventEmitter<Citation>();
  @Output() resourceSelected = new EventEmitter<string>();
  @ViewChild('messageViewport') private messageViewport?: ElementRef<HTMLElement>;
  @ViewChild('historyToggle') private historyToggle?: ElementRef<HTMLButtonElement>;
  readonly a = inject(KoinonAssistant);
  private readonly clients = inject(KoinonClientContext);
  readonly files = inject(KoinonChatAttachments);
  readonly fileReferences = computed(() => [
    ...new Map(
      this.a
        .messages()
        .flatMap((message) => message.attachments ?? [])
        .map((file) => [file.id, file]),
    ).values(),
  ]);
  readonly primaryEvidence = computed(
    () =>
      new Map(
        this.a.messages().map((message) => {
          const activities = message.tool_activities ?? [];
          const complete =
            ['queued', 'running'].includes(message.status) ||
            (activities.length > 0 &&
              !message.tool_activity_has_more &&
              (message.tool_activity_count ?? activities.length) <= activities.length &&
              activities.every(
                (activity) => activity.status !== 'completed' || !!activity.result_id,
              ));
          return [
            message.id,
            complete
              ? activities
                  .filter(
                    (activity) =>
                      activity.status === 'completed' &&
                      ['query_dataset', 'propose_catalog_update'].includes(activity.tool_name) &&
                      !!activity.result_id,
                  )
                  .map((activity) => activity.result_id!)
              : undefined,
          ] as const;
        }),
      ),
  );
  readonly f = inject(KoinonFacade);
  readonly artifactAction = signal<'audit' | 'export' | 'share' | null>(null);
  readonly artifactSelection = signal<ConversationSelection | null>(null);
  readonly artifactMessage = computed(
    () =>
      this.a
        .messages()
        .find((message) => message.id === this.artifactSelection()?.message_ids[0]) ?? null,
  );
  readonly exportSelection = computed<ExportSelection | null>(() => {
    const selected = this.artifactSelection();
    return selected ? { kind: 'conversation', ...selected } : null;
  });
  private readonly tasks = inject(PendingTasks);
  private readonly host = inject<ElementRef<HTMLElement>>(ElementRef);
  private readonly injector = inject(Injector);
  private observer?: ResizeObserver;
  private followLatest = true;
  private visibleThread = '';
  draft = '';
  readonly historyOpen = signal(false);
  readonly compact = signal(true);
  readonly historyCollapsed = this.a.historyCollapsed;
  readonly emptyReady = computed(
    () =>
      this.a.canUseAgent() &&
      !this.a.pending() &&
      !this.a.messages().length &&
      !this.a.activeThread()?.archived_at &&
      !this.a.error(),
  );
  readonly failedAvatar = signal('');
  constructor() {
    effect(() => {
      this.a.contextVersion();
      this.draft = '';
      this.closeArtifact();
    });
    effect(() => {
      this.a.messages();
      this.a.toolActivity();
      const thread = this.a.threadId();
      if (thread !== this.visibleThread) {
        this.visibleThread = thread;
        this.followLatest = true;
      }
      if (this.followLatest)
        afterNextRender(
          () => {
            const viewport = this.messageViewport?.nativeElement;
            if (viewport && this.followLatest && thread === this.a.threadId())
              viewport.scrollTop = viewport.scrollHeight;
          },
          { injector: this.injector },
        );
    });
  }
  ngOnInit() {
    this.tasks.run(async () => {
      const id = this.actions?.agentId?.();
      await this.a.initialize(id);
      if (this.actions?.newConversation?.()) this.startConversation();
      if (id && this.a.agents().some((agent) => agent.id === id)) {
        this.a.newConversation();
        this.a.agentId.set(id);
      }
    });
  }
  ngAfterViewInit() {
    const resize = (width: number) => {
      this.compact.set(width < 900);
      if (width >= 900) this.historyOpen.set(false);
    };
    resize(this.host.nativeElement.getBoundingClientRect().width);
    if (typeof ResizeObserver !== 'undefined') {
      this.observer = new ResizeObserver((entries) => resize(entries[0].contentRect.width));
      this.observer.observe(this.host.nativeElement);
    }
  }
  ngOnDestroy() {
    this.observer?.disconnect();
    this.closeArtifact();
  }
  setup() {
    this.setupRequested.emit();
    this.actions?.setup();
  }
  onCitation(value: Citation) {
    this.citationSelected.emit(value);
    this.actions?.citation(value);
  }
  resource(id: string) {
    this.resourceSelected.emit(id);
    this.actions?.resource(id);
  }
  canArtifact(action: 'audit' | 'export' | 'share') {
    const permissions = this.f.permissions();
    const required =
      action === 'audit'
        ? []
        : action === 'export'
          ? ['exports:read', 'exports:write']
          : ['shares:read', 'shares:write'];
    return !this.f.authRequired() && required.every((permission) => permissions.has(permission));
  }
  openArtifact(action: 'audit' | 'export' | 'share', messageId: string) {
    const message = this.a.messages().find((item) => item.id === messageId);
    if (
      !this.canArtifact(action) ||
      !this.a.threadId() ||
      (action !== 'audit' && this.a.running()) ||
      message?.role !== 'assistant' ||
      (action !== 'audit' && message.status !== 'completed')
    )
      return;
    this.artifactSelection.set({ thread_id: this.a.threadId(), message_ids: [messageId] });
    this.artifactAction.set(action);
  }
  closeArtifact() {
    this.artifactAction.set(null);
    this.artifactSelection.set(null);
  }
  auditResource(id: string) {
    this.closeArtifact();
    this.resource(id);
  }
  auditCitation(citation: Citation) {
    this.closeArtifact();
    this.onCitation(citation);
  }
  async auditConversation(id: string) {
    if (this.a.running()) return;
    const selection = this.artifactSelection(),
      tenant = this.f.tenantId(),
      revision = this.clients.revision();
    if (!selection || this.artifactAction() !== 'audit') return;
    try {
      const thread = await this.clients.get().chat.get(tenant, id);
      if (
        selection !== this.artifactSelection() ||
        tenant !== this.f.tenantId() ||
        revision !== this.clients.revision() ||
        this.a.running()
      )
        return;
      if (
        (thread.scope.workspace_id ?? '') !== this.f.workspaceId() ||
        (thread.scope.project_id ?? '') !== this.f.projectId()
      ) {
        this.a.error.set(
          'This conversation is no longer available in the current knowledge scope.',
        );
        return;
      }
      this.closeArtifact();
      this.selectThread(thread);
    } catch (error) {
      if (
        selection !== this.artifactSelection() ||
        tenant !== this.f.tenantId() ||
        revision !== this.clients.revision()
      )
        return;
      if (error instanceof Error && 'status' in error && error.status === 401)
        this.f.authRequired.set(true);
      this.a.error.set('The recorded conversation could not be opened.');
    }
  }
  userInitials() {
    return (this.actions?.displayName?.() || 'Your account')
      .split(/\s+/)
      .filter(Boolean)
      .slice(0, 2)
      .map((part) => Array.from(part)[0])
      .join('')
      .toUpperCase();
  }
  userAvatar() {
    return this.actions?.avatar?.() || '';
  }
  private readonly i18n = inject(KoinonI18n);
  assistantCopy(key: string) {
    return this.i18n.text(key).replaceAll('koinon', this.assistantName());
  }
  assistantName() {
    return this.actions?.assistantName?.() || 'koinon';
  }
  brandSymbol() {
    if (this.actions?.brandSymbol) return this.actions.brandSymbol();
    return (this.actions?.brandBase?.() || '/assets/brand') + '/logos/koinon-symbol-color.svg';
  }
  toggleHistory() {
    if (this.compact()) this.historyOpen.set(!this.historyOpen());
    else this.historyCollapsed.set(!this.historyCollapsed());
  }
  historyVisible() {
    return this.compact() ? this.historyOpen() : !this.historyCollapsed();
  }
  startConversation(context?: { folder: ChatFolder | null }) {
    if (this.a.running() || this.a.pending()) return;
    this.draft = '';
    this.a.newConversation(context?.folder ?? null);
    this.closeHistory();
    afterNextRender(
      () =>
        this.host.nativeElement
          .querySelector<HTMLTextAreaElement>('ffk-chat-composer textarea')
          ?.focus(),
      { injector: this.injector },
    );
  }
  closeHistory() {
    const wasOpen = this.historyOpen();
    this.historyOpen.set(false);
    if (wasOpen)
      afterNextRender(() => this.historyToggle?.nativeElement.focus(), { injector: this.injector });
  }
  deletedConversation(threadId: string) {
    if (this.a.threadId() === threadId) this.startConversation();
  }
  trackScroll() {
    const viewport = this.messageViewport?.nativeElement;
    if (viewport)
      this.followLatest = viewport.scrollHeight - viewport.scrollTop - viewport.clientHeight < 80;
  }
  async loadOlder() {
    const viewport = this.messageViewport?.nativeElement;
    const thread = this.a.threadId();
    const height = viewport?.scrollHeight ?? 0,
      top = viewport?.scrollTop ?? 0;
    this.followLatest = false;
    await this.a.loadOlder();
    afterNextRender(
      () => {
        if (viewport && thread === this.a.threadId())
          viewport.scrollTop = top + viewport.scrollHeight - height;
      },
      { injector: this.injector },
    );
  }
  async submit() {
    const text = this.draft.trim();
    if (
      !text ||
      this.a.running() ||
      this.a.pending() ||
      !this.files.ready() ||
      this.files.selecting()
    )
      return;
    this.followLatest = true;
    this.draft = '';
    const ids = this.files.ids();
    const contextVersion = this.a.contextVersion();
    const admitted = await this.a.send(text, ids);
    if (contextVersion !== this.a.contextVersion()) return;
    if (admitted) this.files.sent();
    else if (!this.draft) this.draft = text;
  }
  scopeLabel(id: string | undefined, fallback: string) {
    if (!id) return '';
    return (
      [...(this.f.context()?.workspaces ?? []), ...this.f.entries()].find((x) => x.id === id)
        ?.name || fallback
    );
  }
  canConfigure() {
    return (
      this.f.tenantPermissions().has('agents:write') &&
      (!!this.actions?.setup || this.setupRequested.observed)
    );
  }
  selectThread(thread: ChatThread) {
    this.closeHistory();
    this.followLatest = true;
    void this.a.selectThread(thread.id, thread);
  }
}
