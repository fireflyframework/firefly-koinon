// Copyright 2026 Firefly Software Foundation
// SPDX-License-Identifier: Apache-2.0
import { computed, signal } from '@angular/core';
import { KoinonError } from '@fireflyframework/koinon-sdk';
import type { CommunicationsApi } from '@fireflyframework/koinon-sdk/communications';
import type {
  CommunicationPolicyView,
  CommunicationReadiness,
  DeliveryFilter,
  DeliveryPage,
  DeliveryRecordView,
} from '@fireflyframework/koinon-angular/communications';
import { communicationRules } from '@fireflyframework/koinon-angular/communications/runtime';
interface Scope {
  key: string;
  tenantId: string;
  allowed: boolean;
}
export interface View {
  readiness: CommunicationReadiness | null;
  policy: CommunicationPolicyView | null;
  deliveries: DeliveryPage | null;
  selected: DeliveryRecordView | null;
  busy: boolean;
  background: boolean;
  stale: boolean;
  denied: boolean;
  error: string;
}
const empty = (): View => ({
  readiness: null,
  policy: null,
  deliveries: null,
  selected: null,
  busy: false,
  background: false,
  stale: false,
  denied: false,
  error: '',
});
export class CommunicationsObservation {
  private readonly state = signal<View>(empty());
  private key: string;
  private request?: AbortController;
  private alive = true;
  readonly view = computed(() => {
    const value = this.state();
    return this.alive && this.ports.scope().key === this.key && this.ports.scope().allowed
      ? value
      : empty();
  });
  constructor(
    private readonly ports: {
      scope(): Scope;
      api(): CommunicationsApi | null;
      denied(status: 401 | 403): void;
    },
  ) {
    this.key = ports.scope().key;
  }
  sync() {
    const scope = this.ports.scope();
    if (scope.key === this.key && scope.allowed) return;
    this.request?.abort();
    this.request = undefined;
    this.key = scope.key;
    this.state.set(empty());
  }
  patch(value: Partial<View>) {
    this.sync();
    if (this.alive && this.ports.scope().allowed && !this.view().denied)
      this.state.update((current) => ({ ...current, ...value }));
  }
  cancelRead() {
    if (!this.request) return;
    this.request?.abort();
    this.request = undefined;
    this.state.update((value) => ({ ...value, busy: false, background: false }));
  }
  deny(status: 401 | 403) {
    this.request?.abort();
    this.request = undefined;
    this.state.set({
      ...empty(),
      denied: true,
      error: 'Your current account cannot manage communications.',
    });
    this.ports.denied(status);
  }
  async load(
    section: string,
    filter: DeliveryFilter,
    selected: string | null,
    includePolicy = false,
    background = false,
  ): Promise<boolean> {
    this.sync();
    const scope = this.ports.scope(),
      api = this.ports.api();
    if (!this.alive || !scope.allowed || this.view().denied || !api) return true;
    if (background && this.request) return true;
    this.request?.abort();
    const controller = new AbortController();
    this.request = controller;
    const current = () =>
      this.alive &&
      this.request === controller &&
      !controller.signal.aborted &&
      scope.key === this.ports.scope().key &&
      this.ports.scope().allowed;
    this.state.update((value) => ({ ...value, busy: true, background }));
    const options = { signal: controller.signal };
    try {
      const tasks: Promise<Partial<View>>[] = [];
      if (section === 'service' || includePolicy)
        tasks.push(
          api.administration
            .capabilities(scope.tenantId, options)
            .then((readiness) => ({ readiness })),
        );
      if (includePolicy)
        tasks.push(
          api.administration
            .policy(scope.tenantId, options)
            .then((policy) => ({ policy: { ...policy, rules: communicationRules(policy.rules) } })),
        );
      if (section === 'history') {
        tasks.push(
          api.administration
            .deliveries(
              scope.tenantId,
              {
                page: filter.page,
                page_size: filter.page_size,
                ...(filter.status ? { status: filter.status } : {}),
                ...(filter.kind ? { event_kind: filter.kind } : {}),
                ...(filter.from
                  ? { created_from: new Date(filter.from + 'T00:00:00').toISOString() }
                  : {}),
                ...(filter.to
                  ? { created_to: new Date(filter.to + 'T23:59:59.999').toISOString() }
                  : {}),
              },
              options,
            )
            .then((deliveries) => ({ deliveries })),
        );
        if (selected)
          tasks.push(
            api.administration.delivery(scope.tenantId, selected, options).then((value) => {
              if (value.id !== selected) throw Error('Delivery observation mismatch');
              return { selected: value };
            }),
          );
      }
      const values = await Promise.all(tasks);
      if (!current()) return true;
      this.state.update((value) => ({
        ...value,
        ...Object.assign({}, ...values),
        stale: false,
        error: '',
      }));
      return true;
    } catch (error) {
      if (!current()) return true;
      controller.abort();
      if (error instanceof KoinonError && (error.status === 401 || error.status === 403))
        this.deny(error.status);
      else
        this.state.update((value) => ({
          ...value,
          stale: true,
          error:
            'Communication status could not be updated. Previously observed information may be out of date.',
        }));
      return false;
    } finally {
      if (this.request === controller) {
        this.request = undefined;
        this.state.update((value) => ({ ...value, busy: false, background: false }));
      }
    }
  }
  dispose() {
    this.alive = false;
    this.request?.abort();
    this.request = undefined;
    this.state.set(empty());
  }
}
