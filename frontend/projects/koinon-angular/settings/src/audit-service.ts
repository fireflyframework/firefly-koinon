// Copyright 2026 Firefly Software Foundation
// SPDX-License-Identifier: Apache-2.0
import { Injectable, OnDestroy, computed, effect, inject, signal } from '@angular/core';
import { KoinonClientContext, KoinonFacade, KoinonI18n } from '@fireflyframework/koinon-angular';
import type { AuditEvent, AuditFilter, Page } from '@fireflyframework/koinon-sdk';
const INITIAL: AuditFilter = { page: 1, page_size: 25, sort: 'created_at', order: 'desc' };
@Injectable()
export class KoinonAuditService implements OnDestroy {
  private readonly clients = inject(KoinonClientContext);
  private readonly facade = inject(KoinonFacade);
  private readonly i18n = inject(KoinonI18n);
  readonly scope = computed(() => this.contextKey());
  private key = this.contextKey();
  private epoch = 0;
  private controller: AbortController | null = null;
  readonly page = signal<Page<AuditEvent> | null>(null);
  readonly filters = signal<AuditFilter>({ ...INITIAL });
  readonly pending = signal(false);
  readonly error = signal<Error | null>(null);
  constructor() {
    effect(() => {
      const key = this.contextKey();
      if (key !== this.key) this.reset(key);
    });
  }
  private contextKey() {
    return (
      this.facade.tenantId() +
      ':' +
      this.clients.revision() +
      ':' +
      this.i18n.preferences().time_zone
    );
  }
  private reset(key: string) {
    this.key = key;
    ++this.epoch;
    this.controller?.abort();
    this.page.set(null);
    this.filters.set({ ...INITIAL });
    this.error.set(null);
    this.pending.set(false);
  }
  async load(filter: AuditFilter = {}) {
    const key = this.contextKey();
    if (key !== this.key) this.reset(key);
    const tenant = this.facade.tenantId();
    if (!tenant) return;
    const query: AuditFilter = {
      ...this.filters(),
      ...filter,
      time_zone: this.i18n.preferences().time_zone,
    };
    for (const [name, value] of Object.entries(query))
      if (value === undefined || value === '') delete query[name];
    this.filters.set(query);
    this.controller?.abort();
    this.controller = new AbortController();
    const epoch = ++this.epoch;
    this.pending.set(true);
    this.error.set(null);
    try {
      const page = await this.clients
        .get()
        .audit.list(tenant, { query, signal: this.controller.signal });
      if (epoch === this.epoch && key === this.contextKey()) this.page.set(page);
    } catch (error) {
      if (epoch === this.epoch && key === this.contextKey()) {
        const value =
          error instanceof Error ? error : new Error('Audit activity could not be loaded.');
        if ('status' in value && value.status === 401) this.facade.authRequired.set(true);
        this.error.set(value);
      }
    } finally {
      if (epoch === this.epoch && key === this.contextKey()) this.pending.set(false);
    }
  }
  ngOnDestroy() {
    ++this.epoch;
    this.controller?.abort();
  }
}
