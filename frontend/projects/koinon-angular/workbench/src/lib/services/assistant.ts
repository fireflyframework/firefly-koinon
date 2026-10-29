// Copyright 2026 Firefly Software Foundation SPDX-License-Identifier: Apache-2.0
import { Injectable, OnDestroy, computed, effect, inject, signal } from '@angular/core';
import type {
  AgentConfiguration,
  ChatMessage,
  ChatRun,
  ChatThread,
  KnowledgeScope,
  ChatEventData,
  StreamEvent,
  Page,
  ThreadPatch,
  ToolActivity,
  ChatFolder,
} from '@fireflyframework/koinon-sdk';
import { KoinonFacade } from '../koinon-facade';
import { KoinonClientContext } from './client-context';
@Injectable()
export class KoinonAssistant implements OnDestroy {
  private readonly f = inject(KoinonFacade);
  private readonly clients = inject(KoinonClientContext);
  private epoch = 0;
  readonly contextVersion = signal(0);
  private readonly activityGenerations = new Map<string, number>();
  private scopeKey = '';
  private abort?: AbortController;
  private streamText = '';
  private historyExpanded = false;
  private historyRequest = 0;
  private readonly activeRecord = signal<ChatThread | undefined>(undefined);
  private readonly eventCursors = new Map<string, string>();
  readonly olderCursor = signal<string | null>(null);
  readonly pendingHistory = signal(false);
  readonly agents = signal<AgentConfiguration[]>([]);
  readonly threads = signal<ChatThread[]>([]);
  readonly historyPage = signal<Page<ChatThread> | null>(null);
  readonly historyQuery = signal('');
  readonly historyStatus = signal<'active' | 'archived'>('active');
  readonly pendingThreads = signal(false);
  readonly historyCollapsed = signal(false);
  readonly draftFolder = signal<ChatFolder | null>(null);
  readonly historyError = signal('');
  readonly messages = signal<ChatMessage[]>([]);
  readonly threadId = signal('');
  readonly agentId = signal('');
  readonly runId = signal('');
  readonly pending = signal(false);
  readonly running = signal(false);
  readonly error = signal('');
  readonly toolActivity = signal('');
  readonly activityLoading = signal(new Set<string>());
  readonly activityErrors = signal<Record<string, string>>({});
  private readonly activityPages = new Map<string, number>();
  readonly activeThread = computed(() => this.activeRecord());
  readonly selectedAgent = computed(() => this.agents().find((x) => x.id === this.agentId()));
  readonly libraryScope = computed<KnowledgeScope>(() => {
    const folder = this.f.entries().find((x) => x.id === this.f.parentId());
    const selected = this.f.selected();
    return {
      ...(this.f.workspaceId() ? { workspace_id: this.f.workspaceId() } : {}),
      ...(this.f.projectId() ? { project_id: this.f.projectId() } : {}),
      ...(folder && (folder.kind === 'collection' || folder.kind === 'corpus')
        ? { collection_id: folder.id }
        : {}),
      ...(selected && (selected.kind === 'document' || selected.kind === 'dataset')
        ? { asset_ids: [selected.id] }
        : {}),
    };
  });
  readonly scope = computed(
    () => this.activeThread()?.scope ?? this.draftFolder()?.scope ?? this.libraryScope(),
  );
  private currentScopeKey() {
    return [
      this.f.tenantId(),
      this.f.workspaceId(),
      this.f.projectId(),
      this.f.selected()?.id ?? '',
      this.clients.revision(),
    ].join(':');
  }
  constructor() {
    this.scopeKey = this.currentScopeKey();
    effect(() => {
      const key = this.currentScopeKey();
      if (key !== this.scopeKey) {
        this.scopeKey = key;
        this.reset();
      }
    });
  }
  private reset() {
    this.contextVersion.update((value) => value + 1);
    this.activityGenerations.clear();
    this.olderCursor.set(null);
    this.pendingHistory.set(false);
    this.historyExpanded = false;
    ++this.historyRequest;
    this.historyPage.set(null);
    this.historyQuery.set('');
    this.historyStatus.set('active');
    this.pendingThreads.set(false);
    this.historyError.set('');
    this.activeRecord.set(undefined);
    this.draftFolder.set(null);
    ++this.epoch;
    this.abort?.abort();
    this.agents.set([]);
    this.threads.set([]);
    this.messages.set([]);
    this.threadId.set('');
    this.agentId.set('');
    this.runId.set('');
    this.pending.set(false);
    this.running.set(false);
    this.error.set('');
    this.toolActivity.set('');
    this.eventCursors.clear();
    this.activityLoading.set(new Set());
    this.activityErrors.set({});
    this.activityPages.clear();
  }
  private fail(error: unknown) {
    const message =
      error instanceof Error ? error.message : 'The conversation could not be opened.';
    if (error instanceof Error && 'status' in error && error.status === 401)
      this.f.authRequired.set(true);
    this.error.set(message);
  }
  async initialize(agentOverride?: string) {
    const epoch = ++this.epoch,
      tenant = this.f.tenantId(),
      scopeKey = this.currentScopeKey();
    this.agentId.set('');
    this.pending.set(true);
    this.error.set('');
    try {
      const client = this.clients.get();
      const scope = this.libraryScope();
      const query = {
        ...(scope.workspace_id ? { workspace_id: scope.workspace_id } : {}),
        ...(scope.project_id ? { project_id: scope.project_id } : {}),
      };
      const [agents, threads, settings] = await Promise.all([
        client.agents.list(tenant, { query }),
        client.chat.threads(tenant, {
          query: { page: 1, page_size: 25, status: 'active', ...query },
        }),
        agentOverride ? Promise.resolve(null) : client.organizationChat.get(tenant, query),
      ]);
      if (epoch !== this.epoch || scopeKey !== this.currentScopeKey()) return;
      const id =
        agentOverride ||
        (settings?.tenant_id === tenant && settings.configured && settings.can_run
          ? settings.default_agent_id
          : null);
      const available = [...agents.items];
      for (
        let page = 2;
        id && !available.some((agent) => agent.id === id) && page <= (agents.pages ?? 1);
        ++page
      ) {
        const next = await client.agents.list(tenant, { query: { ...query, page } });
        if (epoch !== this.epoch || scopeKey !== this.currentScopeKey()) return;
        available.push(...next.items);
      }
      this.agents.set(available);
      this.agentId.set(available.some((agent) => agent.id === id) ? id! : '');
      this.threads.set(threads.items);
      this.historyPage.set(threads);
      const first = this.threads()[0];
      if (first) await this.selectThread(first.id);
    } catch (error) {
      if (epoch === this.epoch) this.fail(error);
    } finally {
      if (epoch === this.epoch) this.pending.set(false);
    }
  }
  async loadThreads(options: { page?: number; q?: string; status?: 'active' | 'archived' } = {}) {
    const request = ++this.historyRequest;
    const scopeKey = this.currentScopeKey();
    const scope = this.libraryScope();
    const q = (options.q ?? this.historyQuery()).trim();
    const status = options.status ?? this.historyStatus();
    this.historyQuery.set(q);
    this.historyStatus.set(status);
    this.pendingThreads.set(true);
    this.historyError.set('');
    this.threads.set([]);
    this.historyPage.set(null);
    try {
      const result = await this.clients.get().chat.threads(this.f.tenantId(), {
        query: {
          page: options.page ?? 1,
          page_size: 25,
          q,
          status,
          ...(scope.workspace_id ? { workspace_id: scope.workspace_id } : {}),
          ...(scope.project_id ? { project_id: scope.project_id } : {}),
        },
      });
      if (request !== this.historyRequest || scopeKey !== this.currentScopeKey()) return;
      this.threads.set(result.items);
      this.historyPage.set(result);
    } catch (error) {
      if (request === this.historyRequest && scopeKey === this.currentScopeKey()) {
        this.historyError.set(
          error instanceof Error ? error.message : 'Conversations could not be loaded.',
        );
        if (error instanceof Error && 'status' in error && error.status === 401)
          this.f.authRequired.set(true);
      }
    } finally {
      if (request === this.historyRequest) this.pendingThreads.set(false);
    }
  }
  newConversation(folder: ChatFolder | null = null) {
    if (this.running()) return;
    ++this.epoch;
    this.contextVersion.update((value) => value + 1);
    this.abort?.abort();
    this.pending.set(false);
    this.activityLoading.set(new Set());
    this.activityErrors.set({});
    this.olderCursor.set(null);
    this.pendingHistory.set(false);
    this.historyExpanded = false;
    this.threadId.set('');
    this.draftFolder.set(folder);
    this.activeRecord.set(undefined);
    this.messages.set([]);
    this.error.set('');
    this.runId.set('');
  }
  async updateThread(patch: Omit<ThreadPatch, 'expected_revision'>): Promise<boolean> {
    const thread = this.activeRecord();
    if (!thread || this.running() || this.pending()) return false;
    const epoch = this.epoch;
    this.pending.set(true);
    this.error.set('');
    try {
      const updated = await this.clients.get().chat.update(this.f.tenantId(), thread.id, {
        ...patch,
        expected_revision: thread.revision,
      });
      if (epoch !== this.epoch || this.threadId() !== thread.id) return false;
      this.activeRecord.set(updated);
      await this.loadThreads({
        page: patch.archived === false ? 1 : (this.historyPage()?.page ?? 1),
        status: patch.archived === false ? 'active' : this.historyStatus(),
      });
      return true;
    } catch (error) {
      if (epoch === this.epoch) this.fail(error);
      return false;
    } finally {
      if (epoch === this.epoch) this.pending.set(false);
    }
  }
  applyThread(updated: ChatThread) {
    if (updated.id === this.threadId() && updated.revision >= (this.activeRecord()?.revision ?? 0))
      this.activeRecord.set(updated);
    this.threads.update((rows) =>
      rows.map((row) =>
        row.id === updated.id && updated.revision >= row.revision ? updated : row,
      ),
    );
  }
  async selectThread(id: string, supplied?: ChatThread) {
    const selected = supplied?.id === id ? supplied : this.threads().find((row) => row.id === id);
    if (this.running() || !selected) return;
    const epoch = ++this.epoch;
    this.contextVersion.update((value) => value + 1);
    this.threadId.set(id);
    this.activeRecord.set(selected);
    this.activityLoading.set(new Set());
    this.activityErrors.set({});
    this.messages.set([]);
    this.olderCursor.set(null);
    this.pendingHistory.set(false);
    this.historyExpanded = false;
    this.pending.set(true);
    this.error.set('');
    try {
      await this.reload(epoch, id);
      const active = this.messages().find(
        (message) =>
          message.role === 'assistant' &&
          message.run_id &&
          ['queued', 'running'].includes(message.status),
      );
      if (active && epoch === this.epoch) {
        this.runId.set(active.run_id!);
        void this.listen(
          { run_id: active.run_id!, message_id: active.id, event_cursor: active.event_cursor },
          epoch,
        );
      }
    } catch (error) {
      if (epoch === this.epoch) this.fail(error);
    } finally {
      if (epoch === this.epoch) this.pending.set(false);
    }
  }
  private async reload(epoch: number, thread = this.threadId()) {
    const result = await this.clients
      .get()
      .chat.messages(this.f.tenantId(), thread, { query: { limit: 40 } });
    if (epoch === this.epoch && thread === this.threadId()) {
      this.messages.set(this.mergeMessages(this.messages(), result.items));
      if (!this.historyExpanded) this.olderCursor.set(result.next_cursor ?? null);
      for (const message of result.items)
        if (message.run_id && message.event_cursor)
          this.eventCursors.set(message.run_id, message.event_cursor);
    }
  }
  private async refreshThread(epoch: number, thread = this.threadId()) {
    const canonical = await this.clients.get().chat.get(this.f.tenantId(), thread);
    if (epoch !== this.epoch || thread !== this.threadId() || canonical.id !== thread) return;
    if (canonical.revision >= (this.activeRecord()?.revision ?? 0))
      this.activeRecord.set(canonical);
    this.threads.update((rows) =>
      rows.map((row) =>
        row.id === thread && canonical.revision >= (row.revision ?? 0) ? canonical : row,
      ),
    );
  }
  private mergeMessages(current: ChatMessage[], incoming: ChatMessage[]) {
    const merged = new Map(current.map((message) => [message.id, message]));
    for (const message of incoming) {
      const previous = merged.get(message.id);
      merged.set(
        message.id,
        previous && this.activityPages.has(message.id)
          ? {
              ...message,
              tool_activities: this.mergeActivity(
                previous.tool_activities ?? [],
                message.tool_activities ?? [],
              ),
            }
          : message,
      );
    }
    return [...merged.values()].sort(
      (a, b) => a.created_at.localeCompare(b.created_at) || a.id.localeCompare(b.id),
    );
  }
  async loadOlder() {
    const cursor = this.olderCursor();
    if (!cursor || this.pendingHistory()) return;
    const epoch = this.epoch,
      thread = this.threadId();
    this.pendingHistory.set(true);
    this.error.set('');
    try {
      const page = await this.clients
        .get()
        .chat.messages(this.f.tenantId(), thread, { query: { before: cursor, limit: 40 } });
      if (epoch !== this.epoch || thread !== this.threadId()) return;
      this.messages.set(this.mergeMessages(page.items, this.messages()));
      this.olderCursor.set(page.next_cursor ?? null);
      this.historyExpanded = true;
    } catch (error) {
      if (epoch === this.epoch) this.fail(error);
    } finally {
      if (epoch === this.epoch) this.pendingHistory.set(false);
    }
  }
  canUseAgent(agent: AgentConfiguration | undefined = this.selectedAgent()) {
    return !!agent && (agent.can_run ?? agent.status === 'ready');
  }
  private async createThread(epoch: number): Promise<string | null> {
    const current = this.threadId();
    if (current) return current;
    const folder = this.draftFolder();
    const created = await this.clients.get().chat.create(this.f.tenantId(), {
      scope: folder?.scope ?? this.libraryScope(),
      ...(folder ? { folder_id: folder.id } : {}),
    });
    if (epoch !== this.epoch) return null;
    this.threadId.set(created.id);
    this.activeRecord.set(created);
    this.draftFolder.set(null);
    if (this.historyStatus() === 'active' && !this.historyQuery())
      this.threads.update((rows) => [created, ...rows]);
    return created.id;
  }
  async ensureThread(): Promise<string | null> {
    if (this.running() || this.pending() || !this.canUseAgent()) return null;
    const epoch = this.epoch;
    this.pending.set(true);
    this.error.set('');
    try {
      return await this.createThread(epoch);
    } catch (error) {
      if (epoch === this.epoch) this.fail(error);
      return null;
    } finally {
      if (epoch === this.epoch) this.pending.set(false);
    }
  }
  async send(text: string, attachmentIds: readonly string[] = []): Promise<boolean> {
    if (this.running() || this.pending() || !text.trim()) return false;
    const agent = this.selectedAgent();
    if (!this.canUseAgent(agent)) {
      this.error.set('Choose an available agent before starting a conversation.');
      return false;
    }
    const epoch = this.epoch,
      tenant = this.f.tenantId(),
      client = this.clients.get();
    this.pending.set(true);
    this.error.set('');
    let admitted = false;
    try {
      const thread = await this.createThread(epoch);
      if (!thread) return false;
      const run = await client.chat.submit(tenant, thread, {
        agent_id: agent!.id,
        message: text.trim(),
        scope: this.scope(),
        client_request_id: crypto.randomUUID(),
        ...(attachmentIds.length ? { attachment_ids: [...attachmentIds] } : {}),
      });
      admitted = true;
      if (epoch !== this.epoch) return true;
      this.runId.set(run.run_id);
      await this.reload(epoch, thread);
      this.pending.set(false);
      await this.listen(run, epoch);
      return true;
    } catch (error) {
      if (epoch === this.epoch) this.fail(error);
      return admitted;
    } finally {
      if (epoch === this.epoch) this.pending.set(false);
    }
  }
  private updateMessage(id: string, update: (message: ChatMessage) => ChatMessage) {
    this.messages.update((rows) =>
      rows.map((message) => (message.id === id ? update(message) : message)),
    );
  }
  private async listen(run: ChatRun, epoch: number) {
    const observed = this.messages().find((message) => message.id === run.message_id);
    if (observed && ['completed', 'failed', 'cancelled'].includes(observed.status)) {
      this.running.set(false);
      await this.refreshThread(epoch);
      if (epoch === this.epoch && !this.pendingThreads())
        await this.loadThreads({ page: this.historyPage()?.page ?? 1 });
      return;
    }
    this.abort?.abort();
    const abort = new AbortController();
    this.abort = abort;
    this.running.set(true);
    this.toolActivity.set('');
    const hydratedCursor = this.eventCursors.get(run.run_id);
    this.streamText = hydratedCursor
      ? (this.messages().find((message) => message.id === run.message_id)?.text ?? '')
      : '';
    let terminal = false;
    try {
      for (
        let attempt = 0;
        attempt < 3 && !terminal && epoch === this.epoch && !abort.signal.aborted;
        ++attempt
      ) {
        try {
          const cursor = this.eventCursors.get(run.run_id) ?? run.event_cursor ?? '';
          for await (const event of this.clients.get().chat.events(this.f.tenantId(), run.run_id, {
            signal: abort.signal,
            ...(cursor ? { headers: { 'Last-Event-ID': cursor } } : {}),
          })) {
            if (epoch !== this.epoch || abort.signal.aborted) break;
            const seen = this.eventCursors.get(run.run_id);
            if (
              event.id &&
              seen &&
              /^\d+$/.test(event.id) &&
              /^\d+$/.test(seen) &&
              BigInt(event.id) <= BigInt(seen)
            )
              continue;
            if (event.id) this.eventCursors.set(run.run_id, event.id);
            terminal = await this.apply(event, run, epoch);
            if (terminal) break;
          }
          if (epoch !== this.epoch || abort.signal.aborted) return;
          if (!terminal) {
            await this.reload(epoch);
            const latest = this.messages().find((message) => message.id === run.message_id);
            terminal = !!latest && ['completed', 'failed', 'cancelled'].includes(latest.status);
          }
        } catch (error) {
          const status = error instanceof Error && 'status' in error ? error.status : undefined;
          if (
            !(error instanceof TypeError) &&
            ![408, 429, 500, 502, 503, 504].includes(Number(status))
          )
            throw error;
          if (attempt === 2) throw error;
        }
        if (epoch !== this.epoch || abort.signal.aborted) return;
        if (!terminal && attempt < 2) {
          this.toolActivity.set('Reconnecting to your answer…');
          await this.reconnectDelay(abort.signal, 300 * 2 ** attempt);
        }
      }
      if (!terminal && epoch === this.epoch && !abort.signal.aborted)
        this.error.set(
          'The connection ended before the answer finished. Reopen the conversation to check its current status.',
        );
      if (terminal && epoch === this.epoch && !abort.signal.aborted) {
        await this.refreshThread(epoch);
        if (epoch === this.epoch && !this.pendingThreads())
          await this.loadThreads({ page: this.historyPage()?.page ?? 1 });
      }
    } catch (error) {
      if (epoch === this.epoch && !abort.signal.aborted) this.fail(error);
    } finally {
      if (epoch === this.epoch) {
        this.running.set(false);
        this.toolActivity.set('');
      }
    }
  }
  private reconnectDelay(signal: AbortSignal, milliseconds: number): Promise<void> {
    return new Promise((resolve) => {
      const finish = () => {
        clearTimeout(timer);
        signal.removeEventListener('abort', finish);
        resolve();
      };
      const timer = setTimeout(finish, milliseconds);
      signal.addEventListener('abort', finish, { once: true });
      if (signal.aborted) finish();
    });
  }
  private async apply(
    event: StreamEvent<ChatEventData>,
    run: ChatRun,
    epoch: number,
  ): Promise<boolean> {
    const data = event.data;
    if (data.message_id && data.message_id !== run.message_id) return false;
    if (event.type === 'message_reset') {
      this.streamText = '';
      this.activityPages.delete(run.message_id);
      this.activityGenerations.set(
        run.message_id,
        (this.activityGenerations.get(run.message_id) ?? 0) + 1,
      );
      this.activityLoading.update(
        (rows) => new Set([...rows].filter((id) => id !== run.message_id)),
      );
      this.activityErrors.update((rows) => ({ ...rows, [run.message_id]: '' }));
      this.updateMessage(run.message_id, (message) => {
        const reset = {
          ...message,
          text: '',
          artifacts: [],
          citations: [],
          status: data.status ?? 'running',
          tool_activities: [],
          tool_activity_count: 0,
          tool_activity_has_more: false,
        };
        delete reset.answer_policy;
        return reset;
      });
      await this.reload(epoch);
      const hydrated = this.messages().find((message) => message.id === run.message_id);
      if (hydrated?.event_cursor) this.streamText = hydrated.text;
    }
    if (event.type === 'message_metadata') {
      this.updateMessage(run.message_id, (message) => ({
        ...message,
        ...(data.presentation ? { presentation: data.presentation } : {}),
        ...(data.answer_policy ? { answer_policy: data.answer_policy } : {}),
      }));
    }
    if (event.type === 'message_delta' && data.text) {
      this.streamText += data.text;
      this.updateMessage(run.message_id, (message) => ({
        ...message,
        text: message.text.startsWith(this.streamText) ? message.text : this.streamText,
      }));
    }
    if (event.type === 'tool_activity') {
      this.toolActivity.set(data.message ?? data.stage ?? '');
      if (data.tool_activity)
        this.updateMessage(run.message_id, (message) => {
          const activities = this.mergeActivity(message.tool_activities ?? [], [
            data.tool_activity!,
          ]);
          return {
            ...message,
            tool_activities: activities,
            tool_activity_count: Math.max(message.tool_activity_count ?? 0, activities.length),
          };
        });
    }
    if (event.type === 'openui_delta' && data.artifact) {
      const artifact = data.artifact;
      if (artifact.run_id !== run.run_id)
        throw new Error('This evidence belongs to a different answer.');
      this.updateMessage(run.message_id, (message) => ({
        ...message,
        artifacts: [...message.artifacts.filter((x) => x.id !== artifact.id), artifact],
      }));
    }
    if (event.type === 'citation' && data.citation) {
      const citation = data.citation;
      this.updateMessage(run.message_id, (message) => ({
        ...message,
        citations: message.citations.some((x) => JSON.stringify(x) === JSON.stringify(citation))
          ? message.citations
          : [...message.citations, citation],
      }));
    }
    if (['completed', 'failed', 'cancelled'].includes(event.type)) {
      if (event.type === 'failed')
        this.error.set(data.message ?? 'The answer could not be completed.');
      await this.reload(epoch);
      return true;
    }
    return false;
  }
  private mergeActivity(current: ToolActivity[], incoming: ToolActivity[]): ToolActivity[] {
    const merged = new Map(current.map((item) => [item.call_id, item]));
    for (const item of incoming) {
      const previous = merged.get(item.call_id);
      const terminal = (status: ToolActivity['status']) =>
        ['completed', 'failed', 'cancelled'].includes(status);
      if (
        !previous ||
        (item.occurred_at >= previous.occurred_at &&
          (!terminal(previous.status) || terminal(item.status)))
      )
        merged.set(item.call_id, item);
    }
    return [...merged.values()];
  }
  async loadActivity(message: ChatMessage) {
    if (!message.run_id || this.activityLoading().has(message.id)) return;
    const generation = this.activityGenerations.get(message.id) ?? 0;
    const epoch = this.epoch,
      thread = this.threadId(),
      page = (this.activityPages.get(message.id) ?? 0) + 1;
    this.activityLoading.update((rows) => new Set([...rows, message.id]));
    this.activityErrors.update((rows) => ({ ...rows, [message.id]: '' }));
    try {
      const result = await this.clients
        .get()
        .chat.activities(this.f.tenantId(), message.run_id, { query: { page, page_size: 25 } });
      if (
        epoch !== this.epoch ||
        thread !== this.threadId() ||
        generation !== (this.activityGenerations.get(message.id) ?? 0)
      )
        return;
      this.activityPages.set(message.id, page);
      this.updateMessage(message.id, (current) => ({
        ...current,
        tool_activities: this.mergeActivity(current.tool_activities ?? [], result.items),
        tool_activity_count: result.total,
        tool_activity_has_more:
          result.page !== undefined && result.pages !== undefined && result.page < result.pages,
      }));
    } catch (error) {
      if (epoch === this.epoch && generation === (this.activityGenerations.get(message.id) ?? 0))
        this.activityErrors.update((rows) => ({
          ...rows,
          [message.id]:
            error instanceof Error ? error.message : 'Tool activity could not be loaded.',
        }));
    } finally {
      if (epoch === this.epoch && generation === (this.activityGenerations.get(message.id) ?? 0))
        this.activityLoading.update((rows) => new Set([...rows].filter((id) => id !== message.id)));
    }
  }
  async cancel() {
    if (!this.runId() || !this.running()) return;
    const epoch = this.epoch;
    try {
      const result = await this.clients.get().chat.cancel(this.f.tenantId(), this.runId());
      if (epoch !== this.epoch) return;
      if (result.status === 'cancelled') {
        this.abort?.abort();
        this.running.set(false);
        await this.reload(epoch);
      } else this.toolActivity.set('Stopping the answer…');
    } catch (error) {
      if (epoch === this.epoch) this.fail(error);
    }
  }
  async retry(message: ChatMessage) {
    if (this.running() || this.pending() || !message.run_id) return;
    const epoch = this.epoch;
    this.pending.set(true);
    this.error.set('');
    try {
      const run = await this.clients.get().chat.retry(this.f.tenantId(), message.run_id);
      if (epoch !== this.epoch) return;
      this.runId.set(run.run_id);
      await this.reload(epoch);
      this.pending.set(false);
      await this.listen(run, epoch);
    } catch (error) {
      if (epoch === this.epoch) this.fail(error);
    } finally {
      if (epoch === this.epoch) this.pending.set(false);
    }
  }
  readonly resolveEvidence = (runId: string, resultId: string, signal?: AbortSignal) =>
    this.clients.get().chat.result(this.f.tenantId(), runId, resultId, { signal });
  ngOnDestroy() {
    ++this.epoch;
    this.abort?.abort();
  }
}
