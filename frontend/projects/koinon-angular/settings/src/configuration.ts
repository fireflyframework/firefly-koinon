// Copyright 2026 Firefly Software Foundation SPDX-License-Identifier: Apache-2.0
import { Injectable, OnDestroy, effect, inject, signal } from '@angular/core';
import { KoinonFacade, KoinonClientContext } from '@fireflyframework/koinon-angular';
import type {
  Configuration,
  ProviderInput,
  AgentConfiguration,
  AgentInput,
  ValidationResult,
  Page,
} from '@fireflyframework/koinon-sdk';
@Injectable()
export class KoinonConfiguration implements OnDestroy {
  readonly f = inject(KoinonFacade);
  private readonly clients = inject(KoinonClientContext);
  private epoch = 0;
  private key = '';
  readonly configuration = signal<Configuration | null>(null);
  readonly agents = signal<Page<AgentConfiguration>>({ items: [] });
  readonly agentFilter = signal({ page: 1, page_size: 25, q: '', status: '' });
  readonly pending = signal(false);
  readonly error = signal('');
  readonly notice = signal('');
  readonly validation = signal<ValidationResult | null>(null);
  constructor() {
    this.key = this.contextKey();
    effect(() => {
      const key = this.contextKey();
      if (key !== this.key) {
        this.key = key;
        ++this.epoch;
        this.configuration.set(null);
        this.agents.set({ items: [] });
        this.validation.set(null);
        this.error.set('');
        this.notice.set('');
        this.pending.set(false);
      }
    });
  }
  private contextKey() {
    return this.f.tenantId() + ':' + this.clients.revision();
  }
  private fail(error: unknown) {
    if (error instanceof Error && 'status' in error && error.status === 401)
      this.f.authRequired.set(true);
    this.error.set(error instanceof Error ? error.message : 'Settings could not be loaded.');
  }
  private async perform<T>(
    operation: () => Promise<T>,
    apply: ((value: T) => void) | undefined,
    notice = '',
  ): Promise<T | null> {
    const epoch = this.epoch;
    this.pending.set(true);
    this.error.set('');
    this.notice.set('');
    try {
      const value = await operation();
      if (epoch !== this.epoch) return null;
      apply?.(value);
      this.notice.set(notice);
      return value;
    } catch (error) {
      if (epoch === this.epoch) this.fail(error);
      return null;
    } finally {
      if (epoch === this.epoch) this.pending.set(false);
    }
  }
  async load() {
    const tenant = this.f.tenantId();
    return this.perform(
      () => this.clients.get().configuration.get(tenant),
      (value) => this.configuration.set(value),
    );
  }
  async loadAgents(
    filter: Partial<{ page: number; page_size: number; q: string; status: string }> = {},
  ) {
    this.agentFilter.update((value) => ({ ...value, ...filter }));
    return this.perform(
      () => this.clients.get().agents.list(this.f.tenantId(), { query: this.agentFilter() }),
      (value) => this.agents.set(value),
    );
  }
  async saveProvider(id: string | null, input: ProviderInput) {
    this.validation.set(null);
    const client = this.clients.get(),
      tenant = this.f.tenantId();
    return this.perform(
      () =>
        id ? client.providers.update(tenant, id, input) : client.providers.create(tenant, input),
      (provider) =>
        this.configuration.update((value) =>
          value
            ? {
                ...value,
                providers: [...value.providers.filter((row) => row.id !== provider.id), provider],
              }
            : null,
        ),
      'Provider settings saved',
    );
  }
  async validateProvider(id: string) {
    const result = await this.perform(
      () => this.clients.get().providers.validate(this.f.tenantId(), id),
      (value) => this.validation.set(value),
    );
    if (result) {
      const epoch = this.epoch;
      try {
        const configuration = await this.clients.get().configuration.get(this.f.tenantId());
        if (epoch === this.epoch) this.configuration.set(configuration);
      } catch (error) {
        if (epoch === this.epoch) this.fail(error);
      }
    }
    return result;
  }
  async saveAgent(id: string | null, input: AgentInput) {
    const client = this.clients.get(),
      tenant = this.f.tenantId(),
      epoch = this.epoch;
    const agent = await this.perform(
      () => (id ? client.agents.update(tenant, id, input) : client.agents.create(tenant, input)),
      undefined,
    );
    if (!agent || epoch !== this.epoch) return null;
    await this.loadAgents({ page: 1 });
    if (epoch !== this.epoch) return null;
    this.notice.set('Agent settings saved');
    return agent;
  }
  async validateAgent(id: string) {
    const epoch = this.epoch;
    const agent = await this.perform(
      () => this.clients.get().agents.validate(this.f.tenantId(), id),
      undefined,
    );
    if (!agent || epoch !== this.epoch) return null;
    await this.loadAgents();
    return epoch === this.epoch ? agent : null;
  }
  provider(id: string) {
    return this.configuration()?.providers.find((provider) => provider.id === id);
  }
  ngOnDestroy() {
    ++this.epoch;
  }
}
