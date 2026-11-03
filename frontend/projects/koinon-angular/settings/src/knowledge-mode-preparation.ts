// Copyright 2026 Firefly Software Foundation
// SPDX-License-Identifier: Apache-2.0
import { Injectable, OnDestroy, computed, effect, inject, signal } from '@angular/core';
import { KoinonClientContext, KoinonFacade } from '@fireflyframework/koinon-angular';
import type {
  KnowledgeModeTargetView,
  KnowledgeModeRecoveryReceipt,
  KnowledgeModeTransitionView,
  OrganizationKnowledgeSettingsInput,
} from '@fireflyframework/koinon-sdk';

@Injectable()
export class KnowledgeModePreparation implements OnDestroy {
  private readonly clients = inject(KoinonClientContext);
  private readonly f = inject(KoinonFacade);
  private readonly result = signal<{
    key: string;
    value: KnowledgeModeTransitionView | null;
  } | null>(null);
  private readonly rows = signal<KnowledgeModeTargetView[]>([]);
  private readonly recoveryRows = signal<KnowledgeModeRecoveryReceipt[]>([]);
  private timer?: ReturnType<typeof setTimeout>;
  private alive = true;
  private request?: { payload: string; key: string };
  private generation = 0;
  readonly key = computed(() =>
    JSON.stringify([
      this.f.tenantId(),
      this.f.context()?.subject,
      this.clients.revision(),
      [...this.f.tenantPermissions()].sort(),
    ]),
  );
  readonly value = computed(() =>
    this.result()?.key === this.key() ? this.result()!.value : null,
  );
  readonly targets = computed(() => (this.result()?.key === this.key() ? this.rows() : []));
  readonly recoveries = computed(() =>
    this.result()?.key === this.key() ? this.recoveryRows() : [],
  );
  readonly recoveryCursor = signal<string | null>(null);
  readonly cursor = signal<string | null>(null);
  readonly busy = signal(false);
  readonly error = signal('');
  readonly unknown = signal(false);
  readonly reviewRetry = signal(false);
  readonly reviewRecovery = signal<{
    receipt: KnowledgeModeRecoveryReceipt;
    action: 'finish' | 'restore_previous';
  } | null>(null);
  readonly active = computed(() =>
    ['queued', 'running', 'failed'].includes(this.value()?.status ?? ''),
  );
  readonly locked = computed(
    () =>
      this.active() ||
      (this.value()?.pending_index_recoveries ?? 0) > 0 ||
      this.busy() ||
      this.unknown(),
  );
  readonly permitted = computed(() => this.f.tenantPermissions().has('settings:write'));
  constructor() {
    effect(() => {
      this.key();
      this.reset();
    });
  }
  reset() {
    ++this.generation;
    clearTimeout(this.timer);
    this.result.set(null);
    this.rows.set([]);
    this.recoveryRows.set([]);
    this.recoveryCursor.set(null);
    this.cursor.set(null);
    this.busy.set(false);
    this.error.set('');
    this.unknown.set(false);
    this.reviewRetry.set(false);
    this.reviewRecovery.set(null);
    this.request = undefined;
  }
  private current(key: string, generation: number) {
    return this.alive && key === this.key() && generation === this.generation;
  }
  private fail(error: unknown) {
    if (error instanceof Error && 'status' in error && error.status === 401)
      this.f.authRequired.set(true);
    if (error instanceof Error && 'status' in error && [401, 403].includes(Number(error.status))) {
      this.result.set(null);
      this.rows.set([]);
      this.recoveryRows.set([]);
      this.recoveryCursor.set(null);
      this.cursor.set(null);
      clearTimeout(this.timer);
    }
    this.error.set(
      error instanceof Error
        ? error.message
        : 'Preparation status could not be loaded. Refresh to try again.',
    );
  }
  private schedule() {
    clearTimeout(this.timer);
    if (['queued', 'running'].includes(this.value()?.status ?? ''))
      this.timer = setTimeout(() => {
        void this.load();
      }, 3000);
  }
  async load() {
    if (!this.permitted() || this.busy()) return;
    const key = this.key(),
      generation = this.generation,
      tenant = this.f.tenantId();
    this.busy.set(true);
    this.error.set('');
    try {
      const current = await this.clients.get().knowledgeModes.current(tenant);
      if (!this.current(key, generation)) return;
      const previous = this.value();
      this.result.set({ key, value: current.transition });
      if (
        current.transition &&
        (!previous ||
          current.transition.id !== previous.id ||
          current.transition.revision !== previous.revision)
      ) {
        const page = await this.clients
          .get()
          .knowledgeModes.targets(tenant, current.transition.id, { limit: 50 });
        if (!this.current(key, generation)) return;
        this.rows.set(page.items);
        this.cursor.set(page.next_cursor);
      }
      if (current.transition) {
        const page = await this.clients
          .get()
          .knowledgeModes.recoveries(tenant, current.transition.id, { limit: 50 });
        if (!this.current(key, generation)) return;
        this.recoveryRows.set(page.items);
        this.recoveryCursor.set(page.next_cursor);
        this.unknown.set(false);
      }
    } catch (error) {
      if (this.current(key, generation)) this.fail(error);
    } finally {
      if (this.current(key, generation)) {
        this.busy.set(false);
        this.schedule();
      }
    }
  }
  async more() {
    const row = this.value(),
      after = this.cursor();
    if (!row || !after || this.busy()) return;
    const key = this.key(),
      generation = this.generation;
    this.busy.set(true);
    try {
      const page = await this.clients
        .get()
        .knowledgeModes.targets(this.f.tenantId(), row.id, { after, limit: 50 });
      if (!this.current(key, generation) || this.value()?.id !== row.id) return;
      if (page.next_cursor === after)
        throw new Error('Preparation pagination did not advance. Refresh the status.');
      this.rows.update((rows) => [
        ...rows.filter((item) => !page.items.some((next) => next.id === item.id)),
        ...page.items,
      ]);
      this.cursor.set(page.next_cursor);
    } catch (error) {
      if (this.current(key, generation)) this.fail(error);
    } finally {
      if (this.current(key, generation)) this.busy.set(false);
    }
  }
  async create(input: OrganizationKnowledgeSettingsInput) {
    if (!this.permitted() || this.busy() || this.active()) return false;
    const payload = JSON.stringify(input);
    if (this.request && this.request.payload !== payload && this.unknown()) return false;
    this.request ??= { payload, key: crypto.randomUUID() };
    if (this.request.payload !== payload) this.request = { payload, key: crypto.randomUUID() };
    const key = this.key(),
      generation = this.generation;
    this.busy.set(true);
    this.error.set('');
    try {
      const value = await this.clients
        .get()
        .knowledgeModes.create(this.f.tenantId(), input, this.request.key);
      if (!this.current(key, generation)) return false;
      this.result.set({ key, value });
      this.rows.set([]);
      this.recoveryRows.set([]);
      this.recoveryCursor.set(null);
      this.cursor.set(null);
      this.unknown.set(false);
      return true;
    } catch (error) {
      if (this.current(key, generation)) {
        this.unknown.set(
          !(
            error instanceof Error &&
            'status' in error &&
            Number(error.status) >= 400 &&
            Number(error.status) < 500
          ),
        );
        this.fail(error);
      }
      return false;
    } finally {
      if (this.current(key, generation)) {
        this.busy.set(false);
        this.schedule();
      }
    }
  }
  async repeatRequest() {
    if (this.request && this.unknown())
      await this.create(JSON.parse(this.request.payload) as OrganizationKnowledgeSettingsInput);
  }
  async act(action: 'cancel' | 'retry') {
    const row = this.value();
    if (!row || !this.permitted() || this.busy() || (action === 'retry' && !this.reviewRetry()))
      return;
    const key = this.key(),
      generation = this.generation;
    this.busy.set(true);
    this.error.set('');
    try {
      const value = await this.clients
        .get()
        .knowledgeModes[action](this.f.tenantId(), row.id, { expected_revision: row.revision });
      if (!this.current(key, generation)) return;
      this.result.set({ key, value });
      this.reviewRetry.set(false);
      const [page, recoveries] = await Promise.all([
        this.clients.get().knowledgeModes.targets(this.f.tenantId(), row.id, { limit: 50 }),
        this.clients.get().knowledgeModes.recoveries(this.f.tenantId(), row.id, { limit: 50 }),
      ]);
      if (!this.current(key, generation)) return;
      this.rows.set(page.items);
      this.cursor.set(page.next_cursor);
      this.recoveryRows.set(recoveries.items);
      this.recoveryCursor.set(recoveries.next_cursor);
    } catch (error) {
      if (this.current(key, generation)) this.fail(error);
    } finally {
      if (this.current(key, generation)) {
        this.busy.set(false);
        this.schedule();
      }
    }
  }
  async moreRecoveries() {
    const row = this.value(),
      after = this.recoveryCursor();
    if (!row || !after || this.busy()) return;
    const key = this.key(),
      generation = this.generation;
    this.busy.set(true);
    try {
      const page = await this.clients
        .get()
        .knowledgeModes.recoveries(this.f.tenantId(), row.id, { after, limit: 50 });
      if (!this.current(key, generation) || this.value()?.id !== row.id) return;
      if (page.next_cursor === after)
        throw new Error('Recovery pagination did not advance. Refresh the status.');
      this.recoveryRows.update((rows) => [
        ...rows.filter((item) => !page.items.some((next) => next.receipt_id === item.receipt_id)),
        ...page.items,
      ]);
      this.recoveryCursor.set(page.next_cursor);
    } catch (error) {
      if (this.current(key, generation)) this.fail(error);
    } finally {
      if (this.current(key, generation)) this.busy.set(false);
    }
  }
  async recover() {
    const selected = this.reviewRecovery(),
      recovery = selected?.receipt;
    if (
      !selected ||
      !this.permitted() ||
      this.result()?.key !== this.key() ||
      !recovery ||
      !recovery.expected_revision ||
      !recovery.actions.includes(selected.action) ||
      this.busy()
    )
      return;
    const key = this.key(),
      generation = this.generation;
    this.busy.set(true);
    this.error.set('');
    try {
      await this.clients.get().knowledgeIndexes.activate(this.f.tenantId(), recovery.index_id, {
        expected_revision: recovery.expected_revision,
        expected_active_id: recovery.expected_active_id ?? null,
        expected_connection_revision: recovery.expected_connection_revision ?? null,
        recovery: selected.action,
      });
      if (!this.current(key, generation)) return;
      this.reviewRecovery.set(null);
      this.result.set(null);
    } catch (error) {
      if (this.current(key, generation)) this.fail(error);
    } finally {
      if (this.current(key, generation)) this.busy.set(false);
    }
    if (this.current(key, generation) && !this.error()) await this.load();
  }
  ngOnDestroy() {
    this.alive = false;
    this.reset();
  }
}
