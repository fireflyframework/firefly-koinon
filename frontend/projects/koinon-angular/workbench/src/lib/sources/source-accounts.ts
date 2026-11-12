// Copyright 2026 Firefly Software Foundation SPDX-License-Identifier: Apache-2.0
import { Injectable, OnDestroy, computed, effect, inject, signal } from '@angular/core';
import {
  createContentSourcesApi,
  type ReaderSelectionOutput,
  type ReaderSourceSelection,
} from '@fireflyframework/koinon-sdk/content-sources';
import {
  KoinonClientContext,
  KoinonFacade,
  organizationContextKey,
} from '@fireflyframework/koinon-angular/workbench/core';
import type {
  ConnectionPage,
  SourceAuthorization,
  SourceCapabilities,
  SourceConnection,
  SourceProvider,
} from './source-contracts';
export type ReaderMode = 'saved' | 'explicit' | 'local';
const EMPTY: ConnectionPage = { items: [], next_cursor: null, synchronization_available: false };
interface Snapshot {
  generation: number;
  key: string;
  context: ReturnType<KoinonFacade['context']>;
}
@Injectable()
export class KoinonSourceAccounts implements OnDestroy {
  private readonly f = inject(KoinonFacade);
  private readonly clients = inject(KoinonClientContext);
  readonly identity = computed(() =>
    JSON.stringify([organizationContextKey(this.f, this.clients), this.f.authRequired()]),
  );
  private readonly snapshot = signal<Snapshot | null>(null);
  private readonly rows = signal<ConnectionPage>(EMPTY);
  private readonly capability = signal<SourceCapabilities | null>(null);
  private readonly saved = signal<ReaderSelectionOutput | null>(null);
  private readonly failure = signal('');
  private readonly message = signal('');
  private readonly busy = signal(false);
  private readonly writing = signal(false);
  private readonly stale = signal(false);
  private sequence = 0;
  private generation = 0;
  private preferenceSequence = 0;
  private alive = true;
  private abort?: AbortController;
  readonly page = computed(() => (this.visible() ? this.rows() : EMPTY));
  readonly capabilities = computed(() => (this.visible() ? this.capability() : null));
  readonly preference = computed(() => (this.visible() ? this.saved() : null));
  readonly error = computed(() => (this.visible() ? this.failure() : ''));
  readonly notice = computed(() => (this.visible() ? this.message() : ''));
  readonly loading = computed(() => this.visible() && this.busy());
  readonly pending = computed(() => this.visible() && this.writing());
  readonly preferenceStale = computed(() => this.visible() && this.stale());
  constructor() {
    effect(() => {
      this.identity();
      this.f.context();
      if (!this.visible()) this.clear();
    });
  }
  private visible() {
    const snapshot = this.snapshot();
    return !!snapshot && this.current(snapshot);
  }
  private current(snapshot: Snapshot) {
    return (
      this.alive &&
      !this.f.authRequired() &&
      snapshot.generation === this.generation &&
      snapshot.key === this.identity() &&
      snapshot.context === this.f.context()
    );
  }
  private capture() {
    if (!this.visible()) this.clear();
    const snapshot = {
      key: this.identity(),
      context: this.f.context(),
      generation: this.generation,
    };
    this.snapshot.set(snapshot);
    return snapshot;
  }
  private clear() {
    ++this.generation;
    ++this.sequence;
    ++this.preferenceSequence;
    this.abort?.abort();
    this.rows.set(EMPTY);
    this.capability.set(null);
    this.saved.set(null);
    this.failure.set('');
    this.message.set('');
    this.busy.set(false);
    this.writing.set(false);
    this.stale.set(false);
    this.snapshot.set(null);
  }
  private root() {
    return '/tenants/' + encodeURIComponent(this.f.tenantId()) + '/content-sources';
  }
  private api() {
    const transport = this.clients.getTransport();
    if (!transport) throw Error('Source accounts are not available in this application.');
    return createContentSourcesApi(transport);
  }
  private fail(error: unknown, fallback: string) {
    const status = error instanceof Error && 'status' in error ? error.status : null;
    if (status === 401) {
      this.clear();
      this.f.authRequired.set(true);
      return;
    }
    if (status === 403) {
      this.clear();
      this.capture();
      this.failure.set('Access changed. Check your account and try again.');
      return;
    }
    this.failure.set(fallback);
  }
  async load(more = false) {
    if (this.loading()) return;
    const cursor = more ? this.page().next_cursor : null;
    if (more && !cursor) return;
    const snapshot = this.capture(),
      sequence = ++this.sequence;
    this.abort?.abort();
    const abort = (this.abort = new AbortController());
    if (!more) this.rows.set(EMPTY);
    this.busy.set(true);
    this.failure.set('');
    try {
      const page = await this.api().list(
        this.f.tenantId(),
        { limit: 25, ...(cursor ? { cursor } : {}) },
        { signal: abort.signal },
      );
      if (!this.current(snapshot) || sequence !== this.sequence) return;
      this.rows.set({
        ...page,
        items: more
          ? [...new Map([...this.rows().items, ...page.items].map((row) => [row.id, row])).values()]
          : page.items,
      });
    } catch (error) {
      if (this.current(snapshot) && sequence === this.sequence) {
        this.rows.set(EMPTY);
        this.fail(error, 'Could not load accounts. Try again.');
      }
    } finally {
      if (this.current(snapshot) && sequence === this.sequence) this.busy.set(false);
    }
  }
  async loadPreference() {
    const snapshot = this.capture(),
      sequence = ++this.preferenceSequence;
    try {
      const result = await this.api().readerSelection(this.f.tenantId());
      if (this.current(snapshot) && sequence === this.preferenceSequence) {
        this.saved.set(result);
        this.stale.set(false);
        this.failure.set('');
      }
    } catch (error) {
      if (this.current(snapshot) && sequence === this.preferenceSequence)
        this.fail(error, 'Could not load your source account preference. Try again.');
    }
  }
  async loadCapabilities() {
    const snapshot = this.capture();
    try {
      const result = await this.clients
        .getTransport()!
        .request<SourceCapabilities>('GET', this.root() + '/capabilities');
      if (this.current(snapshot)) this.capability.set(result);
    } catch (error) {
      if (this.current(snapshot))
        this.fail(error, 'Could not load source availability. Try again.');
    }
  }
  async begin(provider: SourceProvider): Promise<SourceAuthorization | null> {
    if (
      this.pending() ||
      !this.capabilities()?.providers.some(
        (row) => row.provider === provider && row.consent_available,
      )
    )
      return null;
    const snapshot = this.capture();
    this.writing.set(true);
    this.failure.set('');
    try {
      const result = await this.clients
        .getTransport()!
        .request<SourceAuthorization>('POST', this.root() + '/authorizations', {
          body: { provider },
        });
      return this.current(snapshot) ? result : null;
    } catch (error) {
      if (this.current(snapshot))
        this.fail(error, 'Account connection could not be started. Try again.');
      return null;
    } finally {
      if (this.current(snapshot)) this.writing.set(false);
    }
  }
  async complete(challenge: SourceAuthorization, state: string, code: string) {
    if (this.pending()) return false;
    const snapshot = this.capture();
    this.writing.set(true);
    this.failure.set('');
    try {
      await this.clients
        .getTransport()!
        .request<SourceConnection>('POST', this.root() + '/authorizations/complete', {
          body: { challenge_id: challenge.challenge_id, state, code },
        });
      if (!this.current(snapshot)) return false;
      await this.load();
      if (!this.current(snapshot)) return false;
      this.message.set('Account connected.');
      return true;
    } catch (error) {
      if (this.current(snapshot))
        this.fail(error, 'Account connection could not be completed. Try again.');
      return false;
    } finally {
      if (this.current(snapshot)) this.writing.set(false);
    }
  }
  apply(mode: ReaderMode, ids: readonly string[]): ReaderSourceSelection[] | null {
    if (mode === 'saved') return null;
    if (mode === 'local') return [];
    if (ids.length > 100 || new Set(ids).size !== ids.length)
      throw Error('Choose at most 100 source accounts.');
    const choices = ids.map((id) => {
      const row = this.page().items.find((item) => item.id === id && item.status === 'connected');
      if (!row?.account) throw Error('Selection needs to be checked again');
      return {
        provider: row.provider,
        external_tenant: row.account.tenant_id,
        connection_id: row.id,
      };
    });
    if (
      new Set(choices.map((row) => JSON.stringify([row.provider, row.external_tenant]))).size !==
      choices.length
    )
      throw Error('Choose one account for each provider and organization.');
    return choices;
  }
  async save(choices: ReaderSourceSelection[]) {
    const preference = this.preference();
    if (!preference || this.pending() || this.preferenceStale()) return false;
    const snapshot = this.capture();
    this.writing.set(true);
    this.failure.set('');
    this.message.set('');
    try {
      const result = await this.api().replaceReaderSelection(this.f.tenantId(), {
        connections: choices,
        expected_revision: preference.revision,
        operation_id: crypto.randomUUID(),
      });
      if (!this.current(snapshot)) return false;
      this.saved.set(result);
      this.message.set('Source account preference saved.');
      return true;
    } catch (error) {
      if (this.current(snapshot)) {
        this.stale.set(true);
        this.fail(
          error,
          error instanceof Error && 'status' in error && error.status === 409
            ? 'Your source account preference changed elsewhere. Reload it before saving.'
            : 'Check your current source account preference before saving again.',
        );
      }
      return false;
    } finally {
      if (this.current(snapshot)) this.writing.set(false);
    }
  }
  async disconnect(id: string) {
    const row = this.page().items.find((row) => row.id === id);
    if (!row || this.pending()) return false;
    const snapshot = this.capture();
    this.writing.set(true);
    this.failure.set('');
    try {
      const result = await this.api().disconnect(this.f.tenantId(), id, {
        expected_revision: row.revision,
      });
      if (!this.current(snapshot)) return false;
      this.rows.update((page) => ({
        ...page,
        items: page.items.map((row) => (row.id === id ? result : row)),
      }));
      this.saved.set(null);
      return true;
    } catch (error) {
      if (this.current(snapshot)) {
        this.rows.set(EMPTY);
        this.fail(error, 'Check the current account status before disconnecting again.');
      }
      return false;
    } finally {
      if (this.current(snapshot)) this.writing.set(false);
    }
  }
  ngOnDestroy() {
    this.alive = false;
    this.clear();
  }
}
