// Copyright 2026 Firefly Software Foundation SPDX-License-Identifier: Apache-2.0
import { Injectable, OnDestroy, effect, inject, signal } from '@angular/core';
import { KoinonClientContext, KoinonFacade } from '@fireflyframework/koinon-angular';
import type {
  KnowledgeConnection,
  KnowledgeConnectionInput,
  KnowledgeRoles,
} from '@fireflyframework/koinon-sdk';

@Injectable()
export class KoinonKnowledgeConfiguration implements OnDestroy {
  private readonly clients = inject(KoinonClientContext);
  private readonly facade = inject(KoinonFacade);
  private epoch = 0;
  private key = this.contextKey();
  readonly scope = signal('');
  readonly roles = signal<KnowledgeRoles | null>(null);
  readonly connections = signal<KnowledgeConnection[]>([]);
  readonly pending = signal(false);
  readonly error = signal<Error | null>(null);
  readonly notice = signal('');
  constructor() {
    effect(() => {
      const key = this.contextKey();
      if (key !== this.key) {
        this.key = key;
        ++this.epoch;
        this.scope.set('');
        this.roles.set(null);
        this.connections.set([]);
        this.pending.set(false);
        this.error.set(null);
        this.notice.set('');
      }
    });
  }
  private contextKey() {
    return this.facade.tenantId() + ':' + this.clients.revision();
  }
  private failure(error: unknown) {
    const value =
      error instanceof Error ? error : new Error('Knowledge models could not be loaded.');
    if ('status' in value && value.status === 401) this.facade.authRequired.set(true);
    this.error.set(value);
  }
  async load(scope = this.scope()) {
    const epoch = ++this.epoch,
      tenant = this.facade.tenantId(),
      client = this.clients.get();
    this.scope.set(scope);
    this.pending.set(true);
    this.error.set(null);
    this.notice.set('');
    this.roles.set(null);
    this.connections.set([]);
    try {
      const [roles, connections] = await Promise.all([
        client.knowledgeConnections.roles(tenant, scope || undefined),
        client.knowledgeConnections.list(tenant, scope || undefined),
      ]);
      if (epoch !== this.epoch) return false;
      this.roles.set(roles);
      this.connections.set(connections.items);
      return true;
    } catch (error) {
      if (epoch === this.epoch) this.failure(error);
      return false;
    } finally {
      if (epoch === this.epoch) this.pending.set(false);
    }
  }
  async save(input: KnowledgeConnectionInput, existing: KnowledgeConnection | null) {
    const epoch = this.epoch,
      tenant = this.facade.tenantId(),
      scope = this.scope(),
      client = this.clients.get();
    this.pending.set(true);
    this.error.set(null);
    this.notice.set('');
    try {
      const value = existing
        ? await client.knowledgeConnections.update(tenant, existing.id, {
            ...input,
            expected_revision: existing.revision,
          })
        : await client.knowledgeConnections.create(tenant, input);
      if (epoch !== this.epoch) return null;
      if (!(await this.load(scope))) return null;
      if (this.scope() !== scope || tenant !== this.facade.tenantId()) return null;
      this.notice.set('Knowledge model assignment saved.');
      return value;
    } catch (error) {
      if (epoch === this.epoch) this.failure(error);
      return null;
    } finally {
      if (epoch === this.epoch) this.pending.set(false);
    }
  }
  async remove(existing: KnowledgeConnection) {
    const epoch = this.epoch,
      tenant = this.facade.tenantId(),
      scope = this.scope();
    this.pending.set(true);
    this.error.set(null);
    this.notice.set('');
    try {
      await this.clients.get().knowledgeConnections.remove(tenant, existing.id, existing.revision);
      if (epoch !== this.epoch) return false;
      if (!(await this.load(scope))) return false;
      if (this.scope() !== scope || tenant !== this.facade.tenantId()) return false;
      this.notice.set(
        scope ? 'Workspace override removed.' : 'Knowledge model assignment removed.',
      );
      return true;
    } catch (error) {
      if (epoch === this.epoch) this.failure(error);
      return false;
    } finally {
      if (epoch === this.epoch) this.pending.set(false);
    }
  }
  ngOnDestroy() {
    ++this.epoch;
  }
}
