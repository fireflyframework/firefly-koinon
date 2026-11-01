// Copyright 2026 Firefly Software Foundation SPDX-License-Identifier: Apache-2.0
import { registerKoinonSpanish } from '@fireflyframework/koinon-angular/workbench';
import { COMMUNICATION_RUNTIME_SPANISH } from './spanish';
registerKoinonSpanish(COMMUNICATION_RUNTIME_SPANISH);
import type { Signal } from '@angular/core';
import { DestroyRef, Injectable, computed, effect, inject, signal } from '@angular/core';
import { KoinonClientContext, KoinonFacade } from '@fireflyframework/koinon-angular';
import { KoinonError } from '@fireflyframework/koinon-sdk';
import {
  createCommunicationsApi,
  type CommunicationsApi,
} from '@fireflyframework/koinon-sdk/communications';
import type { NotificationPreferenceRule as WireRule } from '@fireflyframework/koinon-sdk';
import type { NotificationPreferenceRule } from '@fireflyframework/koinon-angular/communications';
const descriptions = {
  welcome: ['Welcome', 'An introduction to your organization’s shared knowledge.'],
  security: ['Security and access', 'Required updates about tokens and authorized applications.'],
  invitation: ['Invitations', 'Updates about invitations addressed to your account.'],
  access_granted: ['Access granted', 'New organization or workspace roles.'],
  role_changed: ['Role changed', 'Changes to your existing access.'],
  access_removed: [
    'Access removed',
    'Required access updates remain available after a role is removed.',
  ],
  digest: ['Usage summary', 'Your own usage counts, without private content.'],
} as const;
export function communicationRules(rules: readonly WireRule[]): NotificationPreferenceRule[] {
  return rules.map((rule) => ({
    ...rule,
    label: descriptions[rule.kind][0],
    description: descriptions[rule.kind][1],
  }));
}
export interface BoundCommunicationState<T> extends Signal<T> {
  set(value: T): void;
  update(change: (value: T) => T): void;
}
@Injectable()
export class KoinonCommunicationsSession {
  readonly facade = inject(KoinonFacade);
  private readonly clients = inject(KoinonClientContext);
  private contextIdentity: object | null = null;
  private contextRevision = 0;
  readonly key = computed(() => {
    const context = this.facade.context();
    if (context !== this.contextIdentity) {
      this.contextIdentity = context;
      ++this.contextRevision;
    }
    return `${context?.subject ?? ''}:${this.facade.tenantId()}:${this.facade.workspaceId?.() ?? ''}:${this.clients.revision()}:${this.contextRevision}`;
  });
  readonly error = signal('');
  readonly pending = signal(false);
  private readonly requests = new Map<string, AbortController>();
  private readonly requestKeys = new Map<string, string>();
  private readonly currentApi = computed(() => {
    this.clients.revision();
    const transport = this.clients.getTransport();
    return transport ? createCommunicationsApi(transport) : null;
  });
  get api(): CommunicationsApi | null {
    return this.currentApi();
  }
  state<T>(initial: T): BoundCommunicationState<T> {
    const stored = signal({ key: this.key(), value: initial });
    const read = computed(() => (stored().key === this.key() ? stored().value : initial));
    return Object.assign(read, {
      set: (value: T) => stored.set({ key: this.key(), value }),
      update: (change: (value: T) => T) => stored.set({ key: this.key(), value: change(read()) }),
    });
  }
  constructor() {
    let previous = this.key();
    effect(() => {
      const key = this.key();
      if (key !== previous) {
        previous = key;
        this.cancel(key);
        this.error.set('');
      }
    });
    inject(DestroyRef).onDestroy(() => this.cancel());
  }
  private cancel(currentKey?: string) {
    for (const [channel, request] of this.requests) {
      if (currentKey === undefined || this.requestKeys.get(channel) !== currentKey) {
        request.abort();
        this.requests.delete(channel);
        this.requestKeys.delete(channel);
      }
    }
    this.pending.set(this.requests.size > 0);
  }

  async run<T>(
    channel: string,
    request: (signal: AbortSignal) => Promise<T>,
    apply: (value: T) => void,
    failed?: (error: unknown) => void,
  ): Promise<T | null> {
    if (!this.api) {
      this.error.set(
        'Communications are not connected in this application. Contact the application owner.',
      );
      return null;
    }
    const key = this.key(),
      controller = new AbortController();
    this.requests.get(channel)?.abort();
    this.requests.set(channel, controller);
    this.requestKeys.set(channel, key);
    this.pending.set(true);
    this.error.set('');
    const current = () =>
      key === this.key() && this.requests.get(channel) === controller && !controller.signal.aborted;
    try {
      const result = await request(controller.signal);
      if (!current()) return null;
      apply(result);
      return result;
    } catch (error) {
      if (current()) {
        if (error instanceof KoinonError && error.status === 401)
          this.facade.authRequired.set(true);
        this.error.set(
          error instanceof KoinonError && error.status === 409
            ? 'This information changed. Refresh it before trying again.'
            : error instanceof KoinonError && error.status === 403
              ? 'Your current account cannot perform this action.'
              : 'Communications could not be loaded or saved. Try again.',
        );
        failed?.(error);
      }
      return null;
    } finally {
      if (this.requests.get(channel) === controller) {
        this.requests.delete(channel);
        this.requestKeys.delete(channel);
        this.pending.set(this.requests.size > 0);
      }
    }
  }
}
