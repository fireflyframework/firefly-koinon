// Copyright 2026 Firefly Software Foundation
// SPDX-License-Identifier: Apache-2.0
import { Injectable, OnDestroy, computed, inject, signal } from '@angular/core';
import type {
  ChatFolder,
  ChatThread,
  FolderFilter,
  KnowledgeScope,
  Page,
  TitleSuggestion,
} from '@fireflyframework/koinon-sdk';
import { KoinonFacade } from '../koinon-facade';
import { KoinonClientContext } from './client-context';
import {
  emptyConversationPage,
  observedPage,
  scopeWithin,
  type ConversationBranch,
  type ConversationPage,
} from './conversation-group-models';
type ListScope = Pick<KnowledgeScope, 'workspace_id' | 'project_id'>;
@Injectable()
export class KoinonConversationGroups implements OnDestroy {
  private readonly facade = inject(KoinonFacade);
  private readonly clients = inject(KoinonClientContext);
  readonly roots = signal<ConversationPage<ChatFolder>>(emptyConversationPage());
  readonly recent = signal<ConversationPage<ChatThread>>(emptyConversationPage());
  readonly results = signal<ConversationPage<ChatThread>>(emptyConversationPage());
  readonly picker = signal<ConversationPage<ChatFolder>>(emptyConversationPage());
  readonly branches = signal(new Map<string, ConversationBranch>());
  readonly selectedFolder = signal<ChatFolder | null>(null);
  readonly query = signal('');
  readonly status = signal<'active' | 'archived'>('active');
  readonly mutating = signal(false);
  readonly error = signal<Error | null>(null);
  readonly suggesting = signal(false);
  readonly searchView = computed(() => Boolean(this.query() || this.status() === 'archived'));
  readonly canUse = computed(
    () => this.facade.permissions().has('chat:use') && !this.facade.authRequired(),
  );
  readonly scopeKey = computed(() =>
    [
      this.facade.tenantId(),
      this.facade.workspaceId(),
      this.facade.projectId(),
      this.clients.revision(),
      this.canUse(),
    ].join(':'),
  );
  private bound = '';
  private epoch = 0;
  private sequence = new Map<string, number>();
  private reads = new Map<string, AbortController>();
  private context() {
    const key = this.scopeKey();
    if (key !== this.bound) {
      this.reset();
      this.bound = key;
    }
    return this.facade.tenantId() && this.canUse()
      ? {
          key,
          epoch: this.epoch,
          tenant: this.facade.tenantId(),
          scope: {
            ...(this.facade.workspaceId() ? { workspace_id: this.facade.workspaceId() } : {}),
            ...(this.facade.projectId() ? { project_id: this.facade.projectId() } : {}),
          } as ListScope,
        }
      : null;
  }
  private reset() {
    ++this.epoch;
    for (const read of this.reads.values()) read.abort();
    this.reads.clear();
    this.sequence.clear();
    this.roots.set(emptyConversationPage());
    this.recent.set(emptyConversationPage());
    this.results.set(emptyConversationPage());
    this.picker.set(emptyConversationPage());
    this.branches.set(new Map());
    this.selectedFolder.set(null);
    this.query.set('');
    this.status.set('active');
    this.error.set(null);
    this.mutating.set(false);
    this.suggesting.set(false);
  }
  private failure(error: unknown) {
    const value = error instanceof Error ? error : new Error('Conversations could not be loaded.');
    if ('status' in value && value.status === 401) {
      this.facade.authRequired.set(true);
      this.reset();
    }
    return value;
  }
  private branch(folder: ChatFolder) {
    const found = this.branches().get(folder.id);
    if (found) return found;
    const state: ConversationBranch = {
      folder,
      expanded: false,
      children: emptyConversationPage(),
      threads: emptyConversationPage(),
    };
    this.branches.update((rows) => new Map(rows).set(folder.id, state));
    return state;
  }
  private changeBranch(id: string, update: (row: ConversationBranch) => ConversationBranch) {
    this.branches.update((rows) => {
      const row = rows.get(id);
      return row ? new Map(rows).set(id, update(row)) : rows;
    });
  }
  private recordFolders(rows: readonly ChatFolder[]) {
    for (const folder of rows) {
      this.branch(folder);
      this.changeBranch(folder.id, (row) => ({ ...row, folder }));
    }
  }
  private async readPage<T extends { id: string }>(
    slot: string,
    state: () => ConversationPage<T>,
    update: (fn: (value: ConversationPage<T>) => ConversationPage<T>) => void,
    read: (tenant: string, scope: ListScope, signal: AbortSignal) => Promise<Page<T>>,
    append = false,
    onPage?: (items: readonly T[]) => void,
  ) {
    const context = this.context();
    if (!context) return;
    this.reads.get(slot)?.abort();
    const controller = new AbortController();
    this.reads.set(slot, controller);
    const seq = (this.sequence.get(slot) ?? 0) + 1;
    this.sequence.set(slot, seq);
    update((value) => ({ ...value, pending: true, error: '' }));
    const active = () =>
      context.key === this.scopeKey() &&
      context.epoch === this.epoch &&
      seq === this.sequence.get(slot) &&
      !controller.signal.aborted;
    try {
      const result = await read(context.tenant, context.scope, controller.signal);
      if (!active()) return;
      const observed = observedPage(state(), result, append);
      onPage?.(result.items);
      update(() => observed);
    } catch (error) {
      if (active()) {
        const value = this.failure(error);
        if (active())
          update((valueState) => ({ ...valueState, pending: false, error: value.message }));
      }
    } finally {
      if (active()) {
        update((value) => ({ ...value, pending: false }));
        this.reads.delete(slot);
      }
    }
  }
  async initialize() {
    if (!this.context()) return;
    await Promise.all([this.loadRoots(), this.loadRecent()]);
  }
  async loadRoots(page = 1, append = false) {
    await this.readPage<ChatFolder>(
      'roots',
      this.roots,
      (fn) => this.roots.update(fn),
      (tenant, scope, signal) =>
        this.clients
          .get()
          .chat.folders.list(tenant, {
            signal,
            query: {
              root_only: true,
              page,
              page_size: 12,
              ...(scope.workspace_id ? { workspace_id: scope.workspace_id } : {}),
            },
          }),
      append,
      (rows) => this.recordFolders(rows),
    );
  }
  async moreRoots() {
    const page = this.roots();
    if (page.pages !== null && page.page < page.pages) await this.loadRoots(page.page + 1, true);
  }
  async loadRecent(page = 1, append = false) {
    await this.readPage<ChatThread>(
      'recent',
      this.recent,
      (fn) => this.recent.update(fn),
      (tenant, scope, signal) =>
        this.clients
          .get()
          .chat.threads(tenant, {
            signal,
            query: {
              ...scope,
              page,
              page_size: 8,
              unfiled: true,
              status: 'active',
              sort: 'updated_at',
              order: 'desc',
            },
          }),
      append,
    );
  }
  async moreRecent() {
    const page = this.recent();
    if (page.pages !== null && page.page < page.pages) await this.loadRecent(page.page + 1, true);
  }
  async toggle(folder: ChatFolder) {
    this.context();
    const branch = this.branch(folder);
    this.selectedFolder.set(folder);
    this.changeBranch(folder.id, (row) => ({ ...row, expanded: !branch.expanded }));
    if (!branch.expanded && (branch.children.page === 0 || branch.threads.page === 0))
      await Promise.all([this.loadChildren(folder), this.loadFolderThreads(folder)]);
  }
  async loadChildren(folder: ChatFolder, page = 1, append = false) {
    this.branch(folder);
    await this.readPage<ChatFolder>(
      'children:' + folder.id,
      () => this.branches().get(folder.id)?.children ?? emptyConversationPage<ChatFolder>(),
      (fn) => this.changeBranch(folder.id, (row) => ({ ...row, children: fn(row.children) })),
      (tenant, scope, signal) =>
        this.clients
          .get()
          .chat.folders.list(tenant, {
            signal,
            query: {
              parent_id: folder.id,
              page,
              page_size: 12,
              ...(scope.workspace_id ? { workspace_id: scope.workspace_id } : {}),
            },
          }),
      append,
      (rows) => this.recordFolders(rows),
    );
  }
  async moreChildren(folder: ChatFolder) {
    const page = this.branches().get(folder.id)?.children;
    if (page?.pages != null && page.page < page.pages)
      await this.loadChildren(folder, page.page + 1, true);
  }
  async loadFolderThreads(folder: ChatFolder, page = 1, append = false) {
    this.branch(folder);
    await this.readPage<ChatThread>(
      'threads:' + folder.id,
      () => this.branches().get(folder.id)?.threads ?? emptyConversationPage<ChatThread>(),
      (fn) => this.changeBranch(folder.id, (row) => ({ ...row, threads: fn(row.threads) })),
      (tenant, scope, signal) =>
        this.clients
          .get()
          .chat.threads(tenant, {
            signal,
            query: {
              ...scope,
              folder_id: folder.id,
              page,
              page_size: 8,
              status: 'active',
              sort: 'updated_at',
              order: 'desc',
            },
          }),
      append,
    );
  }
  async moreFolderThreads(folder: ChatFolder) {
    const page = this.branches().get(folder.id)?.threads;
    if (page?.pages != null && page.page < page.pages)
      await this.loadFolderThreads(folder, page.page + 1, true);
  }
  async search(value: string, page = 1, append = false) {
    if (!this.context()) return;
    this.query.set(value.trim());
    if (!append) this.results.set(emptyConversationPage());
    this.reads.get('search')?.abort();
    if (!this.searchView()) return;
    await this.readPage<ChatThread>(
      'search',
      this.results,
      (fn) => this.results.update(fn),
      (tenant, scope, signal) =>
        this.clients
          .get()
          .chat.threads(tenant, {
            signal,
            query: {
              ...scope,
              q: this.query(),
              status: this.status(),
              page,
              page_size: 12,
              sort: 'updated_at',
              order: 'desc',
            },
          }),
      append,
    );
  }
  async moreResults() {
    const page = this.results();
    if (page.pages !== null && page.page < page.pages)
      await this.search(this.query(), page.page + 1, true);
  }
  async setStatus(status: 'active' | 'archived') {
    if (!this.context()) return;
    this.status.set(status);
    if (this.searchView()) await this.search(this.query());
    else await this.initialize();
  }
  private pickerQuery = '';
  async loadPicker(q = '', page = 1, append = false) {
    this.pickerQuery = q;
    await this.readPage<ChatFolder>(
      'picker',
      this.picker,
      (fn) => this.picker.update(fn),
      (tenant, scope, signal) =>
        this.clients
          .get()
          .chat.folders.list(tenant, {
            signal,
            query: {
              q,
              page,
              page_size: 12,
              ...(scope.workspace_id ? { workspace_id: scope.workspace_id } : {}),
            } as FolderFilter,
          }),
      append,
    );
  }
  async morePicker() {
    const page = this.picker();
    if (page.pages !== null && page.page < page.pages)
      await this.loadPicker(this.pickerQuery, page.page + 1, true);
  }
  canMove(thread: ChatThread, folder: ChatFolder) {
    return scopeWithin(thread.scope, folder.scope);
  }
  async refresh() {
    const expanded = [...this.branches().values()]
      .filter((row) => row.expanded)
      .map((row) => row.folder);
    await this.initialize();
    if (this.searchView()) await this.search(this.query());
    for (const folder of expanded)
      await Promise.all([this.loadChildren(folder), this.loadFolderThreads(folder)]);
  }
  private async mutate<T>(write: (tenant: string) => Promise<T>): Promise<T | null> {
    const context = this.context();
    if (!context || this.mutating()) return null;
    this.mutating.set(true);
    this.error.set(null);
    try {
      const result = await write(context.tenant);
      if (context.key !== this.scopeKey() || context.epoch !== this.epoch) return null;
      await this.refresh();
      return context.key === this.scopeKey() && context.epoch === this.epoch ? result : null;
    } catch (error) {
      if (context.key === this.scopeKey() && context.epoch === this.epoch)
        this.error.set(this.failure(error));
      return null;
    } finally {
      if (context.key === this.scopeKey() && context.epoch === this.epoch) this.mutating.set(false);
    }
  }
  private validName(value: string) {
    const name = value.trim();
    if (!name || name.length > 160) throw Error('Enter a name with 1 to 160 characters.');
    return name;
  }
  async renameThread(thread: ChatThread, title: string, expectedRevision = thread.revision) {
    return this.mutate((tenant) =>
      this.clients
        .get()
        .chat.update(tenant, thread.id, {
          title: this.validName(title),
          expected_revision: expectedRevision,
        }),
    );
  }
  async moveThread(thread: ChatThread, folder: ChatFolder | null) {
    if (folder && !this.canMove(thread, folder)) {
      this.error.set(Error('This folder uses a different knowledge scope.'));
      return null;
    }
    return this.mutate((tenant) =>
      this.clients
        .get()
        .chat.update(tenant, thread.id, {
          folder_id: folder?.id ?? null,
          expected_revision: thread.revision,
        }),
    );
  }
  async archiveThread(thread: ChatThread, archived: boolean) {
    return this.mutate((tenant) =>
      this.clients
        .get()
        .chat.update(tenant, thread.id, { archived, expected_revision: thread.revision }),
    );
  }
  async createFolder(name: string, parent: ChatFolder | null) {
    const context = this.context();
    if (!context) return null;
    const created = await this.mutate((tenant) =>
      this.clients
        .get()
        .chat.folders.create(tenant, {
          name: this.validName(name),
          parent_id: parent?.id ?? null,
          scope: parent?.scope ?? context.scope,
        }),
    );
    if (created) {
      this.branch(created);
      this.selectedFolder.set(created);
    }
    return created;
  }
  async renameFolder(folder: ChatFolder, name: string) {
    const updated = await this.mutate((tenant) =>
      this.clients
        .get()
        .chat.folders.update(tenant, folder.id, {
          name: this.validName(name),
          expected_revision: folder.revision,
        }),
    );
    if (updated) {
      this.branch(updated);
      this.changeBranch(updated.id, (row) => ({ ...row, folder: updated }));
      if (this.selectedFolder()?.id === updated.id) this.selectedFolder.set(updated);
    }
    return updated;
  }
  async deleteFolder(folder: ChatFolder) {
    const result = await this.mutate(async (tenant) => {
      await this.clients.get().chat.folders.delete(tenant, folder.id, folder.revision);
      return true;
    });
    if (result) {
      this.branches.update((rows) => {
        const next = new Map(rows);
        next.delete(folder.id);
        return next;
      });
      if (this.selectedFolder()?.id === folder.id) this.selectedFolder.set(null);
    }
    return result === true;
  }
  async latestThread(thread: ChatThread) {
    const context = this.context();
    if (!context) return null;
    try {
      const result = await this.clients.get().chat.get(context.tenant, thread.id);
      return context.key === this.scopeKey() ? result : null;
    } catch (error) {
      this.error.set(this.failure(error));
      return null;
    }
  }
  async latestFolder(folder: ChatFolder) {
    const context = this.context();
    if (!context) return null;
    try {
      const result = await this.clients.get().chat.folders.get(context.tenant, folder.id);
      return context.key === this.scopeKey() ? result : null;
    } catch (error) {
      this.error.set(this.failure(error));
      return null;
    }
  }
  async suggestTitle(thread: ChatThread, agentId: string): Promise<TitleSuggestion | null> {
    const context = this.context();
    if (!context || !agentId || this.suggesting()) return null;
    this.error.set(null);
    this.suggesting.set(true);
    const controller = new AbortController();
    this.reads.set('suggestion', controller);
    try {
      const result = await this.clients
        .get()
        .chat.suggestTitle(
          context.tenant,
          thread.id,
          { agent_id: agentId, expected_revision: thread.revision },
          { signal: controller.signal },
        );
      return context.key === this.scopeKey() && !controller.signal.aborted ? result : null;
    } catch (error) {
      if (context.key === this.scopeKey() && !controller.signal.aborted)
        this.error.set(this.failure(error));
      return null;
    } finally {
      if (context.key === this.scopeKey()) this.suggesting.set(false);
      if (this.reads.get('suggestion') === controller) this.reads.delete('suggestion');
    }
  }
  cancelSuggestion() {
    this.reads.get('suggestion')?.abort();
    this.suggesting.set(false);
  }
  ngOnDestroy() {
    this.reset();
  }
}
