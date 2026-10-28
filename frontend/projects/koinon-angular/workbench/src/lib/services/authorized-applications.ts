// Copyright 2026 Firefly Software Foundation SPDX-License-Identifier: Apache-2.0
import { Injectable, OnDestroy, effect, inject, signal } from '@angular/core';
import type {
  AuthorizedApplication,
  AuthorizedApplicationFilter,
  Page,
} from '@fireflyframework/koinon-sdk';
import { KoinonClientContext } from './client-context';
import { KoinonFacade } from '../koinon-facade';

const INITIAL: AuthorizedApplicationFilter = {
  q: '',
  status: 'all',
  page: 1,
  page_size: 25,
  sort: 'connected_at',
  order: 'desc',
};
export function applicationLifecycle(
  row: AuthorizedApplication,
  now = Date.now(),
): AuthorizedApplication['status'] {
  return row.status === 'active' && Date.parse(row.expires_at) <= now ? 'expired' : row.status;
}

@Injectable()
export class KoinonAuthorizedApplications implements OnDestroy {
  private readonly clients = inject(KoinonClientContext);
  private readonly f = inject(KoinonFacade);
  private key = this.contextKey();
  private epoch = 0;
  private listRequest = 0;
  private detailRequest = 0;
  private alive = true;
  private listAbort?: AbortController;
  private detailAbort?: AbortController;
  readonly identity = signal(0);
  readonly page = signal<Page<AuthorizedApplication>>({ items: [] });
  readonly filter = signal<AuthorizedApplicationFilter>({ ...INITIAL });
  readonly detail = signal<AuthorizedApplication | null>(null);
  readonly loading = signal(false);
  readonly loaded = signal(false);
  readonly detailLoading = signal(false);
  readonly revoking = signal('');
  readonly error = signal('');
  readonly notice = signal('');

  constructor() {
    effect(() => this.syncIdentity());
  }
  private contextKey() {
    return (this.f.context()?.subject ?? '') + ':' + this.clients.revision();
  }
  private current(epoch: number) {
    return this.alive && epoch === this.epoch && this.key === this.contextKey();
  }
  private syncIdentity() {
    const key = this.contextKey();
    if (this.key === key) return;
    this.key = key;
    ++this.epoch;
    this.identity.set(this.epoch);
    this.listAbort?.abort();
    this.detailAbort?.abort();
    this.page.set({ items: [] });
    this.detail.set(null);
    this.filter.set({ ...INITIAL });
    this.loading.set(false);
    this.loaded.set(false);
    this.detailLoading.set(false);
    this.revoking.set('');
    this.error.set('');
    this.notice.set('');
  }
  private failure(error: unknown, message: string) {
    if (error instanceof Error && 'status' in error && error.status === 401)
      this.f.authRequired.set(true);
    this.error.set(message);
  }
  async load(patch: AuthorizedApplicationFilter = {}): Promise<Page<AuthorizedApplication> | null> {
    this.syncIdentity();
    const query = { ...this.filter(), ...patch };
    query.q = (query.q || '').trim().slice(0, 255);
    this.filter.set(query);
    this.page.set({ items: [] });
    this.detail.set(null);
    this.listAbort?.abort();
    this.detailAbort?.abort();
    ++this.detailRequest;
    const abort = (this.listAbort = new AbortController()),
      epoch = this.epoch,
      request = ++this.listRequest;
    this.loading.set(true);
    this.loaded.set(false);
    this.error.set('');
    this.notice.set('');
    this.detailLoading.set(false);
    try {
      const page = await this.clients
        .get()
        .authorizedApplications.list({ query, signal: abort.signal });
      if (!this.current(epoch) || request !== this.listRequest) return null;
      this.page.set(page);
      this.loaded.set(true);
      return page;
    } catch (error) {
      if (this.current(epoch) && request === this.listRequest)
        this.failure(error, 'Authorized applications could not be loaded. Try again.');
      return null;
    } finally {
      if (this.current(epoch) && request === this.listRequest) this.loading.set(false);
    }
  }
  async open(id: string): Promise<AuthorizedApplication | null> {
    this.syncIdentity();
    if (!this.page().items.some((row) => row.id === id)) return null;
    return this.readDetail(id);
  }
  private async readDetail(id: string): Promise<AuthorizedApplication | null> {
    const epoch = this.epoch,
      request = ++this.detailRequest;
    this.detailAbort?.abort();
    const abort = (this.detailAbort = new AbortController());
    this.detail.set(null);
    this.detailLoading.set(true);
    this.error.set('');
    try {
      const row = await this.clients.get().authorizedApplications.get(id, { signal: abort.signal });
      if (!this.current(epoch) || request !== this.detailRequest) return null;
      this.detail.set(row);
      return row;
    } catch (error) {
      if (this.current(epoch) && request === this.detailRequest)
        this.failure(error, 'This application could not be opened. Try again.');
      return null;
    } finally {
      if (this.current(epoch) && request === this.detailRequest) this.detailLoading.set(false);
    }
  }
  closeDetail() {
    ++this.detailRequest;
    this.detailAbort?.abort();
    this.detail.set(null);
    this.detailLoading.set(false);
  }
  async revoke(id: string): Promise<boolean> {
    this.syncIdentity();
    if (
      this.revoking() ||
      !this.page().items.some((row) => row.id === id && row.status === 'active')
    )
      return false;
    const epoch = this.epoch,
      client = this.clients.get(),
      hadDetail = this.detail()?.id === id;
    this.revoking.set(id);
    this.error.set('');
    this.notice.set('');
    try {
      await client.authorizedApplications.revoke(id);
      if (!this.current(epoch)) return false;
      const page = await this.load();
      if (!this.current(epoch)) return false;
      if (page && page.items.length === 0 && (page.page ?? 1) > 1)
        await this.load({ page: (page.page ?? 2) - 1 });
      if (!this.current(epoch)) return false;
      if (hadDetail) await this.readDetail(id);
      if (!this.current(epoch)) return false;
      this.notice.set('Application access revoked.');
      return true;
    } catch (error) {
      if (this.current(epoch))
        this.failure(
          error,
          'This connection could not be revoked. Review its current status and try again.',
        );
      return false;
    } finally {
      if (this.current(epoch)) this.revoking.set('');
    }
  }
  ngOnDestroy() {
    this.alive = false;
    ++this.epoch;
    this.listAbort?.abort();
    this.detailAbort?.abort();
  }
}
