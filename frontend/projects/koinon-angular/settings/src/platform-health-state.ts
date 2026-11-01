// Copyright 2026 Firefly Software Foundation
// SPDX-License-Identifier: Apache-2.0
import {
  Injectable,
  OnDestroy,
  computed,
  effect,
  inject,
  signal,
  type WritableSignal,
} from '@angular/core';
import { KoinonClientContext, KoinonFacade } from '@fireflyframework/koinon-angular';
import {
  createPlatformHealthApi,
  type PlatformHealth,
  type SystemInformation,
} from '@fireflyframework/koinon-sdk/platform-health';
import { platformHealthAccess } from './platform-health-access';

type Report = 'health' | 'information';
interface Scoped<T> {
  key: string;
  value: T;
}

@Injectable()
export class KoinonPlatformHealthState implements OnDestroy {
  private readonly f = inject(KoinonFacade);
  private readonly clients = inject(KoinonClientContext);
  private contextIdentity: object | null = null;
  private contextRevision = 0;
  private readonly alive = signal(true);
  private lastKey = '';
  private readonly requests = new Map<Report, AbortController>();
  private expiryTimer?: ReturnType<typeof setTimeout>;
  readonly now = signal(Date.now());
  readonly key = computed(() => {
    const context = this.f.context();
    if (context !== this.contextIdentity) {
      this.contextIdentity = context;
      ++this.contextRevision;
    }
    return JSON.stringify([
      this.contextRevision,
      context?.subject,
      this.f.tenantId(),
      this.f.workspaceId(),
      this.clients.revision(),
      platformHealthAccess(context, this.f.tenantId(), this.now()),
    ]);
  });
  readonly accessError = signal('');
  readonly allowed = computed(
    () =>
      this.alive() &&
      !this.accessError() &&
      platformHealthAccess(this.f.context(), this.f.tenantId(), this.now()),
  );
  private readonly healthResult = signal<Scoped<PlatformHealth> | null>(null);
  private readonly informationResult = signal<Scoped<SystemInformation> | null>(null);
  readonly health = computed(() =>
    this.allowed() && this.healthResult()?.key === this.key() ? this.healthResult()!.value : null,
  );
  readonly information = computed(() =>
    this.allowed() && this.informationResult()?.key === this.key()
      ? this.informationResult()!.value
      : null,
  );
  readonly healthPending = signal(false);
  readonly informationPending = signal(false);
  readonly healthError = signal('');
  readonly informationError = signal('');

  constructor() {
    this.lastKey = this.key();
    effect(() => {
      const key = this.key();
      if (key !== this.lastKey) this.reset(key);
    });
    effect(() => {
      clearTimeout(this.expiryTimer);
      if (!this.alive()) return;
      const times = [
        ...(this.f.context()?.memberships.map((grant) => grant.expires_at) ?? []),
        ...(this.health()?.components.map((component) => component.expires_at) ?? []),
      ]
        .map((value) => (value ? Date.parse(value) : NaN))
        .filter((value) => value > this.now());
      clearTimeout(this.expiryTimer);
      if (times.length)
        this.expiryTimer = setTimeout(
          () => this.now.set(Date.now()),
          Math.min(Math.max(1, Math.min(...times) - Date.now() + 1), 2_147_483_647),
        );
    });
  }
  private clear() {
    for (const request of this.requests.values()) request.abort();
    this.requests.clear();
    this.healthResult.set(null);
    this.informationResult.set(null);
    this.healthPending.set(false);
    this.informationPending.set(false);
    this.healthError.set('');
    this.informationError.set('');
  }
  private reset(key: string) {
    this.lastKey = key;
    this.clear();
    this.accessError.set('');
  }
  private async read<T extends { tenant_id: string }>(
    kind: Report,
    result: WritableSignal<Scoped<T> | null>,
    pending: WritableSignal<boolean>,
    error: WritableSignal<string>,
    fallback: string,
    operation: (tenant: string, signal: AbortSignal) => Promise<T>,
  ) {
    const key = this.key();
    if (key !== this.lastKey) this.reset(key);
    if (!this.alive() || !this.allowed()) return;
    this.requests.get(kind)?.abort();
    const abort = new AbortController();
    this.requests.set(kind, abort);
    const tenant = this.f.tenantId();
    const current = () =>
      this.alive() &&
      this.allowed() &&
      key === this.key() &&
      this.requests.get(kind) === abort &&
      !abort.signal.aborted;
    result.set(null);
    error.set('');
    pending.set(true);
    try {
      const value = await operation(tenant, abort.signal);
      if (!current()) return;
      if (value.tenant_id !== tenant) {
        error.set(fallback);
        return;
      }
      this.now.set(Date.now());
      result.set({ key, value });
    } catch (failure) {
      if (!current()) return;
      const status = failure instanceof Error && 'status' in failure ? failure.status : undefined;
      if (status === 401 || status === 403) {
        if (status === 401) this.f.authRequired.set(true);
        this.clear();
        this.accessError.set('Current organization administrator access is required.');
      } else error.set(fallback);
    } finally {
      if (this.requests.get(kind) === abort) {
        pending.set(false);
        this.requests.delete(kind);
      }
    }
  }
  async loadHealth() {
    return this.read(
      'health',
      this.healthResult,
      this.healthPending,
      this.healthError,
      'Platform health could not be loaded.',
      (tenant, signal) => {
        const transport = this.clients.getTransport();
        if (!transport) throw new Error('Missing host transport');
        return createPlatformHealthApi(transport).health(tenant, { signal });
      },
    );
  }
  async loadInformation() {
    return this.read(
      'information',
      this.informationResult,
      this.informationPending,
      this.informationError,
      'System information could not be loaded.',
      (tenant, signal) => {
        const transport = this.clients.getTransport();
        if (!transport) throw new Error('Missing host transport');
        return createPlatformHealthApi(transport).systemInformation(tenant, { signal });
      },
    );
  }
  ngOnDestroy() {
    this.alive.set(false);
    clearTimeout(this.expiryTimer);
    this.clear();
  }
}
