// Copyright 2026 Firefly Software Foundation SPDX-License-Identifier: Apache-2.0
import {
  ChangeDetectionStrategy,
  Component,
  DestroyRef,
  effect,
  inject,
  signal,
  untracked,
} from '@angular/core';
import { UploadObservationLoop } from '@fireflyframework/koinon-angular/workbench/availability';
import { KoinonError } from '@fireflyframework/koinon-sdk';
import {
  KoinonCommunicationsSession,
  communicationRules,
} from '@fireflyframework/koinon-angular/communications/runtime';
import type { DeliveryFilter } from '@fireflyframework/koinon-angular/communications';
import { KoinonCommunicationsAdmin, type CommunicationPolicyUpdate } from './communications-admin';
import { CommunicationsObservation } from './communications-observation';
@Component({
  selector: 'ffk-communications-settings',
  imports: [KoinonCommunicationsAdmin],
  providers: [KoinonCommunicationsSession],
  template: `<ffk-communications-admin
    [deliverySession]="session"
    [readiness]="view().readiness"
    [policy]="view().policy"
    [deliveries]="view().deliveries"
    [selected]="view().selected"
    [loading]="session.pending() || (view().busy && !view().background)"
    [saving]="session.pending()"
    [stale]="view().stale"
    [denied]="view().denied || !allowed()"
    [retryPending]="retryPending()"
    [error]="view().error || session.error()"
    [notice]="notice()"
    (refreshRequested)="refresh()"
    (sectionChanged)="section($event)"
    (filterChanged)="history($event)"
    (policyChanged)="save($event)"
    (deliveryRequested)="detail($event)"
    (deliveryClosed)="close()"
    (deliveryAccessDenied)="deliveryDenied()"
    (observationPaused)="paused.set($event)"
    (retryRequested)="retry($event)"
  />`,
  changeDetection: ChangeDetectionStrategy.OnPush,
})
export class KoinonCommunicationsSettings {
  readonly session = inject(KoinonCommunicationsSession);
  readonly retryPending = this.session.state<string | null>(null);
  readonly notice = this.session.state('');
  readonly paused = signal(false);
  readonly now = signal(Date.now());
  private readonly currentSection = signal('service');
  private selectedId: string | null = null;
  private expiry?: ReturnType<typeof setTimeout>;
  private readonly visible = signal(
    typeof document === 'undefined' || document.visibilityState !== 'hidden',
  );
  readonly state = new CommunicationsObservation({
    scope: () => ({
      key: this.session.key(),
      tenantId: this.session.facade.tenantId(),
      allowed: this.allowed(),
    }),
    api: () => this.session.api,
    denied: (status) => {
      if (status === 401) this.session.facade.authRequired.set(true);
    },
  });
  readonly view = this.state.view;
  private filter: DeliveryFilter = {
    page: 1,
    page_size: 25,
    status: '',
    kind: '',
    from: '',
    to: '',
  };
  private readonly polling = new UploadObservationLoop({
    active: () =>
      this.allowed() &&
      !this.view().denied &&
      !this.view().busy &&
      !this.session.pending() &&
      !this.paused() &&
      this.currentSection() !== 'policy',
    visible: () => this.visible(),
    interval: () =>
      [
        ...(this.view().deliveries?.items ?? []),
        ...(this.view().selected ? [this.view().selected!] : []),
      ].some((row) => ['queued', 'sending', 'deferred'].includes(row.status))
        ? 5000
        : 30000,
    read: () => this.refresh(true),
  });
  private readonly reenter = () => {
    this.visible.set(document.visibilityState !== 'hidden');
    this.now.set(Date.now());
    this.polling.reset();
  };
  allowed() {
    this.now();
    const context = this.session.facade.context(),
      tenantId = this.session.facade.tenantId();
    return (
      !!context?.subject &&
      !!this.session.api &&
      context.tenants.some((t) => t.id === tenantId && t.permissions.includes('members:write')) &&
      context.memberships.some(
        (m) =>
          m.subject === context.subject &&
          m.tenant_id === tenantId &&
          !m.workspace_id &&
          m.role === 'admin' &&
          m.active &&
          (!m.expires_at || Date.parse(m.expires_at) > Date.now()),
      )
    );
  }
  constructor() {
    effect(() => {
      this.now();
      const context = this.session.facade.context();
      clearTimeout(this.expiry);
      const times =
        context?.memberships
          .map((m) => Date.parse(m.expires_at ?? ''))
          .filter((time) => Number.isFinite(time) && time > Date.now()) ?? [];
      if (times.length)
        this.expiry = setTimeout(
          () => this.now.set(Date.now()),
          Math.min(Math.max(1, Math.min(...times) - Date.now() + 1), 2147483647),
        );
    });
    let previousKey = '',
      previousAllowed = false;
    effect(() => {
      const key = this.session.key(),
        allowed = this.allowed();
      if (key === previousKey && allowed === previousAllowed) return;
      previousKey = key;
      previousAllowed = allowed;
      untracked(() => {
        this.state.sync();
        this.selectedId = null;
        this.notice.set('');
        this.paused.set(false);
        void this.refresh();
      });
    });
    effect(() => {
      this.view();
      this.session.pending();
      this.paused();
      this.currentSection();
      this.visible();
      this.now();
      if (this.paused() || this.session.pending()) untracked(() => this.state.cancelRead());
      this.polling.update();
    });
    if (typeof document !== 'undefined') {
      document.addEventListener('visibilitychange', this.reenter);
      window.addEventListener('focus', this.reenter);
    }
    inject(DestroyRef).onDestroy(() => {
      this.polling.dispose();
      this.state.dispose();
      clearTimeout(this.expiry);
      if (typeof document !== 'undefined') {
        document.removeEventListener('visibilitychange', this.reenter);
        window.removeEventListener('focus', this.reenter);
      }
    });
  }
  async refresh(background = false) {
    return this.state.load(
      this.currentSection(),
      this.filter,
      this.selectedId,
      !this.view().policy,
      background,
    );
  }
  section(section: string) {
    this.state.cancelRead();
    this.currentSection.set(section);
    if (section !== 'policy' || !this.view().policy) void this.refresh();
  }
  async history(filter: DeliveryFilter) {
    this.filter = { ...filter };
    this.close();
    await this.refresh();
  }
  private writeFailed(error: unknown) {
    if (error instanceof KoinonError && (error.status === 401 || error.status === 403))
      this.state.deny(error.status);
  }
  async save(input: CommunicationPolicyUpdate) {
    if (!this.allowed() || this.view().stale || this.view().denied) return;
    this.notice.set('');
    await this.session.run(
      'save',
      (signal) =>
        this.session.api!.administration.updatePolicy(this.session.facade.tenantId(), input, {
          signal,
        }),
      (value) => {
        this.state.patch({ policy: { ...value, rules: communicationRules(value.rules) } });
        this.notice.set('Communication policy saved.');
      },
      (error) => this.writeFailed(error),
    );
  }
  async detail(id: string) {
    this.selectedId = id;
    this.state.patch({ selected: null });
    await this.refresh();
  }
  close() {
    this.state.cancelRead();
    this.selectedId = null;
    this.state.patch({ selected: null });
    this.paused.set(false);
  }
  deliveryDenied() {
    this.state.deny(this.session.facade.authRequired() ? 401 : 403);
  }
  async retry(id: string) {
    if (
      !this.allowed() ||
      this.view().stale ||
      this.view().denied ||
      !this.view().selected?.can_retry ||
      this.view().selected?.id !== id ||
      this.retryPending()
    )
      return;
    this.retryPending.set(id);
    await this.session.run(
      'retry',
      (signal) =>
        this.session.api!.administration.retry(this.session.facade.tenantId(), id, { signal }),
      (value) => this.state.patch({ selected: value }),
      (error) => this.writeFailed(error),
    );
    this.retryPending.set(null);
    await this.refresh();
  }
}
