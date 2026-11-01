// Copyright 2026 Firefly Software Foundation
// SPDX-License-Identifier: Apache-2.0
import {
  ChangeDetectionStrategy,
  Component,
  ElementRef,
  EventEmitter,
  HostListener,
  Input,
  OnChanges,
  OnDestroy,
  OnInit,
  Output,
  PendingTasks,
  SimpleChanges,
  ViewChild,
  Injector,
  afterNextRender,
  effect,
  inject,
  signal,
  untracked,
} from '@angular/core';
import { NgTemplateOutlet } from '@angular/common';
import { FormsModule } from '@angular/forms';
import {
  KoinonButton,
  KoinonConversationGroups,
  KoinonI18n,
  KoinonIcon,
  KoinonSearchField,
  KoinonSidePanel,
  KoinonSkeleton,
  KoinonTextPipe,
} from '@fireflyframework/koinon-angular';
import type { ChatFolder, ChatThread, TitleSuggestion } from '@fireflyframework/koinon-sdk';
export interface NewConversationContext {
  folder: ChatFolder | null;
}
type EditAction =
  | 'create-folder'
  | 'rename-folder'
  | 'delete-folder'
  | 'rename-thread'
  | 'move-thread'
  | 'archive-thread'
  | 'delete-thread';
interface SidebarEdit {
  kind: EditAction;
  folder: ChatFolder | null;
  thread: ChatThread | null;
  revision: number;
}
interface SidebarMenu {
  kind: 'global' | 'folder' | 'thread';
  id: string;
}
@Component({
  selector: 'ffk-conversation-sidebar',
  imports: [
    NgTemplateOutlet,
    FormsModule,
    KoinonButton,
    KoinonIcon,
    KoinonSearchField,
    KoinonSidePanel,
    KoinonSkeleton,
    KoinonTextPipe,
  ],
  providers: [KoinonConversationGroups],
  templateUrl: './conversation-sidebar.html',
  styleUrl: './conversation-sidebar.scss',
  changeDetection: ChangeDetectionStrategy.OnPush,
})
export class KoinonConversationSidebar implements OnInit, OnChanges, OnDestroy {
  @Input() activeThread: ChatThread | null = null;
  @Input() selectedThreadId = '';
  @Input() titleAgentId: string | null = null;
  @Input() allowAiTitle = false;
  @Input() closable = false;
  @Input() busy = false;
  @Output() threadSelected = new EventEmitter<ChatThread>();
  @Output() newConversationRequested = new EventEmitter<NewConversationContext>();
  @Output() threadChanged = new EventEmitter<ChatThread>();
  @Output() threadDeleted = new EventEmitter<string>();
  @Output() closeRequested = new EventEmitter<void>();
  readonly s = inject(KoinonConversationGroups);
  readonly i18n = inject(KoinonI18n);
  private readonly tasks = inject(PendingTasks);
  private readonly host = inject<ElementRef<HTMLElement>>(ElementRef);
  private readonly injector = inject(Injector);
  @ViewChild(KoinonSidePanel) private panel?: KoinonSidePanel;
  readonly menu = signal<SidebarMenu | null>(null);
  readonly edit = signal<SidebarEdit | null>(null);
  readonly suggestion = signal<TitleSuggestion | null>(null);
  readonly memoryStatus = signal<'loading' | 'allowed' | 'disabled' | 'unavailable'>('loading');
  readonly formError = signal('');
  readonly treeFocus = signal('');
  readonly destination = signal<ChatFolder | null | undefined>(undefined);
  query = '';
  folderQuery = '';
  formName = '';
  formMemoryEnabled = false;
  private started = false;
  private key = this.s.scopeKey();
  private searchTimer?: ReturnType<typeof setTimeout>;
  private menuTrigger: HTMLElement | null = null;
  constructor() {
    effect(() => {
      const key = this.s.scopeKey();
      if (key !== this.key) {
        this.key = key;
        untracked(() => {
          this.closeMenu(false);
          this.closeEdit();
          this.query = '';
          if (this.started) this.tasks.run(() => this.s.initialize());
        });
      }
    });
  }
  ngOnInit() {
    this.started = true;
    this.tasks.run(() => this.s.initialize());
  }
  ngOnChanges(changes: SimpleChanges) {
    if (changes['activeThread'] && this.activeThread && this.started) this.refresh();
  }
  ngOnDestroy() {
    if (this.searchTimer) clearTimeout(this.searchTimer);
    this.s.cancelSuggestion();
    this.closeEdit();
  }
  refresh() {
    this.tasks.run(() => this.s.refresh());
  }
  search(value: string) {
    this.query = value;
    if (this.searchTimer) clearTimeout(this.searchTimer);
    this.searchTimer = setTimeout(() => this.tasks.run(() => this.s.search(value)), 250);
  }
  submitSearch() {
    if (this.searchTimer) clearTimeout(this.searchTimer);
    this.tasks.run(() => this.s.search(this.query));
  }
  startNew() {
    if (!this.busy && this.s.canUse())
      this.newConversationRequested.emit({ folder: this.s.selectedFolder() });
  }
  selectThread(thread: ChatThread) {
    if (this.busy) return;
    this.closeMenu(false);
    this.threadSelected.emit(thread);
  }
  activeId() {
    return this.selectedThreadId || this.activeThread?.id || '';
  }
  toggle(folder: ChatFolder) {
    this.tasks.run(() => this.s.toggle(folder));
  }
  threadBusy() {
    return this.busy;
  }
  openMenu(event: MouseEvent, kind: SidebarMenu['kind'], id = '') {
    event.stopPropagation();
    const same = this.menu()?.kind === kind && this.menu()?.id === id;
    this.closeMenu(false);
    if (same) return;
    this.menuTrigger = event.currentTarget as HTMLElement;
    this.menu.set({ kind, id });
    afterNextRender(
      () =>
        this.host.nativeElement.querySelector<HTMLElement>('[role=menu] [role=menuitem]')?.focus(),
      { injector: this.injector },
    );
  }
  closeMenu(restore = true) {
    this.menu.set(null);
    if (restore && this.menuTrigger?.isConnected) this.menuTrigger.focus({ preventScroll: true });
    this.menuTrigger = null;
  }
  menuKeys(event: KeyboardEvent) {
    const items = Array.from(
      (event.currentTarget as HTMLElement).querySelectorAll<HTMLButtonElement>(
        'button[role=menuitem]:not(:disabled)',
      ),
    );
    const index = items.indexOf(event.target as HTMLButtonElement);
    if (event.key === 'Escape') {
      event.preventDefault();
      event.stopPropagation();
      this.closeMenu();
    } else if (event.key === 'Tab') this.closeMenu(false);
    else if (['ArrowDown', 'ArrowUp', 'Home', 'End'].includes(event.key)) {
      event.preventDefault();
      const next =
        event.key === 'Home'
          ? 0
          : event.key === 'End'
            ? items.length - 1
            : (index + (event.key === 'ArrowDown' ? 1 : -1) + items.length) % items.length;
      items[next]?.focus();
    }
  }
  @HostListener('document:pointerdown', ['$event']) outside(event: PointerEvent) {
    if (
      this.menu() &&
      !event.composedPath().includes(this.menuTrigger!) &&
      !event
        .composedPath()
        .some((node) => node instanceof HTMLElement && node.getAttribute('role') === 'menu')
    )
      this.closeMenu(false);
  }
  treeKeys(event: KeyboardEvent, folder: ChatFolder | null) {
    const target = event.currentTarget as HTMLElement;
    const all = Array.from(
      this.host.nativeElement.querySelectorAll<HTMLElement>('[data-tree-key]'),
    ).filter((row) => row.getClientRects().length);
    const index = all.indexOf(target);
    if (['ArrowDown', 'ArrowUp', 'Home', 'End'].includes(event.key)) {
      event.preventDefault();
      const next =
        event.key === 'Home'
          ? 0
          : event.key === 'End'
            ? all.length - 1
            : Math.max(0, Math.min(all.length - 1, index + (event.key === 'ArrowDown' ? 1 : -1)));
      all[next]?.focus();
    } else if (event.key === 'ArrowRight' && folder) {
      event.preventDefault();
      if (!this.s.branches().get(folder.id)?.expanded) this.toggle(folder);
      else all.find((row) => row.dataset['parentId'] === folder.id)?.focus();
    } else if (event.key === 'ArrowLeft') {
      event.preventDefault();
      if (folder && this.s.branches().get(folder.id)?.expanded) this.toggle(folder);
      else
        all
          .find((row) => row.dataset['treeKey'] === 'folder:' + target.dataset['parentId'])
          ?.focus();
    }
  }
  @HostListener('keydown.escape', ['$event']) escape(event: Event) {
    if (this.menu()) {
      event.preventDefault();
      event.stopPropagation();
      this.closeMenu();
    } else if (this.closable && !this.edit()) {
      event.preventDefault();
      this.closeRequested.emit();
    }
  }
  begin(kind: EditAction, folder: ChatFolder | null = null, thread: ChatThread | null = null) {
    this.closeMenu();
    this.s.error.set(null);
    this.formError.set('');
    this.suggestion.set(null);
    this.formName =
      kind === 'rename-folder'
        ? (folder?.name ?? '')
        : kind === 'rename-thread'
          ? (thread?.title ?? '')
          : '';
    this.destination.set(undefined);
    this.formMemoryEnabled = kind === 'rename-folder' && folder?.memory_enabled === true;
    this.folderQuery = '';
    this.edit.set({ kind, folder, thread, revision: thread?.revision ?? folder?.revision ?? 0 });
    if (kind === 'create-folder' || kind === 'rename-folder') {
      const form = this.edit(), scope = this.s.scopeKey();
      this.memoryStatus.set('loading');
      this.tasks.run(async () => {
        const status = await this.s.projectMemoryStatus();
        if (form === this.edit() && scope === this.s.scopeKey()) this.memoryStatus.set(status);
      });
    }
    if (kind === 'move-thread') this.tasks.run(() => this.s.loadPicker());
  }
  closeEdit() {
    this.edit.set(null);
    this.suggestion.set(null);
    this.formError.set('');
    this.s.cancelSuggestion();
  }
  heading() {
    const kind = this.edit()?.kind;
    return kind === 'create-folder'
      ? 'New chat project'
      : kind === 'rename-folder'
        ? 'Chat project settings'
        : kind === 'delete-folder'
          ? 'Remove chat project'
          : kind === 'rename-thread'
            ? 'Rename conversation'
            : kind === 'move-thread'
              ? 'Move conversation'
              : kind === 'delete-thread'
                ? 'Delete conversation'
                : 'Archive conversation';
  }
  saveLabel() {
    const kind = this.edit()?.kind;
    return kind === 'delete-folder'
      ? 'Remove chat project'
      : kind === 'delete-thread'
        ? 'Delete conversation'
        : kind === 'archive-thread'
        ? 'Archive conversation'
        : kind === 'move-thread'
          ? 'Move conversation'
          : 'Save changes';
  }
  canSave() {
    const edit = this.edit();
    return (
      !!edit &&
      !this.s.mutating() &&
      !this.s.suggesting() &&
      (edit.kind === 'delete-folder' ||
      edit.kind === 'delete-thread' ||
      edit.kind === 'archive-thread' ||
      edit.kind === 'move-thread'
        ? edit.kind !== 'move-thread' || this.destination() !== undefined
        : !!this.formName.trim())
    );
  }
  save() {
    const edit = this.edit();
    if (!edit || !this.canSave()) return;
    let done = false;
    let thread: ChatThread | null = null;
    this.tasks.run(async () => {
      if (edit.kind === 'create-folder')
        done = !!(await this.s.createFolder(this.formName, edit.folder, this.formMemoryEnabled));
      if (edit.kind === 'rename-folder' && edit.folder)
        done = !!(await this.s.renameFolder(edit.folder, this.formName, this.formMemoryEnabled));
      if (edit.kind === 'delete-folder' && edit.folder)
        done = await this.s.deleteFolder(edit.folder);
      if (edit.thread) {
        if (edit.kind === 'rename-thread')
          thread = await this.s.renameThread(edit.thread, this.formName, edit.revision);
        if (edit.kind === 'move-thread')
          thread = await this.s.moveThread(edit.thread, this.destination() ?? null);
        if (edit.kind === 'archive-thread') thread = await this.s.archiveThread(edit.thread, true);
        if (edit.kind === 'delete-thread') {
          done = await this.s.deleteThread(edit.thread, edit.revision);
          if (done) this.threadDeleted.emit(edit.thread.id);
        } else done = !!thread;
      }
      if (thread) this.threadChanged.emit(thread);
      if (done) this.panel?.dismiss();
    });
  }
  restore(thread: ChatThread) {
    this.closeMenu();
    this.tasks.run(async () => {
      const updated = await this.s.archiveThread(thread, false);
      if (updated) this.threadChanged.emit(updated);
    });
  }
  suggest() {
    const edit = this.edit();
    if (!edit?.thread || !this.allowAiTitle || !this.titleAgentId) return;
    this.tasks.run(async () => {
      const value = await this.s.suggestTitle(edit.thread!, this.titleAgentId!);
      if (this.edit() === edit) this.suggestion.set(value);
    });
  }
  useSuggestion() {
    const value = this.suggestion(),
      edit = this.edit();
    if (value && edit) {
      this.formName = value.title;
      this.edit.set({ ...edit, revision: value.based_on_revision });
      this.suggestion.set(null);
    }
  }
  lookupFolders() {
    this.tasks.run(() => this.s.loadPicker(this.folderQuery));
  }
  status(value: 'active' | 'archived') {
    this.closeMenu();
    this.tasks.run(() => this.s.setStatus(value));
  }
  errorHelp() {
    const error = this.s.error();
    if (error && 'status' in error) {
      if (error.status === 409) return 'This item changed. Reload before saving.';
      if (error.status === 403) return 'You do not have permission to change this conversation.';
      if (error.status === 401) return 'Your session has expired. Sign in again.';
    }
    return error?.message ?? '';
  }
  async reloadEdit() {
    const edit = this.edit();
    if (!edit) return;
    await this.tasks.run(async () => {
      if (edit.thread) {
        const row = await this.s.latestThread(edit.thread);
        if (row) {
          this.edit.set({ ...edit, thread: row, revision: row.revision });
          this.formName = row.title;
        }
      } else if (edit.folder) {
        const row = await this.s.latestFolder(edit.folder);
        if (row) {
          this.edit.set({ ...edit, folder: row, revision: row.revision });
          this.formName = row.name;
          this.formMemoryEnabled = row.memory_enabled === true;
        }
      }
    });
  }
  panelClose() {
    this.panel?.dismiss();
  }
  more(group: string, folder: ChatFolder | null = null) {
    this.tasks.run(() =>
      group === 'recent'
        ? this.s.moreRecent()
        : group === 'folders'
          ? this.s.moreRoots()
          : group === 'results'
            ? this.s.moreResults()
            : group === 'picker'
              ? this.s.morePicker()
              : group === 'children' && folder
                ? this.s.moreChildren(folder)
                : folder
                  ? this.s.moreFolderThreads(folder)
                  : Promise.resolve(),
    );
  }
  retryGroup(group: string) {
    this.tasks.run(() =>
      group === 'recent'
        ? this.s.loadRecent()
        : group === 'folders'
          ? this.s.loadRoots()
          : this.s.search(this.query),
    );
  }
  reloadFolder(folder: ChatFolder) {
    this.tasks.run(() =>
      Promise.all([this.s.loadChildren(folder), this.s.loadFolderThreads(folder)]),
    );
  }
}
