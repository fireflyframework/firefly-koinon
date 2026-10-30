// Copyright 2026 Firefly Software Foundation SPDX-License-Identifier: Apache-2.0
import {
  ChangeDetectionStrategy,
  Component,
  ElementRef,
  Injector,
  OnInit,
  PendingTasks,
  afterNextRender,
  effect,
  inject,
  signal,
} from '@angular/core';
import { FormsModule } from '@angular/forms';
import type {
  AuthorizedApplication,
  AuthorizedApplicationFilter,
} from '@fireflyframework/koinon-sdk';
import {
  KoinonAuthorizedApplications,
  applicationLifecycle,
} from '../services/authorized-applications';
import { KoinonTextPipe, KoinonDatePipe, KoinonI18n } from '../foundations/i18n';
import { KoinonButton } from '../atoms/button';
import { KoinonIcon } from '../atoms/icon';
import { KoinonPagination } from '../molecules/pagination';
import { KoinonMcpConnectionPanel } from './mcp-connection-panel';

const PERMISSIONS: Readonly<Record<string, string>> = {
  'catalog:read': 'Browse knowledge',
  'catalog:write': 'Maintain knowledge',
  'knowledge:search': 'Search documents',
  'query:execute': 'Query datasets',
  'audit:read': 'Read audit records',
  'chat:use': 'Use agents and chat',
  'ingest:write': 'Import knowledge',
  'exports:read': 'Download authorized exports',
  'exports:write': 'Create authorized exports',
  'shares:read': 'Read authenticated conversation shares',
  'shares:write': 'Create and revoke your conversation shares',
  'members:write': 'Manage people and access',
  'providers:write': 'Manage model providers',
  'agents:write': 'Configure agents',
  'jobs:manage': 'Manage processing jobs',
  'sources:configure': 'Configure sources',
  'indexes:manage': 'Manage indexes',
  'settings:write': 'Manage organization settings',
  'identity:manage': 'Manage identity policy',
};

@Component({
  selector: 'ffk-authorized-applications-panel',
  imports: [
    FormsModule,
    KoinonTextPipe,
    KoinonDatePipe,
    KoinonButton,
    KoinonIcon,
    KoinonPagination,
    KoinonMcpConnectionPanel,
  ],
  providers: [KoinonAuthorizedApplications],
  templateUrl: './authorized-applications-panel.html',
  styleUrl: './authorized-applications-panel.scss',
  changeDetection: ChangeDetectionStrategy.OnPush,
})
export class KoinonAuthorizedApplicationsPanel implements OnInit {
  readonly state = inject(KoinonAuthorizedApplications);
  readonly i18n = inject(KoinonI18n);
  lifecycle(row: AuthorizedApplication) {
    return applicationLifecycle(row);
  }
  private readonly tasks = inject(PendingTasks);
  private readonly host = inject<ElementRef<HTMLElement>>(ElementRef);
  private readonly injector = inject(Injector);
  private trigger?: HTMLElement;
  private triggerId = '';
  readonly confirming = signal<AuthorizedApplication | null>(null);
  readonly connecting = signal(false);
  query = '';
  constructor() {
    effect(() => {
      this.state.identity();
      this.confirming.set(null);
      this.query = '';
    });
  }
  ngOnInit() {
    this.tasks.run(() => this.state.load());
  }
  filter(patch: AuthorizedApplicationFilter = {}) {
    this.confirming.set(null);
    return this.state.load(patch);
  }
  apply() {
    return this.filter({ q: this.query, page: 1 });
  }
  clear() {
    this.query = '';
    return this.filter({ q: '', status: 'all', page: 1, sort: 'connected_at', order: 'desc' });
  }
  sortChoice() {
    return (
      (this.state.filter().sort || 'connected_at') + ':' + (this.state.filter().order || 'desc')
    );
  }
  sort(value: string) {
    const [key, order] = value.split(':');
    if (
      ['connected_at', 'name', 'expires_at', 'last_used_at'].includes(key) &&
      ['asc', 'desc'].includes(order)
    )
      return this.filter({
        sort: key as AuthorizedApplicationFilter['sort'],
        order: order as 'asc' | 'desc',
        page: 1,
      });
    return Promise.resolve(null);
  }
  permission(scope: string) {
    return PERMISSIONS[scope] || 'Additional permission';
  }
  activity(value: string | null) {
    if (!value) return null;
    const stamp = Date.parse(value);
    return Number.isFinite(stamp)
      ? new Date(Math.floor(stamp / 300000) * 300000).toISOString()
      : null;
  }
  async open(id: string) {
    if (this.state.detail()?.id === id) {
      this.state.closeDetail();
      return;
    }
    if (await this.state.open(id)) this.focus('.permission-heading');
  }
  confirm(row: AuthorizedApplication, event: Event) {
    this.trigger = (event.target as HTMLElement).closest('button') ?? undefined;
    this.triggerId = row.id;
    this.confirming.set(row);
    this.focus('.confirmation-heading');
  }
  cancel() {
    this.confirming.set(null);
    this.focusTrigger();
  }
  async revoke() {
    const row = this.confirming();
    if (!row) return;
    if (await this.state.revoke(row.id)) {
      this.confirming.set(null);
      this.focus('.notice');
    }
  }
  private focus(selector: string) {
    afterNextRender(
      () => {
        const target = this.host.nativeElement.querySelector<HTMLElement>(selector);
        target?.focus({ preventScroll: true });
        const list = target?.closest<HTMLElement>('.account-body,main');
        if (target && list) {
          const item = (
              target.closest('.confirmation,.connection-detail') || target
            ).getBoundingClientRect(),
            bounds = list.getBoundingClientRect();
          if (item.bottom > bounds.bottom) list.scrollTop += item.bottom - bounds.bottom + 12;
          else if (item.top < bounds.top) list.scrollTop -= bounds.top - item.top + 12;
        }
      },
      { injector: this.injector },
    );
  }
  private focusTrigger() {
    afterNextRender(
      () => {
        if (this.trigger?.isConnected) this.trigger.focus({ preventScroll: true });
        else {
          const row = [
            ...this.host.nativeElement.querySelectorAll<HTMLElement>('.application-row'),
          ].find((value) => value.dataset['applicationId'] === this.triggerId);
          row?.querySelector<HTMLElement>('.revoke-trigger button')?.focus({ preventScroll: true });
        }
      },
      { injector: this.injector },
    );
  }
}
