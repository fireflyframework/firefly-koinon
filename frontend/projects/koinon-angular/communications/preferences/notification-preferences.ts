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
  inject,
} from '@angular/core';
import {
  KoinonActivityWindow,
  activityWindow,
  defaultActivityDates,
} from '@fireflyframework/koinon-angular/activity/window';
import { KoinonEmailPreview } from '@fireflyframework/koinon-angular/communications/email-preview';
import type { ActivityWindow } from '@fireflyframework/koinon-sdk';
import type { CommunicationEmailPreview } from '@fireflyframework/koinon-angular/communications';
import { KoinonDigestSchedule } from '@fireflyframework/koinon-angular/communications/schedule';
import type {
  DigestSchedule,
  DigestSchedulePreview,
} from '@fireflyframework/koinon-angular/communications';
import { FormsModule } from '@angular/forms';
import {
  KoinonBadge,
  KoinonDatePipe,
  KoinonI18n,
  KoinonButton,
  KoinonSkeleton,
  KoinonTextPipe,
} from '@fireflyframework/koinon-angular';
import type {
  NotificationPreferenceRule,
  NotificationPreferencesUpdate,
  NotificationPreferencesView,
} from '@fireflyframework/koinon-angular/communications';
import { registerKoinonSpanish } from '@fireflyframework/koinon-angular/workbench';
import { NOTIFICATION_SPANISH } from './spanish';
registerKoinonSpanish(NOTIFICATION_SPANISH);

@Component({
  selector: 'ffk-notification-preferences',
  imports: [
    KoinonDigestSchedule,
    KoinonActivityWindow,
    KoinonEmailPreview,
    FormsModule,
    KoinonBadge,
    KoinonDatePipe,
    KoinonButton,
    KoinonSkeleton,
    KoinonTextPipe,
  ],
  templateUrl: './notification-preferences.html',
  styleUrl: './notification-preferences.scss',
  changeDetection: ChangeDetectionStrategy.OnPush,
})
export class KoinonNotificationPreferences implements OnChanges {
  private readonly i18n = inject(KoinonI18n);
  localPresentation(time_zone: string) {
    return { ...this.i18n.preferences(), time_zone };
  }
  @Input() showHeading = true;
  @Input() preferences: NotificationPreferencesView | null = null;
  @Input() pending = false;
  @Input() error = '';
  @Input() notice = '';
  @Input() schedulePreview: DigestSchedulePreview | null = null;
  @Input() previewPending = false;
  @Input() emailPreview: CommunicationEmailPreview | null = null;
  @Input() emailPreviewPending = false;
  @Input() canPreviewEmail = false;
  @Output() emailPreviewRequested = new EventEmitter<{
    preferences: NotificationPreferencesUpdate;
    window: ActivityWindow;
  }>();
  private readonly dates = defaultActivityDates();
  emailWindow: ActivityWindow | null | undefined = undefined;
  private emailDraft = '';
  matchingEmailPreview() {
    return this.emailPreview &&
      this.emailDraft ===
        JSON.stringify({ preferences: this.draftInput(), window: this.reportingWindow() })
      ? this.emailPreview
      : null;
  }
  private reportingWindow() {
    return this.emailWindow === undefined
      ? activityWindow(this.dates.start, this.dates.end, this.preferences?.time_zone ?? 'UTC')
      : this.emailWindow;
  }
  previewEmail() {
    const input = this.buildInput(),
      window = this.reportingWindow();
    if (!input || !window) {
      this.validation.set('Choose a valid past reporting window of at most 366 days.');
      return;
    }
    this.emailDraft = JSON.stringify({ preferences: input, window });
    this.emailPreviewRequested.emit({ preferences: input, window });
  }
  @Output() previewRequested = new EventEmitter<NotificationPreferencesUpdate>();
  @Output() saved = new EventEmitter<NotificationPreferencesUpdate>();
  @Output() backRequested = new EventEmitter<void>();
  readonly validation = signal('');
  rules: NotificationPreferenceRule[] = [];
  digest: NotificationPreferencesView['digest'] = 'off';
  notificationLocale = '';
  adminSummaries: 'inherit' | 'on' | 'off' = 'inherit';
  changeDigest(value: NotificationPreferencesView['digest']) {
    this.digest = value;
    if (value !== 'off') {
      const rule = this.rules.find((item) => item.kind === 'digest');
      if (rule?.email_available && !rule.required) rule.email = true;
    }
  }
  localeLabel(value: string) {
    return value.startsWith('es') ? 'Español (' + value + ')' : 'English (' + value + ')';
  }
  originLabel(value: string | undefined) {
    return value === 'user'
      ? 'Your preference'
      : value === 'organization'
        ? 'Organization default'
        : value === 'installation'
          ? 'Installation default'
          : 'System fallback';
  }
  schedule: DigestSchedule = { local_time: '09:00', weekday: 0, day_of_month: 1 };
  ngOnChanges(changes: SimpleChanges) {
    if (changes['preferences']) {
      this.rules = this.preferences?.rules.map((rule) => ({ ...rule })) ?? [];
      this.digest = this.preferences?.digest ?? 'off';
      this.notificationLocale = this.preferences?.notification_locale ?? '';
      this.adminSummaries =
        this.preferences?.admin_summaries === true
          ? 'on'
          : this.preferences?.admin_summaries === false
            ? 'off'
            : 'inherit';
      this.schedule = {
        ...(this.preferences?.schedule ?? { local_time: '09:00', weekday: 0, day_of_month: 1 }),
      };
      this.validation.set('');
    }
  }
  matchingSchedulePreview() {
    const value = this.schedulePreview;
    return value &&
      value.digest === this.digest &&
      value.schedule.local_time === this.schedule.local_time &&
      value.schedule.weekday === this.schedule.weekday &&
      value.schedule.day_of_month === this.schedule.day_of_month
      ? value
      : null;
  }
  digestLabel(value: string) {
    return value === 'monthly'
      ? 'Monthly'
      : value === 'daily'
        ? 'Daily'
        : value === 'weekly'
          ? 'Weekly'
          : 'Off';
  }
  save(preview = false) {
    const input = this.buildInput();
    if (input) (preview ? this.previewRequested : this.saved).emit(input);
  }
  private buildInput(): NotificationPreferencesUpdate | null {
    if (!this.preferences || this.pending) return null;
    if (!this.preferences.allowed_digests.includes(this.digest)) {
      this.validation.set('Choose an available digest schedule.');
      return null;
    }
    if (
      !/^(?:[01][0-9]|2[0-3]):[0-5][0-9]$/.test(this.schedule.local_time) ||
      !Number.isInteger(this.schedule.weekday) ||
      this.schedule.weekday < 0 ||
      this.schedule.weekday > 6 ||
      !Number.isInteger(this.schedule.day_of_month) ||
      this.schedule.day_of_month < 1 ||
      this.schedule.day_of_month > 31
    ) {
      this.validation.set('Choose a valid local time and calendar day.');
      return null;
    }
    this.validation.set('');
    return this.draftInput();
  }
  private draftInput(): NotificationPreferencesUpdate | null {
    if (!this.preferences) return null;
    const rules = this.preferences.rules.map((original) => {
      const draft = this.rules.find((rule) => rule.kind === original.kind) ?? original;
      return {
        kind: original.kind,
        inbox: original.required ? original.inbox : draft.inbox,
        email: original.required || !original.email_available ? original.email : draft.email,
      };
    });
    return {
      expected_revision: this.preferences.revision,
      admin_summaries: this.preferences.admin_summaries_available
        ? this.adminSummaries === 'inherit'
          ? null
          : this.adminSummaries === 'on'
        : (this.preferences.admin_summaries ?? null),
      notification_locale: this.notificationLocale || null,
      rules,
      digest: this.digest,
      schedule: { ...this.schedule },
    };
  }
}
