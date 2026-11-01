// Copyright 2026 Firefly Software Foundation SPDX-License-Identifier: Apache-2.0
import {
  ChangeDetectionStrategy,
  Component,
  EventEmitter,
  Input,
  OnChanges,
  Output,
  SimpleChanges,
  signal,
} from '@angular/core';
import {
  KoinonDigestSchedule,
  validDigestSchedule,
} from '@fireflyframework/koinon-angular/communications/schedule';
import type {
  DigestFrequency,
  DigestSchedule,
  AdministrativeSummarySchedule,
} from '@fireflyframework/koinon-angular/communications';
import { FormsModule } from '@angular/forms';
import {
  KoinonBadge,
  KoinonButton,
  KoinonDatePipe,
  KoinonPagination,
  KoinonSkeleton,
  KoinonTextPipe,
} from '@fireflyframework/koinon-angular';
import type {
  CommunicationEvent,
  CommunicationPolicyView,
  CommunicationReadiness,
  DeliveryFilter,
  DeliveryPage,
  DeliveryRecordView,
  DeliveryState,
  NotificationPreferenceRule,
} from '@fireflyframework/koinon-angular/communications';

export interface CommunicationPolicyUpdate {
  expected_revision: number;
  default_locale: string | null;
  admin_summaries: AdministrativeSummarySchedule[];
  sender_id: string | null;
  digest_enabled: boolean;
  rules: { kind: CommunicationEvent; inbox: boolean; email: boolean }[];
  allowed_digests: DigestFrequency[];
  default_digest: DigestFrequency;
  default_schedule: DigestSchedule;
}
import { registerKoinonSpanish } from '@fireflyframework/koinon-angular/workbench';
import { COMMUNICATIONS_ADMIN_SPANISH } from './spanish';
registerKoinonSpanish(COMMUNICATIONS_ADMIN_SPANISH);

@Component({
  selector: 'ffk-communications-admin',
  imports: [
    KoinonDigestSchedule,
    FormsModule,
    KoinonBadge,
    KoinonButton,
    KoinonDatePipe,
    KoinonPagination,
    KoinonSkeleton,
    KoinonTextPipe,
  ],
  templateUrl: './communications-admin.html',
  styleUrl: './communications-admin.scss',
  changeDetection: ChangeDetectionStrategy.OnPush,
})
export class KoinonCommunicationsAdmin implements OnChanges {
  @Input() readiness: CommunicationReadiness | null = null;
  @Input() policy: CommunicationPolicyView | null = null;
  @Input() deliveries: DeliveryPage | null = null;
  @Input() selected: DeliveryRecordView | null = null;
  @Input() loading = false;
  @Input() saving = false;
  @Input() retryPending: string | null = null;
  @Input() error = '';
  @Input() notice = '';
  @Output() sectionChanged = new EventEmitter<'service' | 'policy' | 'history'>();
  @Output() filterChanged = new EventEmitter<DeliveryFilter>();
  @Output() policyChanged = new EventEmitter<CommunicationPolicyUpdate>();
  @Output() deliveryRequested = new EventEmitter<string>();
  @Output() deliveryClosed = new EventEmitter<void>();
  @Output() retryRequested = new EventEmitter<string>();
  @Output() refreshRequested = new EventEmitter<void>();
  readonly tab = signal<'service' | 'policy' | 'history'>('service');
  readonly confirmingRetry = signal('');
  readonly validation = signal('');
  rules: NotificationPreferenceRule[] = [];
  defaultLocale = '';
  adminSchedules: AdministrativeSummarySchedule[] = [];
  readonly adminCadences: AdministrativeSummarySchedule['cadence'][] = [
    'daily',
    'weekly',
    'monthly',
  ];
  adminSchedule(cadence: AdministrativeSummarySchedule['cadence']) {
    return this.adminSchedules.find((value) => value.cadence === cadence)?.schedule;
  }
  toggleAdminCadence(cadence: AdministrativeSummarySchedule['cadence'], enabled: boolean) {
    if (enabled && !this.adminSchedule(cadence))
      this.adminSchedules = [
        ...this.adminSchedules,
        { cadence, schedule: { local_time: '09:00', weekday: 0, day_of_month: 1 } },
      ];
    else if (!enabled)
      this.adminSchedules = this.adminSchedules.filter((value) => value.cadence !== cadence);
  }
  updateAdminSchedule(cadence: AdministrativeSummarySchedule['cadence'], schedule: DigestSchedule) {
    this.adminSchedules = this.adminSchedules.map((value) =>
      value.cadence === cadence ? { cadence, schedule: { ...schedule } } : value,
    );
  }

  digestEnabled = false;
  allowedDigests: DigestFrequency[] = ['off'];
  defaultDigest: DigestFrequency = 'off';
  defaultSchedule: DigestSchedule = { local_time: '09:00', weekday: 0, day_of_month: 1 };
  readonly frequencies: DigestFrequency[] = ['daily', 'weekly', 'monthly'];
  toggleDigest(frequency: DigestFrequency, enabled: boolean) {
    this.allowedDigests = enabled
      ? [...new Set([...this.allowedDigests, frequency])]
      : this.allowedDigests.filter((value) => value !== frequency);
    if (!this.allowedDigests.includes(this.defaultDigest)) this.defaultDigest = 'off';
  }
  digestLabel(value: DigestFrequency) {
    return { off: 'Off', daily: 'Daily', weekly: 'Weekly', monthly: 'Monthly' }[value];
  }
  senderId = '';
  status: DeliveryState | '' = '';
  kind: CommunicationEvent | '' = '';
  from = '';
  to = '';
  pageSize = 25;
  readonly states: DeliveryState[] = [
    'queued',
    'sending',
    'sent',
    'delivered',
    'deferred',
    'failed',
    'suppressed',
    'cancelled',
    'unknown',
  ];
  readonly kinds: CommunicationEvent[] = [
    'invitation',
    'access_granted',
    'role_changed',
    'access_removed',
    'digest',
    'security',
    'welcome',
  ];
  ngOnChanges(changes: SimpleChanges) {
    if (changes['policy']) {
      this.rules = this.policy?.rules.map((rule) => ({ ...rule })) ?? [];
      this.defaultLocale = this.policy?.default_locale ?? '';
      this.adminSchedules = (this.policy?.admin_summaries ?? []).map((value) => ({
        cadence: value.cadence,
        schedule: { ...value.schedule },
      }));
      this.digestEnabled = this.policy?.digest_enabled ?? false;
      this.allowedDigests = [...(this.policy?.allowed_digests ?? ['off'])];
      this.defaultDigest = this.policy?.default_digest ?? 'off';
      this.defaultSchedule = {
        ...(this.policy?.default_schedule ?? { local_time: '09:00', weekday: 0, day_of_month: 1 }),
      };
      this.senderId = this.policy?.sender_id ?? '';
    }
    if (changes['selected']) this.confirmingRetry.set('');
  }
  openSection(section: 'service' | 'policy' | 'history') {
    this.tab.set(section);
    this.validation.set('');
    this.sectionChanged.emit(section);
  }
  readinessLabel() {
    return this.readiness?.state === 'ready'
      ? 'Ready'
      : this.readiness?.state === 'degraded'
        ? 'Needs attention'
        : this.readiness?.state === 'disabled'
          ? 'Disabled'
          : 'Needs configuration';
  }
  statusLabel(status: DeliveryState) {
    return {
      queued: 'Queued',
      sending: 'Sending',
      sent: 'Accepted by email service',
      delivered: 'Delivered',
      deferred: 'Deferred',
      failed: 'Failed',
      suppressed: 'Suppressed',
      cancelled: 'Cancelled',
      unknown: 'Outcome unknown',
    }[status];
  }
  kindLabel(kind: CommunicationEvent) {
    return {
      invitation: 'Invitation',
      access_granted: 'Access granted',
      role_changed: 'Role changed',
      access_removed: 'Access removed',
      digest: 'Usage summary',
      security: 'Security and access',
      welcome: 'Welcome',
    }[kind];
  }
  changePage(page: number) {
    if (this.loading) return;
    if (this.from && this.to && this.from > this.to) {
      this.validation.set('The end date must be on or after the start date.');
      return;
    }
    this.validation.set('');
    this.filterChanged.emit({
      page,
      page_size: this.pageSize,
      status: this.status,
      kind: this.kind,
      from: this.from,
      to: this.to,
    });
  }
  changePageSize(size: number) {
    this.pageSize = size;
    this.changePage(1);
  }
  savePolicy() {
    if (!this.policy?.can_update || this.saving) return;
    if (
      this.senderId &&
      !this.readiness?.sender_options?.some((sender) => sender.id === this.senderId)
    ) {
      this.validation.set('Choose an available verified sender.');
      return;
    }
    if (this.digestEnabled && !this.allowedDigests.includes(this.defaultDigest)) {
      this.validation.set('Choose an available digest schedule.');
      return;
    }
    if (
      this.adminSchedules.length > 3 ||
      new Set(this.adminSchedules.map((value) => value.cadence)).size !==
        this.adminSchedules.length ||
      this.adminSchedules.some(
        (value) =>
          !this.adminCadences.includes(value.cadence) || !validDigestSchedule(value.schedule),
      )
    ) {
      this.validation.set('Choose one valid schedule for each administrator cadence.');
      return;
    }
    this.policyChanged.emit({
      expected_revision: this.policy.revision,
      admin_summaries: this.adminSchedules.map((value) => ({
        cadence: value.cadence,
        schedule: { ...value.schedule },
      })),
      default_locale: this.defaultLocale || null,
      sender_id: this.senderId || null,
      digest_enabled: this.digestEnabled,
      allowed_digests: this.digestEnabled
        ? [...new Set(['off' as const, ...this.allowedDigests])]
        : ['off'],
      default_digest: this.digestEnabled ? this.defaultDigest : 'off',
      default_schedule: { ...this.defaultSchedule },
      rules: this.policy.rules.map((original) => {
        const draft = this.rules.find((rule) => rule.kind === original.kind) ?? original;
        return {
          kind: original.kind,
          inbox: original.required ? original.inbox : draft.inbox,
          email: original.required || !original.email_available ? original.email : draft.email,
        };
      }),
    });
  }
  retry(record: DeliveryRecordView) {
    if (!record.can_retry || this.retryPending) return;
    this.confirmingRetry.set('');
    this.retryRequested.emit(record.id);
  }
}
