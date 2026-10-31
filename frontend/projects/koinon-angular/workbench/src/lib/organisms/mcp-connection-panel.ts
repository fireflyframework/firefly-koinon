// Copyright 2026 Firefly Software Foundation
// SPDX-License-Identifier: Apache-2.0
import {
  ChangeDetectionStrategy,
  Component,
  OnInit,
  OnDestroy,
  PendingTasks,
  effect,
  inject,
  signal,
} from '@angular/core';
import { DOCUMENT } from '@angular/common';
import { FormsModule } from '@angular/forms';
import type { McpConnectionDescriptor, McpRegisteredClient } from '@fireflyframework/koinon-sdk';
import { KoinonClientContext } from '../services/client-context';
import { KoinonFacade } from '../koinon-facade';
import { KoinonButton } from '../atoms/button';
import { KoinonTextPipe } from '../foundations/i18n';
let panelId = 0;
@Component({
  selector: 'ffk-mcp-connection-panel',
  imports: [FormsModule, KoinonButton, KoinonTextPipe],
  templateUrl: './mcp-connection-panel.html',
  styleUrl: './mcp-connection-panel.scss',
  changeDetection: ChangeDetectionStrategy.OnPush,
})
export class KoinonMcpConnectionPanel implements OnInit, OnDestroy {
  private readonly clients = inject(KoinonClientContext);
  private readonly facade = inject(KoinonFacade);
  private readonly tasks = inject(PendingTasks);
  private readonly document = inject(DOCUMENT);
  readonly id = 'mcp-connection-' + ++panelId;
  readonly value = signal<McpConnectionDescriptor | null>(null);
  readonly loading = signal(false);
  readonly error = signal('');
  readonly notice = signal('');
  app: 'claude' | 'chatgpt' = 'claude';
  registrationId = '';
  private alive = true;
  private request = 0;
  private abort?: AbortController;
  private identity = this.key();
  constructor() {
    effect(() => {
      const key = this.key();
      if (key === this.identity) return;
      this.identity = key;
      ++this.request;
      this.abort?.abort();
      this.value.set(null);
      this.registrationId = '';
      this.loading.set(false);
      this.error.set('');
      this.notice.set('Your account or organization changed. Reload the connection details.');
    });
  }
  private key() {
    return JSON.stringify([
      this.facade.context()?.subject ?? '',
      this.facade.tenantId(),
      this.clients.revision(),
    ]);
  }
  ngOnInit() {
    this.tasks.run(() => this.load());
  }
  ngOnDestroy() {
    this.alive = false;
    ++this.request;
    this.abort?.abort();
  }
  async load() {
    const request = ++this.request,
      key = this.key(),
      tenantId = this.facade.tenantId();
    this.abort?.abort();
    this.abort = new AbortController();
    this.value.set(null);
    this.loading.set(true);
    this.error.set('');
    this.notice.set('');
    this.registrationId = '';
    if (!tenantId) {
      this.loading.set(false);
      this.error.set('Choose an organization to load its connection details.');
      return;
    }
    try {
      const value = await this.clients.get().mcp.organizationConnection(tenantId, {
        signal: this.abort.signal,
      });
      if (!this.alive || request !== this.request || key !== this.key()) return;
      if (typeof value.enabled !== 'boolean' || !Array.isArray(value.authentication))
        throw new Error('Incomplete connection details');
      this.value.set(value);
      this.registrationId = '';
    } catch {
      if (this.alive && request === this.request && key === this.key())
        this.error.set('Connection details could not be loaded. Try again.');
    } finally {
      if (this.alive && request === this.request) this.loading.set(false);
    }
  }
  registrations(): McpRegisteredClient[] {
    const value = this.value();
    if (!value) return [];
    const rows: unknown = Reflect.get(value, 'clients');
    if (!Array.isArray(rows)) return [];
    return rows.filter((row: unknown): row is McpRegisteredClient => {
      if (!row || typeof row !== 'object') return false;
      const value = row as Record<string, unknown>;
      return (
        typeof value['client_id'] === 'string' &&
        typeof value['name'] === 'string' &&
        Array.isArray(value['scopes']) &&
        value['scopes'].every((s: unknown) => typeof s === 'string') &&
        (value['client_auth'] === 'public' || value['client_auth'] === 'confidential')
      );
    });
  }
  registration() {
    return this.registrations().find((row) => row.client_id === this.registrationId);
  }
  async copy(value: string) {
    try {
      const clipboard = this.document.defaultView?.navigator.clipboard;
      if (!clipboard) throw new Error('Clipboard unavailable');
      await clipboard.writeText(value);
      this.notice.set('Connection detail copied.');
    } catch {
      this.notice.set('Copy was blocked. Select and copy the value manually.');
    }
  }
}
