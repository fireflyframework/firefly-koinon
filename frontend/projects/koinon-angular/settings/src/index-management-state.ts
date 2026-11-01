// Copyright 2026 Firefly Software Foundation
// SPDX-License-Identifier: Apache-2.0
import { computed, signal } from '@angular/core';
import type {
  IndexPlanInput,
  IndexPlanView,
  KnowledgeIndexView,
  KoinonClient,
  NativeIndexChoice,
} from '@fireflyframework/koinon-sdk';
import {
  availableIndexActions,
  embeddingAssignment,
  sameIndexScope,
  type IndexActionName,
  type IndexManagementScope,
  type SavedIndexWrite,
} from './index-management-contract';
import { IndexActionJournal } from './index-management-journal';
interface Preconditions {
  activeId: string | null;
  connectionRevision: number | null;
  connectionSpaceId: string | null;
}
interface ActionReview {
  action: IndexActionName;
  target: KnowledgeIndexView;
  before: Preconditions;
  supersedes: SavedIndexWrite | null;
}
interface IndexView {
  rows: KnowledgeIndexView[];
  total: number;
  page: number;
  filter: string;
  active: NativeIndexChoice | null;
  activeKnown: boolean;
  selected: KnowledgeIndexView | null;
  plan: IndexPlanView | null;
  review: ActionReview | null;
  unknown: SavedIndexWrite | null;
  loading: boolean;
  busy: boolean;
  error: string;
  notice: string;
  journalError: boolean;
  accessDenied: boolean;
}
const empty = (): IndexView => ({
  rows: [],
  total: 0,
  page: 1,
  filter: '',
  active: null,
  activeKnown: false,
  selected: null,
  plan: null,
  review: null,
  unknown: null,
  loading: false,
  busy: false,
  error: '',
  notice: '',
  journalError: false,
  accessDenied: false,
});
interface Session {
  scope: IndexManagementScope;
  abort: AbortController;
  client: KoinonClient;
}
interface Ports {
  scope: () => IndexManagementScope;
  client: () => KoinonClient;
  journal: IndexActionJournal;
  denied?: (status: 401 | 403) => void;
}
export class IndexManagementState {
  private readonly state = signal<IndexView>(empty());
  private scope: IndexManagementScope;
  private session: Session | null = null;
  private alive = true;
  readonly view = computed(() =>
    this.alive && sameIndexScope(this.scope, this.ports.scope()) ? this.state() : empty(),
  );
  constructor(private readonly ports: Ports) {
    this.scope = ports.scope();
    this.restore();
  }
  private restore() {
    try {
      this.state.update((v) => ({ ...v, unknown: this.ports.journal.get(this.scope) }));
    } catch {
      this.state.update((v) => ({
        ...v,
        journalError: true,
        error:
          'Saved index actions could not be verified. Session storage is required before changing indexes.',
      }));
    }
  }
  syncScope() {
    const scope = this.ports.scope();
    if (sameIndexScope(scope, this.scope)) return;
    this.session?.abort.abort();
    this.session = null;
    this.scope = scope;
    this.state.set(empty());
    this.restore();
  }
  private current(s: Session) {
    return (
      this.alive &&
      this.session === s &&
      !s.abort.signal.aborted &&
      sameIndexScope(s.scope, this.ports.scope())
    );
  }
  private set(s: Session, change: Partial<IndexView>) {
    if (this.current(s)) this.state.update((v) => ({ ...v, ...change }));
  }
  private check(s: Session) {
    if (!this.current(s)) throw new DOMException('Scope changed', 'AbortError');
  }
  private options(s: Session) {
    this.check(s);
    return { signal: s.abort.signal };
  }
  private scoped(s: Session, row: { tenant_id: string; workspace_id: string; domain: string }) {
    this.check(s);
    if (
      row.tenant_id !== s.scope.tenantId ||
      row.workspace_id !== s.scope.workspaceId ||
      row.domain !== s.scope.domain
    )
      throw Error('Response scope disagrees');
  }
  private async run(manage: boolean, work: (s: Session) => Promise<void>) {
    this.syncScope();
    if (
      !this.alive ||
      this.session ||
      !this.scope.read ||
      this.state().accessDenied ||
      (manage && (!this.scope.manage || this.state().journalError))
    )
      return;
    const s: Session = {
      scope: { ...this.scope },
      abort: new AbortController(),
      client: this.ports.client(),
    };
    this.session = s;
    this.set(s, { loading: !manage, busy: manage, error: '', notice: '' });
    try {
      await work(s);
    } catch (failure) {
      if (!this.current(s)) return;
      const status = failure instanceof Error && 'status' in failure ? failure.status : null;
      if (status === 401 || status === 403) {
        this.set(s, {
          rows: [],
          selected: null,
          plan: null,
          review: null,
          active: null,
          activeKnown: false,
          accessDenied: true,
          error:
            'Current access could not be verified. Refresh your account access before continuing.',
        });
        this.ports.denied?.(status);
      } else
        this.set(s, {
          error: this.state().unknown
            ? 'The result is not confirmed. Inspect current indexes before deciding what to do next.'
            : 'Index information could not be verified. Refresh the current state before continuing.',
        });
    } finally {
      if (this.session === s) {
        this.set(s, { loading: false, busy: false });
        this.session = null;
      }
    }
  }
  private async active(s: Session) {
    const rows: NativeIndexChoice[] = [];
    const seen = new Set<string>();
    for (let offset = 0; offset < 1000; offset += 100) {
      const page = await s.client.knowledgeIndexes.choices(
        s.scope.tenantId,
        { workspace_id: s.scope.workspaceId, domain: s.scope.domain, limit: 100, offset },
        this.options(s),
      );
      this.check(s);
      if (
        page.offset !== offset ||
        page.limit !== 100 ||
        !Number.isSafeInteger(page.total) ||
        page.total < 0 ||
        page.items.length > 100
      )
        throw Error('Incomplete inventory');
      for (const row of page.items) {
        this.scoped(s, row);
        if (seen.has(row.id)) throw Error('Duplicate index identity');
        seen.add(row.id);
        rows.push(row);
      }
      if (offset + page.items.length >= page.total) {
        const active = rows.filter((row) => row.active);
        if (active.length > 1) throw Error('Conflicting active targets');
        return active[0] ?? null;
      }
      if (!page.items.length) break;
    }
    throw Error('Index inventory exceeds bounded inspection');
  }
  private async before(s: Session): Promise<Preconditions> {
    const [active, scoped, inherited] = await Promise.all([
      this.active(s),
      Promise.resolve().then(() =>
        s.client.knowledgeConnections.list(s.scope.tenantId, s.scope.workspaceId, this.options(s)),
      ),
      Promise.resolve().then(() =>
        s.client.knowledgeConnections.list(s.scope.tenantId, undefined, this.options(s)),
      ),
    ]);
    this.check(s);
    for (const row of [...scoped.items, ...inherited.items])
      if (row.tenant_id !== s.scope.tenantId) throw Error('Assignment scope disagrees');
    const connection = embeddingAssignment(
      scoped.items,
      inherited.items,
      s.scope.domain,
      s.scope.workspaceId,
    );
    return {
      activeId: active?.id ?? null,
      connectionRevision: connection?.revision ?? null,
      connectionSpaceId: connection?.space_id ?? null,
    };
  }
  private async read(s: Session, page: number, filter: string) {
    const selectedId = this.state().selected?.id;
    const [list, active, selected] = await Promise.all([
      s.client.knowledgeIndexes.list(
        s.scope.tenantId,
        {
          workspace_id: s.scope.workspaceId,
          domain: s.scope.domain,
          limit: 25,
          offset: (page - 1) * 25,
          ...(filter ? { status: filter } : {}),
        },
        this.options(s),
      ),
      this.active(s),
      selectedId
        ? s.client.knowledgeIndexes.get(s.scope.tenantId, selectedId, this.options(s))
        : Promise.resolve(null),
    ]);
    this.check(s);
    if (
      list.limit !== 25 ||
      list.offset !== (page - 1) * 25 ||
      !Number.isSafeInteger(list.total) ||
      list.total < 0 ||
      list.items.length > 25
    )
      throw Error('Invalid index page');
    for (const row of list.items) this.scoped(s, row);
    if (selected) {
      this.scoped(s, selected);
      if (selected.id !== selectedId) throw Error('Selected target identity changed');
    }
    this.set(s, {
      rows: list.items,
      total: list.total,
      page,
      filter,
      active,
      activeKnown: true,
      selected,
    });
  }
  async load(page = this.view().page, filter = this.view().filter) {
    if (!Number.isSafeInteger(page) || page < 1) return;
    return this.run(false, (s) => this.read(s, page, filter));
  }
  async select(id: string) {
    return this.run(false, async (s) => {
      const row = await s.client.knowledgeIndexes.get(s.scope.tenantId, id, this.options(s));
      this.scoped(s, row);
      if (row.id !== id) throw Error('Target identity changed');
      this.set(s, { selected: row, review: null, plan: null });
    });
  }
  closeReview() {
    if (!this.view().busy) this.state.update((v) => ({ ...v, review: null, plan: null }));
  }
  async plan(input: IndexPlanInput) {
    return this.run(true, async (s) => {
      if (
        this.state().unknown ||
        input.workspace_id !== s.scope.workspaceId ||
        input.domain !== s.scope.domain
      )
        return;
      const plan = await s.client.knowledgeIndexes.plan(s.scope.tenantId, input, this.options(s));
      this.scoped(s, plan);
      if (plan.provider_id !== input.provider_id || plan.model_id !== input.model_id)
        throw Error('Plan identity changed');
      this.set(s, { plan, review: null });
    });
  }
  async build() {
    return this.run(true, async (s) => {
      const plan = this.state().plan;
      if (!plan || this.state().unknown) return;
      const [before, configuration] = await Promise.all([
        this.before(s),
        s.client.configuration.get(s.scope.tenantId, this.options(s)),
      ]);
      this.check(s);
      const provider = configuration.providers.find((row) => row.id === plan.provider_id);
      if (
        before.activeId !== plan.active_index_id ||
        before.connectionRevision !== plan.expected_connection_revision ||
        !provider?.enabled ||
        provider.revision !== plan.provider_revision ||
        !provider.model_ids.includes(plan.model_id)
      ) {
        this.set(s, {
          plan: null,
          error: 'The reviewed configuration changed. Request and review a new plan.',
        });
        return;
      }
      await this.write(s, {
        subject: s.scope.subject,
        tenantId: s.scope.tenantId,
        workspaceId: s.scope.workspaceId,
        domain: s.scope.domain,
        createdAt: Date.now(),
        write: {
          operation: 'create',
          targetId: null,
          key: crypto.randomUUID(),
          input: {
            workspace_id: s.scope.workspaceId,
            domain: s.scope.domain,
            provider_id: plan.provider_id,
            model_id: plan.model_id,
            expected_dimensions: plan.dimensions,
            expected_active_id: plan.active_index_id,
            expected_connection_revision: plan.expected_connection_revision,
            batch_size: 32,
          },
        },
      });
    });
  }
  async reviewAction(action: IndexActionName) {
    return this.run(true, async (s) => {
      const selected = this.state().selected,
        unknown = this.state().unknown;
      if (
        !selected ||
        (unknown &&
          !(
            unknown.write.operation === 'activate' &&
            unknown.write.targetId === selected.id &&
            ['finish', 'restore_previous'].includes(action)
          ))
      )
        return;
      const [row, before] = await Promise.all([
        s.client.knowledgeIndexes.get(s.scope.tenantId, selected.id, this.options(s)),
        this.before(s),
      ]);
      this.scoped(s, row);
      if (row.id !== selected.id || !availableIndexActions(row).includes(action)) {
        this.set(s, {
          selected: row,
          review: null,
          error:
            'This action is unavailable in the current index state. Review the updated details.',
        });
        return;
      }
      this.set(s, {
        selected: row,
        plan: null,
        review: { action, target: row, before, supersedes: unknown },
      });
    });
  }
  async confirmAction() {
    return this.run(true, async (s) => {
      const review = this.state().review;
      if (!review || (this.state().unknown && !review.supersedes)) return;
      const [row, before] = await Promise.all([
        s.client.knowledgeIndexes.get(s.scope.tenantId, review.target.id, this.options(s)),
        this.before(s),
      ]);
      this.scoped(s, row);
      if (
        row.id !== review.target.id ||
        row.revision !== review.target.revision ||
        before.activeId !== review.before.activeId ||
        before.connectionRevision !== review.before.connectionRevision ||
        !availableIndexActions(row).includes(review.action)
      ) {
        this.set(s, {
          selected: row,
          review: null,
          error: 'The reviewed index or assignment changed. Review the current state again.',
        });
        return;
      }
      const base = {
        subject: s.scope.subject,
        tenantId: s.scope.tenantId,
        workspaceId: s.scope.workspaceId,
        domain: s.scope.domain,
        createdAt: Date.now(),
      };
      if (review.action === 'cancel')
        await this.write(s, {
          ...base,
          write: {
            operation: 'cancel',
            targetId: row.id,
            key: null,
            input: { expected_revision: row.revision },
          },
        });
      else if (review.action === 'resume')
        await this.write(s, {
          ...base,
          write: {
            operation: 'resume',
            targetId: row.id,
            key: crypto.randomUUID(),
            input: { expected_revision: row.revision },
          },
        });
      else {
        const action: SavedIndexWrite = {
          ...base,
          write: {
            operation: 'activate',
            targetId: row.id,
            key: null,
            input: {
              expected_revision: row.revision,
              expected_active_id: before.activeId,
              expected_connection_revision: before.connectionRevision,
              ...(review.action !== 'activate' ? { recovery: review.action } : {}),
            },
          },
        };
        if (review.supersedes) this.ports.journal.replaceAfterReview(review.supersedes, action);
        await this.write(s, action);
      }
    });
  }
  private async write(s: Session, action: SavedIndexWrite) {
    this.check(s);
    if (!s.scope.manage) throw Error('Missing management authority');
    this.ports.journal.put(action);
    this.set(s, { unknown: action });
    const write = action.write,
      api = s.client.knowledgeIndexes;
    let row: KnowledgeIndexView;
    if (write.operation === 'create')
      row = (await api.create(s.scope.tenantId, write.input, write.key, this.options(s))).index;
    else if (write.operation === 'resume')
      row = (
        await api.resume(s.scope.tenantId, write.targetId, write.input, write.key, this.options(s))
      ).index;
    else if (write.operation === 'cancel')
      row = await api.cancel(s.scope.tenantId, write.targetId, write.input, this.options(s));
    else row = await api.activate(s.scope.tenantId, write.targetId, write.input, this.options(s));
    this.scoped(s, row);
    if (write.targetId !== null && row.id !== write.targetId)
      throw Error('Write target identity changed');
    this.ports.journal.clear(action);
    this.set(s, {
      unknown: null,
      selected: row,
      review: null,
      plan: null,
      notice:
        write.operation === 'create' || write.operation === 'resume'
          ? 'Build accepted. Inspect its recorded progress; it is not active yet.'
          : 'Index action confirmed. Review the current state.',
    });
    await this.read(s, this.state().page, this.state().filter);
  }
  async repeatSaved() {
    return this.run(true, async (s) => {
      const action = this.state().unknown;
      if (!action || !['create', 'resume'].includes(action.write.operation)) return;
      await this.write(s, action);
    });
  }
  async inspectSaved() {
    return this.run(false, async (s) => {
      const action = this.state().unknown;
      if (!action) return;
      await this.read(s, this.state().page, this.state().filter);
      if (action.write.targetId === null) {
        this.set(s, {
          notice: 'Current indexes observed. The original request remains unconfirmed.',
        });
        return;
      }
      const row = await s.client.knowledgeIndexes.get(
        s.scope.tenantId,
        action.write.targetId,
        this.options(s),
      );
      this.scoped(s, row);
      if (row.id !== action.write.targetId) throw Error('Saved target identity changed');
      this.set(s, { selected: row, review: null });
      let resolved = action.write.operation === 'cancel' && row.status === 'cancelled';
      if (
        action.write.operation === 'activate' &&
        s.scope.manage &&
        row.active &&
        row.status === 'active'
      ) {
        const before = await this.before(s);
        resolved = before.activeId === row.id && before.connectionSpaceId === row.space_id;
      }
      if (resolved) {
        this.ports.journal.clear(action);
        this.set(s, {
          unknown: null,
          notice:
            'The requested target state is now observed. This does not establish which request caused the change.',
        });
      } else
        this.set(s, {
          notice: 'Current target state observed. The original request remains unconfirmed.',
        });
    });
  }
  dispose() {
    this.alive = false;
    this.session?.abort.abort();
    this.session = null;
    this.state.set(empty());
  }
}
