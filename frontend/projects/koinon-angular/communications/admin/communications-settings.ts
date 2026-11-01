// Copyright 2026 Firefly Software Foundation SPDX-License-Identifier: Apache-2.0
import { ChangeDetectionStrategy, Component, effect, inject, untracked } from '@angular/core';
import {
  KoinonCommunicationsSession,
  communicationRules,
} from '@fireflyframework/koinon-angular/communications/runtime';
import type {
  CommunicationPolicyView,
  CommunicationReadiness,
  DeliveryFilter,
  DeliveryPage,
  DeliveryRecordView,
} from '@fireflyframework/koinon-angular/communications';
import { KoinonCommunicationsAdmin } from './communications-admin';
import type { CommunicationPolicyUpdate } from './communications-admin';
@Component({
  selector: 'ffk-communications-settings',
  imports: [KoinonCommunicationsAdmin],
  providers: [KoinonCommunicationsSession],
  template: `<ffk-communications-admin
    [readiness]="readiness()"
    [policy]="policy()"
    [deliveries]="deliveries()"
    [selected]="selected()"
    [loading]="session.pending()"
    [saving]="session.pending()"
    [retryPending]="retryPending()"
    [error]="session.error()"
    [notice]="notice()"
    (refreshRequested)="refresh()"
    (sectionChanged)="section($event)"
    (filterChanged)="history($event)"
    (policyChanged)="save($event)"
    (deliveryRequested)="detail($event)"
    (deliveryClosed)="selected.set(null)"
    (retryRequested)="retry($event)"
  />`,
  changeDetection: ChangeDetectionStrategy.OnPush,
})
export class KoinonCommunicationsSettings {
  readonly session = inject(KoinonCommunicationsSession);
  readonly readiness = this.session.state<CommunicationReadiness | null>(null);
  readonly policy = this.session.state<CommunicationPolicyView | null>(null);
  readonly deliveries = this.session.state<DeliveryPage | null>(null);
  readonly selected = this.session.state<DeliveryRecordView | null>(null);
  readonly retryPending = this.session.state<string | null>(null);
  readonly notice = this.session.state('');
  private filter: DeliveryFilter = {
    page: 1,
    page_size: 25,
    status: '',
    kind: '',
    from: '',
    to: '',
  };
  private currentSection = 'service';
  constructor() {
    effect(() => {
      this.session.key();
      untracked(() => {
        this.readiness.set(null);
        this.policy.set(null);
        this.deliveries.set(null);
        this.selected.set(null);
        this.notice.set('');
        void this.refresh();
      });
    });
  }
  async refresh() {
    await Promise.all([
      this.session.run(
        'readiness',
        (signal) =>
          this.session.api!.administration.capabilities(this.session.facade.tenantId(), { signal }),
        (value) => this.readiness.set(value),
      ),
      this.session.run(
        'policy',
        (signal) =>
          this.session.api!.administration.policy(this.session.facade.tenantId(), { signal }),
        (value) => this.policy.set({ ...value, rules: communicationRules(value.rules) }),
      ),
    ]);
    if (this.currentSection === 'history') await this.history(this.filter);
  }
  section(section: string) {
    this.currentSection = section;
    if (section === 'history') void this.history(this.filter);
  }
  async history(filter: DeliveryFilter) {
    this.filter = filter;
    await this.session.run(
      'history',
      (signal) =>
        this.session.api!.administration.deliveries(
          this.session.facade.tenantId(),
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
          { signal },
        ),
      (value) => this.deliveries.set(value),
    );
  }
  async save(input: CommunicationPolicyUpdate) {
    this.notice.set('');
    await this.session.run(
      'save',
      (signal) =>
        this.session.api!.administration.updatePolicy(this.session.facade.tenantId(), input, {
          signal,
        }),
      (value) => {
        this.policy.set({ ...value, rules: communicationRules(value.rules) });
        this.notice.set('Communication policy saved.');
      },
    );
  }
  async detail(id: string) {
    this.selected.set(null);
    await this.session.run(
      'detail',
      (signal) =>
        this.session.api!.administration.delivery(this.session.facade.tenantId(), id, { signal }),
      (value) => this.selected.set(value),
    );
  }
  async retry(id: string) {
    if (!this.selected()?.can_retry || this.selected()?.id !== id || this.retryPending()) return;
    this.retryPending.set(id);
    await this.session.run(
      'retry',
      (signal) =>
        this.session.api!.administration.retry(this.session.facade.tenantId(), id, { signal }),
      (value) => this.selected.set(value),
    );
    this.retryPending.set(null);
    await this.history(this.filter);
  }
}
