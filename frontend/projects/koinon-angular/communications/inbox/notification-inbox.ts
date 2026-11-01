// Copyright 2026 Firefly Software Foundation SPDX-License-Identifier: Apache-2.0
import { ChangeDetectionStrategy, Component, EventEmitter, Input, Output } from '@angular/core';
import { FormsModule } from '@angular/forms';
import {
  KoinonBadge,
  KoinonButton,
  KoinonDatePipe,
  KoinonIcon,
  KoinonPagination,
  KoinonSkeleton,
  KoinonTextPipe,
} from '@fireflyframework/koinon-angular';
import type {
  CommunicationEvent,
  NotificationFilter,
  NotificationPage,
  NotificationTarget,
  OwnNotificationView,
} from '@fireflyframework/koinon-angular/communications';
import { registerKoinonSpanish } from '@fireflyframework/koinon-angular/workbench';
import { NOTIFICATION_SPANISH } from './spanish';
registerKoinonSpanish(NOTIFICATION_SPANISH);

@Component({
  selector: 'ffk-notification-inbox',
  imports: [
    FormsModule,
    KoinonBadge,
    KoinonButton,
    KoinonDatePipe,
    KoinonIcon,
    KoinonPagination,
    KoinonSkeleton,
    KoinonTextPipe,
  ],
  templateUrl: './notification-inbox.html',
  styleUrl: './notification-inbox.scss',
  changeDetection: ChangeDetectionStrategy.OnPush,
})
export class KoinonNotificationInbox {
  @Input() page: NotificationPage | null = null;
  @Input() loading = false;
  @Input() readPending: string | null = null;
  @Input() error = '';
  @Output() filterChanged = new EventEmitter<NotificationFilter>();
  @Output() readRequested = new EventEmitter<string>();
  @Output() targetRequested = new EventEmitter<NotificationTarget>();
  @Output() preferencesRequested = new EventEmitter<void>();
  read: NotificationFilter['read'] = 'all';
  kind: CommunicationEvent | '' = '';
  pageSize = 25;
  readonly kinds: { id: CommunicationEvent; label: string }[] = [
    { id: 'invitation', label: 'Invitations' },
    { id: 'access_granted', label: 'Access granted' },
    { id: 'role_changed', label: 'Role changes' },
    { id: 'access_removed', label: 'Access removed' },
    { id: 'digest', label: 'Usage summary' },
    { id: 'security', label: 'Security and access' },
    { id: 'welcome', label: 'Welcome' },
  ];
  applyFilters() {
    this.changePage(1);
  }
  changePage(page: number) {
    if (!this.loading)
      this.filterChanged.emit({ page, page_size: this.pageSize, read: this.read, kind: this.kind });
  }
  changePageSize(size: number) {
    this.pageSize = size;
    this.changePage(1);
  }
  hasTarget(notice: OwnNotificationView) {
    return (
      ['invitation', 'workspace', 'access'].includes(notice.target.kind) &&
      /^[A-Za-z0-9_-]{1,128}$/.test(notice.target.id)
    );
  }
  open(notice: OwnNotificationView) {
    if (this.hasTarget(notice)) this.targetRequested.emit({ ...notice.target });
  }
  markRead(notice: OwnNotificationView) {
    if (!notice.read_at && !this.readPending) this.readRequested.emit(notice.id);
  }
  targetLabel(notice: OwnNotificationView) {
    return notice.target.kind === 'invitation'
      ? 'Review invitation'
      : notice.target.kind === 'workspace'
        ? 'Open workspace'
        : 'View access';
  }
}
