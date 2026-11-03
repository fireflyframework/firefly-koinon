// Copyright 2026 Firefly Software Foundation
// SPDX-License-Identifier: Apache-2.0
import { signal } from '@angular/core';
import { UploadObservationLoop } from './upload-observation-loop';
import { createAvailabilityApi } from '@fireflyframework/koinon-sdk/availability';
import type { AssetAvailability } from '@fireflyframework/koinon-sdk/availability';
import type { KoinonFacade } from '@fireflyframework/koinon-angular/workbench/core';
import type { KoinonClientContext } from '@fireflyframework/koinon-angular/workbench/core';

export class AvailabilitySession {
  readonly values = signal<Record<string, AssetAvailability>>({});
  private stamp = '';
  private identity: object | null = null;
  private epoch = 0;
  readonly observedAt = signal('');
  private refs = new Map<string, number>();
  private scheduled = false;
  private request?: AbortController;
  readonly stale = signal(false);
  private denied = false;
  private pending = false;
  private listening = false;
  private readonly visible = () => typeof document === 'undefined' || document.visibilityState !== 'hidden';
  private readonly reenter = () => {
    this.sync();
    if (this.visible()) this.schedule();
    this.polling.update();
  };
  private readonly polling = new UploadObservationLoop({
    active: () => !!this.refs.size && !this.request && !this.denied && !!this.clients.getTransport()
      && !!this.facade.tenantId() && !!this.facade.context()?.subject,
    visible: this.visible,
    interval: () => Object.values(this.values()).some(value =>
      ['queued', 'processing', 'indexing'].includes(value.phase ?? '') ||
      value.search?.state === 'pending' || value.query?.state === 'pending') ? 5000 : 30000,
    read: () => this.load(),
  });
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
    this.denied = false;
    this.stale.set(false);
    this.polling.reset();
    this.schedule();
  }
  watch(id: string) {
    if (!this.listening && typeof document !== 'undefined') {
      document.addEventListener('visibilitychange', this.reenter);
      window.addEventListener('focus', this.reenter);
      this.listening = true;
    }
    this.refs.set(id, (this.refs.get(id) ?? 0) + 1);
    this.schedule();
    return () => {
      const count = (this.refs.get(id) ?? 1) - 1;
      if (count) this.refs.set(id, count);
      else this.refs.delete(id);
      if (!this.refs.size) {
        this.stop();
        this.values.set({});
        this.stale.set(false);
        this.observedAt.set('');
        if (this.listening) {
          document.removeEventListener('visibilitychange', this.reenter);
          window.removeEventListener('focus', this.reenter);
          this.listening = false;
        }
      }
    };
  }
  refresh() {
    this.schedule();
  }
  private stop() {
    this.request?.abort();
    this.request = undefined;
    this.pending = false;
    this.polling.reset();
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
    if (!transport || !tenant || !this.facade.context()?.subject || !this.refs.size || this.denied) return true;
    if (this.request) { this.pending = true; return true; }
    this.pending = false;
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
        if (!current()) return true;
        const result = await createAvailabilityApi(transport).observe(
          tenant,
          {
            asset_ids: ids.slice(offset, offset + 100),
            ...(this.facade.workspaceId() ? { workspace_id: this.facade.workspaceId() } : {}),
          },
          { signal: controller.signal },
        );
        if (!current()) return true;
        for (const id of ids.slice(offset, offset + 100)) {
          if (result.items[id]) combined[id] = result.items[id];
        }
        observedAt = result.observed_at;
      }
      if (!current()) return true;
      this.stamp = stamp;
      this.values.set(combined);
      this.observedAt.set(observedAt);
      this.stale.set(false);
      return true;
    } catch (error) {
      if (!current()) return true;
      const status = error instanceof Error && 'status' in error ? error.status : null;
      if (status === 401 || status === 403) {
        this.denied = true;
        this.values.set({});
        this.observedAt.set('');
        this.stale.set(false);
      } else this.stale.set(true);
      return false;
    } finally {
      if (this.request === controller) {
        this.request = undefined;
        if (this.pending) this.schedule();
        this.polling.update();
      }
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
