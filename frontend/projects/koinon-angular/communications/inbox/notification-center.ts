// Copyright 2026 Firefly Software Foundation SPDX-License-Identifier: Apache-2.0
import {
  ChangeDetectionStrategy,
  Component,
  EventEmitter,
  Input,
  OnChanges,
  Output,
  effect,
  inject,
  untracked,
} from '@angular/core';
import {
  KoinonCommunicationsSession,
  communicationRules,
} from '@fireflyframework/koinon-angular/communications/runtime';
import { KoinonEmailInvitationAcceptance } from '@fireflyframework/koinon-angular/communications/invitations';
import type {
  ActivityEmailPreviewInput,
  EmailPreview,
  DigestSchedulePreview,
  Membership,
} from '@fireflyframework/koinon-sdk';
import type {
  NotificationFilter,
  NotificationPage,
  NotificationPreferencesView,
  NotificationPreferencesUpdate,
  NotificationTarget,
} from '@fireflyframework/koinon-angular/communications';
import { KoinonNotificationInbox } from './notification-inbox';
import { KoinonNotificationRefresh } from '@fireflyframework/koinon-angular/communications';
import { KoinonNotificationPreferences } from '@fireflyframework/koinon-angular/communications/preferences';
@Component({
  selector: 'ffk-notification-center',
  imports: [
    KoinonNotificationInbox,
    KoinonNotificationPreferences,
    KoinonEmailInvitationAcceptance,
  ],
  providers: [KoinonCommunicationsSession],
  template: ` @if (invitation(); as id) {
      @defer (when !!invitation()) {
        <ffk-email-invitation-acceptance
          [invitationId]="id"
          (closed)="invitation.set('')"
          (accepted)="accepted($event)"
          (signInRequested)="session.facade.authRequired.set(true)"
          (switchAccountRequested)="signOut()"
        />
      }
    } @else if (mode === 'notification-preferences') {
      @defer (when mode==='notification-preferences') {
        <ffk-notification-preferences
          [showHeading]="false"
          [preferences]="preferences()"
          [pending]="session.pending()"
          [error]="session.error()"
          [notice]="notice()"
          [schedulePreview]="preview()"
          [emailPreview]="emailPreview()"
          [emailPreviewPending]="session.pending()"
          [canPreviewEmail]="!!session.facade.tenantId()"
          (emailPreviewRequested)="previewEmail($event)"
          (previewRequested)="previewSchedule($event)"
          (saved)="save($event)"
          (backRequested)="changeMode('notifications')"
        />
      }
    } @else {
      <ffk-notification-inbox
        [showHeading]="false"
        [page]="page()"
        [loading]="session.pending()"
        [error]="session.error()"
        [readPending]="readPending()"
        (filterChanged)="load($event)"
        (readRequested)="markRead($event)"
        (targetRequested)="openTarget($event)"
        (preferencesRequested)="changeMode('notification-preferences')"
      />
    }`,
  changeDetection: ChangeDetectionStrategy.OnPush,
})
export class KoinonNotificationCenter implements OnChanges {
  readonly session = inject(KoinonCommunicationsSession);
  private readonly updates = inject(KoinonNotificationRefresh);
  readonly readPending = this.session.state<string | null>(null);
  @Input() actions?: {
    modeChanged: (mode: 'notifications' | 'notification-preferences') => void;
    signOut: () => void;
    target: (target: NotificationTarget) => void;
  };
  changeMode(mode: 'notifications' | 'notification-preferences') {
    this.modeChange.emit(mode);
    this.actions?.modeChanged(mode);
  }
  signOut() {
    this.signOutRequested.emit();
    this.actions?.signOut();
  }
  @Input() mode: 'notifications' | 'notification-preferences' = 'notifications';
  @Output() modeChange = new EventEmitter<'notifications' | 'notification-preferences'>();
  @Output() signOutRequested = new EventEmitter<void>();
  @Output() targetRequested = new EventEmitter<NotificationTarget>();
  readonly page = this.session.state<NotificationPage | null>(null);
  readonly preferences = this.session.state<NotificationPreferencesView | null>(null);
  readonly preview = this.session.state<DigestSchedulePreview | null>(null);
  readonly emailPreview = this.session.state<EmailPreview | null>(null);
  readonly notice = this.session.state('');
  readonly invitation = this.session.state('');
  private filter: NotificationFilter = { page: 1, page_size: 25, read: 'all', kind: '' };
  constructor() {
    effect(() => {
      this.session.key();
      untracked(() => {
        this.page.set(null);
        this.preferences.set(null);
        this.preview.set(null);
        this.emailPreview.set(null);
        this.invitation.set('');
        this.notice.set('');
        void this.refresh();
      });
    });
  }
  ngOnChanges() {
    void this.refresh();
  }
  private refresh() {
    return this.mode === 'notification-preferences'
      ? this.loadPreferences()
      : this.load(this.filter);
  }
  async load(filter: NotificationFilter) {
    this.filter = filter;
    await this.session.run(
      'inbox',
      (signal) =>
        this.session.api!.notifications.list(
          {
            page: filter.page,
            page_size: filter.page_size,
            read: filter.read,
            ...(filter.kind ? { event_kind: filter.kind } : {}),
          },
          { signal },
        ),
      (value) =>
        this.page.set({
          ...value,
          items: value.items.map((item) => ({
            ...item,
            target: { ...item.target, id: item.target.id ?? '' },
          })),
        }),
    );
  }
  async markRead(id: string) {
    if (this.session.pending()) return;
    const key = this.session.key();
    this.readPending.set(id);
    const result = await this.session.run(
      'read',
      (signal) => this.session.api!.notifications.markRead(id, { signal }),
      (value) =>
        this.page.update((page) =>
          page
            ? {
                ...page,
                items: page.items.map((item) =>
                  item.id === value.id ? { ...item, read_at: value.read_at } : item,
                ),
              }
            : null,
        ),
    );
    if (this.session.key() !== key) return;
    this.readPending.set(null);
    if (result) {
      this.updates.invalidate();
      if (this.filter.read === 'unread') await this.load({ ...this.filter, page: 1 });
    }
  }
  async loadPreferences() {
    await this.session.run(
      'preferences',
      (signal) => this.session.api!.notifications.preferences({ signal }),
      (value) => this.preferences.set({ ...value, rules: communicationRules(value.rules) }),
    );
  }
  async save(input: NotificationPreferencesUpdate) {
    this.notice.set('');
    await this.session.run(
      'save',
      (signal) => this.session.api!.notifications.updatePreferences(input, { signal }),
      (value) => {
        this.preferences.set({ ...value, rules: communicationRules(value.rules) });
        this.preview.set(null);
        this.emailPreview.set(null);
        this.notice.set('Notification preferences saved.');
      },
    );
  }
  async previewSchedule(input: NotificationPreferencesUpdate) {
    this.preview.set(null);
    await this.session.run(
      'calendar',
      (signal) => this.session.api!.notifications.previewPreferences(input, { signal }),
      (value) => this.preview.set(value),
    );
  }
  async previewEmail(input: Omit<ActivityEmailPreviewInput, 'tenant_id'>) {
    this.emailPreview.set(null);
    await this.session.run(
      'email-preview',
      (signal) =>
        this.session.api!.notifications.previewEmail(
          { ...input, tenant_id: this.session.facade.tenantId() },
          { signal },
        ),
      (value) => this.emailPreview.set(value),
    );
  }
  openTarget(target: NotificationTarget) {
    if (target.kind === 'invitation') this.invitation.set(target.id);
    else {
      this.targetRequested.emit(target);
      this.actions?.target(target);
    }
  }
  async accepted(membership: Membership) {
    this.invitation.set('');
    await this.session.facade.bootstrap(membership.tenant_id);
    void this.load(this.filter);
  }
}
