// Copyright 2026 Firefly Software Foundation
// SPDX-License-Identifier: Apache-2.0
import { signal } from '@angular/core';
import { createAvailabilityApi } from '@fireflyframework/koinon-sdk/availability';
import type { AssetAvailability } from '@fireflyframework/koinon-sdk/availability';
import type { KoinonFacade } from '../koinon-facade';
import type { KoinonClientContext } from './client-context';

export class AvailabilitySession {
  readonly values = signal<Record<string, AssetAvailability>>({});
  private stamp = '';
  private identity: object | null = null;
  private epoch = 0;
  readonly observedAt = signal('');
  private refs = new Map<string, number>();
  private scheduled = false;
  private request?: AbortController;
  private timer?: ReturnType<typeof setTimeout>;
  private polls = 0;
  constructor(
    private facade: KoinonFacade,
    private clients: KoinonClientContext,
  ) {}
  key() {
    const context = this.facade.context();
    if (context !== this.identity) {
      this.identity = context;
      ++this.epoch;
    }
    return JSON.stringify([
      this.epoch,
      this.clients.revision(),
      this.facade.context()?.subject,
      this.facade.tenantId(),
      this.facade.workspaceId(),
      this.facade.projectId(),
      this.facade.parentId(),
    ]);
  }
  get(id: string) {
    return this.stamp === this.key() && this.clients.getTransport() ? this.values()[id] : undefined;
  }
  sync() {
    const key = this.key();
    if (key === this.stamp) return;
    this.stop();
    this.stamp = key;
    this.values.set({});
    this.observedAt.set('');
    this.polls = 0;
    this.schedule();
  }
  watch(id: string) {
    this.refs.set(id, (this.refs.get(id) ?? 0) + 1);
    this.schedule();
    return () => {
      const count = (this.refs.get(id) ?? 1) - 1;
      if (count) this.refs.set(id, count);
      else this.refs.delete(id);
      if (!this.refs.size) {
        this.stop();
        this.values.set({});
      }
    };
  }
  refresh() {
    this.polls = 0;
    this.schedule();
  }
  private stop() {
    this.request?.abort();
    clearTimeout(this.timer);
  }
  private schedule() {
    if (this.scheduled) return;
    this.scheduled = true;
    queueMicrotask(() => {
      this.scheduled = false;
      void this.load();
    });
  }
  private async load() {
    const transport = this.clients.getTransport();
    const tenant = this.facade.tenantId();
    if (!transport || !tenant || !this.facade.context()?.subject || !this.refs.size) return;
    this.request?.abort();
    clearTimeout(this.timer);
    const controller = new AbortController();
    this.request = controller;
    const stamp = this.key();
    const current = () =>
      this.request === controller &&
      !controller.signal.aborted &&
      this.key() === stamp &&
      this.clients.getTransport() === transport;
    try {
      const ids = [...this.refs.keys()];
      const combined: Record<string, AssetAvailability> = {};
      let observedAt = '';
      for (let offset = 0; offset < ids.length; offset += 100) {
        const result = await createAvailabilityApi(transport).observe(
          tenant,
          {
            asset_ids: ids.slice(offset, offset + 100),
            ...(this.facade.workspaceId() ? { workspace_id: this.facade.workspaceId() } : {}),
          },
          { signal: controller.signal },
        );
        Object.assign(combined, result.items);
        observedAt = result.observed_at;
      }
      if (!current()) return;
      this.stamp = stamp;
      this.values.set(combined);
      this.observedAt.set(observedAt);
      if (
        ++this.polls < 12 &&
        Object.values(combined).some((value) =>
          ['queued', 'processing', 'indexing'].includes(value.phase ?? 'unknown'),
        )
      )
        this.timer = setTimeout(() => {
          void this.load();
        }, 5000);
    } catch {
      if (current()) this.values.set({});
    }
  }
}

// One bounded request group per embedded workbench; references end with the last visible indicator.
const sessions = new WeakMap<KoinonFacade, AvailabilitySession>();
export function availabilitySession(facade: KoinonFacade, clients: KoinonClientContext) {
  let value = sessions.get(facade);
  if (!value) {
    value = new AvailabilitySession(facade, clients);
    sessions.set(facade, value);
  }
  return value;
}
