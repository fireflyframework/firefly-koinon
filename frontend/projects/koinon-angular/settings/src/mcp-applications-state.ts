// Copyright 2026 Firefly Software Foundation
// SPDX-License-Identifier: Apache-2.0
import { Injectable, OnDestroy, computed, effect, inject, signal } from '@angular/core';
import { KoinonClientContext, KoinonFacade } from '@fireflyframework/koinon-angular';
import type {
  McpOAuthClient,
  McpOAuthClientCredential,
  McpOAuthClientFilter,
  McpOAuthClientInput,
  McpOAuthClientPage,
  McpOAuthClientPatch,
  McpOAuthClientReadiness,
} from '@fireflyframework/koinon-sdk';

const INITIAL: McpOAuthClientFilter = {
  q: '',
  status: 'all',
  page: 1,
  page_size: 25,
  sort: 'name',
  order: 'asc',
};
const EMPTY: McpOAuthClientPage = { items: [], total: 0, page: 1, page_size: 25, pages: 0 };

@Injectable()
export class KoinonMcpApplicationsState implements OnDestroy {
  private readonly clients = inject(KoinonClientContext);
  private readonly f = inject(KoinonFacade);
  private key = this.contextKey();
  private epoch = 0;
  private alive = true;
  private listRequest = 0;
  private detailRequest = 0;
  private readinessRequest = 0;
  private reloadRequest = 0;
  private listAbort?: AbortController;
  private detailAbort?: AbortController;
  private readinessAbort?: AbortController;
  readonly identity = signal(0);
  readonly readiness = signal<McpOAuthClientReadiness | null>(null);
  readonly page = signal<McpOAuthClientPage>({ ...EMPTY, items: [] });
  readonly filter = signal<McpOAuthClientFilter>({ ...INITIAL });
  readonly detail = signal<McpOAuthClient | null>(null);
  readonly secret = signal<McpOAuthClientCredential | null>(null);
  readonly loading = signal(false);
  readonly loaded = signal(false);
  readonly detailLoading = signal(false);
  readonly readinessLoading = signal(false);
  readonly saving = signal(false);
  readonly stale = signal(false);
  readonly error = signal('');
  readonly notice = signal('');
  readonly allowed = computed(
    () => !!this.f.tenantId() && this.f.tenantPermissions().has('identity:manage'),
  );
  readonly canWrite = computed(
    () =>
      this.allowed() &&
      this.readiness() !== null &&
      !this.saving() &&
      !this.stale() &&
      !this.secret(),
  );

  constructor() {
    effect(() => this.syncIdentity());
  }

  private contextKey() {
    return JSON.stringify([
      this.f.tenantId(),
      this.f.context()?.subject ?? '',
      this.clients.revision(),
      this.f.tenantPermissions().has('identity:manage'),
    ]);
  }
  private current(epoch: number) {
    return this.alive && epoch === this.epoch && this.key === this.contextKey();
  }
  private syncIdentity() {
    const key = this.contextKey();
    if (!this.alive || key === this.key) return;
    this.key = key;
    this.identity.set(++this.epoch);
    this.listAbort?.abort();
    this.detailAbort?.abort();
    this.readinessAbort?.abort();
    ++this.reloadRequest;
    this.readiness.set(null);
    this.page.set({ ...EMPTY, items: [] });
    this.detail.set(null);
    this.secret.set(null);
    this.filter.set({ ...INITIAL });
    this.loading.set(false);
    this.loaded.set(false);
    this.detailLoading.set(false);
    this.readinessLoading.set(false);
    this.saving.set(false);
    this.stale.set(false);
    this.error.set('');
    this.notice.set('');
  }
  private failure(error: unknown, fallback: string) {
    if (error instanceof Error && 'status' in error && error.status === 401)
      this.f.authRequired.set(true);
    this.error.set(fallback);
  }
  async loadReadiness(): Promise<McpOAuthClientReadiness | null> {
    this.syncIdentity();
    if (!this.alive || !this.allowed()) return null;
    const epoch = this.epoch,
      request = ++this.readinessRequest;
    this.readinessAbort?.abort();
    const abort = (this.readinessAbort = new AbortController());
    this.readinessLoading.set(true);
    this.readiness.set(null);
    this.error.set('');
    try {
      const result = await this.clients
        .get()
        .mcpOAuthClients.readiness(this.f.tenantId(), { signal: abort.signal });
      if (!this.current(epoch) || request !== this.readinessRequest) return null;
      this.readiness.set(result);
      return result;
    } catch (error) {
      if (this.current(epoch) && request === this.readinessRequest)
        this.failure(error, 'Application setup could not be checked. Try again.');
      return null;
    } finally {
      if (this.current(epoch) && request === this.readinessRequest)
        this.readinessLoading.set(false);
    }
  }
  async load(patch: McpOAuthClientFilter = {}): Promise<McpOAuthClientPage | null> {
    this.syncIdentity();
    if (!this.alive || !this.allowed() || this.saving() || this.secret()) return null;
    const query = { ...this.filter(), ...patch };
    query.q = (query.q ?? '').trim().slice(0, 255);
    this.filter.set(query);
    this.closeDetail();
    this.listAbort?.abort();
    const epoch = this.epoch,
      request = ++this.listRequest;
    const abort = (this.listAbort = new AbortController());
    this.loading.set(true);
    this.loaded.set(false);
    this.page.set({ ...EMPTY, items: [] });
    this.error.set('');
    this.notice.set('');
    try {
      const result = await this.clients
        .get()
        .mcpOAuthClients.list(this.f.tenantId(), { query, signal: abort.signal });
      if (!this.current(epoch) || request !== this.listRequest) return null;
      if (result.items.some((row) => row.tenant_id !== this.f.tenantId()))
        throw new Error('Organization mismatch');
      this.page.set(result);
      this.loaded.set(true);
      return result;
    } catch (error) {
      if (this.current(epoch) && request === this.listRequest)
        this.failure(error, 'Applications could not be loaded. Try again.');
      return null;
    } finally {
      if (this.current(epoch) && request === this.listRequest) this.loading.set(false);
    }
  }
  async reload(): Promise<boolean> {
    this.syncIdentity();
    if (this.saving() || this.secret()) return false;
    const epoch = this.epoch,
      request = ++this.reloadRequest;
    const [readiness, page] = await Promise.all([this.loadReadiness(), this.load()]);
    if (!this.current(epoch) || request !== this.reloadRequest || !readiness || !page) return false;
    this.stale.set(false);
    return true;
  }
  async open(id: string): Promise<McpOAuthClient | null> {
    this.syncIdentity();
    if (
      !this.alive ||
      !this.allowed() ||
      this.saving() ||
      !this.page().items.some((row) => row.id === id)
    )
      return null;
    this.closeDetail();
    const epoch = this.epoch,
      request = ++this.detailRequest;
    const abort = (this.detailAbort = new AbortController());
    this.detailLoading.set(true);
    this.error.set('');
    try {
      const result = await this.clients
        .get()
        .mcpOAuthClients.get(this.f.tenantId(), id, { signal: abort.signal });
      if (!this.current(epoch) || request !== this.detailRequest) return null;
      if (result.id !== id || result.tenant_id !== this.f.tenantId())
        throw new Error('Application mismatch');
      this.detail.set(result);
      return result;
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
    this.dismissSecret();
  }
  dismissSecret() {
    this.secret.set(null);
  }

  private writable(identity: number, id?: string, revision?: number) {
    this.syncIdentity();
    if (!this.alive || identity !== this.identity() || !this.canWrite()) return false;
    if (!id) return true;
    const row = this.detail();
    return row?.id === id && row.tenant_id === this.f.tenantId() && row.revision === revision;
  }
  private async write(
    action: () => Promise<McpOAuthClient | McpOAuthClientCredential>,
    creating: boolean,
    expected?: McpOAuthClient,
  ): Promise<McpOAuthClient | null> {
    const epoch = this.epoch,
      tenant = this.f.tenantId();
    this.saving.set(true);
    this.error.set('');
    this.notice.set('');
    this.dismissSecret();
    this.listAbort?.abort();
    this.detailAbort?.abort();
    ++this.listRequest;
    ++this.detailRequest;
    this.loading.set(false);
    this.detailLoading.set(false);
    try {
      const result = await action();
      if (!this.current(epoch)) return null;
      const row = 'client' in result ? result.client : result;
      if (row.tenant_id !== tenant) throw new Error('Organization mismatch');
      if (
        expected &&
        (row.id !== expected.id ||
          row.client_id !== expected.client_id ||
          row.client_type !== expected.client_type ||
          row.revision !== expected.revision + 1)
      )
        throw new Error('Application response mismatch');
      this.detail.set(row);
      this.loaded.set(false);
      this.page.set({ ...EMPTY, items: [] });
      if ('client' in result && result.client_secret) this.secret.set(result);
      this.notice.set(
        creating
          ? 'Application created. Copy its secret now if one was issued. It cannot be shown again.'
          : 'Application updated. Existing connections have been revoked. Users must connect again.',
      );
      return row;
    } catch (error) {
      if (this.current(epoch)) {
        const status = error instanceof Error && 'status' in error ? error.status : null;
        const uncertain = typeof status !== 'number' || status >= 500;
        if (uncertain || status === 409 || status === 401) {
          this.stale.set(true);
          this.closeDetail();
        }
        this.failure(
          error,
          status === 409
            ? 'This application changed. Reload before making another change.'
            : uncertain
              ? 'The result could not be confirmed. Reload to check the application before trying again. A secret from a lost response cannot be recovered.'
              : 'The application could not be changed. Review your access and application settings.',
        );
      }
      return null;
    } finally {
      if (this.current(epoch)) this.saving.set(false);
    }
  }
  async create(input: McpOAuthClientInput, identity: number): Promise<McpOAuthClient | null> {
    if (!this.writable(identity)) return null;
    const client = this.clients.get(),
      tenant = this.f.tenantId(),
      snapshot = structuredClone(input);
    return this.write(() => client.mcpOAuthClients.create(tenant, snapshot), true);
  }
  async update(
    id: string,
    patch: McpOAuthClientPatch,
    identity: number,
  ): Promise<McpOAuthClient | null> {
    if (!this.writable(identity, id, patch.expected_revision)) return null;
    const client = this.clients.get(),
      tenant = this.f.tenantId(),
      snapshot = structuredClone(patch);
    return this.write(
      () => client.mcpOAuthClients.update(tenant, id, snapshot),
      false,
      this.detail()!,
    );
  }
  async disable(id: string, identity: number, revision: number): Promise<McpOAuthClient | null> {
    return this.update(id, { expected_revision: revision, enabled: false }, identity);
  }
  async rotateSecret(
    id: string,
    identity: number,
    revision: number,
  ): Promise<McpOAuthClient | null> {
    if (!this.writable(identity, id, revision) || this.detail()?.client_type !== 'confidential')
      return null;
    const client = this.clients.get(),
      tenant = this.f.tenantId();
    return this.write(
      () => client.mcpOAuthClients.rotateSecret(tenant, id, { expected_revision: revision }),
      false,
      this.detail()!,
    );
  }
  ngOnDestroy() {
    this.alive = false;
    this.identity.set(++this.epoch);
    this.listAbort?.abort();
    this.detailAbort?.abort();
    this.readinessAbort?.abort();
    this.secret.set(null);
    this.detail.set(null);
    this.readiness.set(null);
  }
}
