// Copyright 2026 Firefly Software Foundation SPDX-License-Identifier: Apache-2.0
import {
  ChangeDetectionStrategy,
  Component,
  DestroyRef,
  EventEmitter,
  Input,
  Output,
  effect,
  inject,
  untracked,
} from '@angular/core';
import { KoinonNotificationTrigger } from '@fireflyframework/koinon-angular/communications';
import { KoinonCommunicationsSession } from './session';
@Component({
  selector: 'ffk-notification-center-trigger',
  imports: [KoinonNotificationTrigger],
  providers: [KoinonCommunicationsSession],
  template: `<ffk-notification-trigger [unread]="unread()" (opened)="open()" />`,
  changeDetection: ChangeDetectionStrategy.OnPush,
})
export class KoinonNotificationCenterTrigger {
  readonly session = inject(KoinonCommunicationsSession);
  @Input() actions?: { opened: () => void };
  open() {
    this.opened.emit();
    this.actions?.opened();
  }
  @Output() opened = new EventEmitter<void>();
  readonly unread = this.session.state<number | null>(null);
  constructor() {
    effect(() => {
      this.session.key();
      untracked(() => {
        this.unread.set(null);
        void this.load();
      });
    });
    const timer = setInterval(() => {
      if (typeof document !== 'undefined' && document.visibilityState === 'visible')
        void this.load();
    }, 60000);
    inject(DestroyRef).onDestroy(() => clearInterval(timer));
  }
  private async load() {
    if (!this.session.facade.context()?.subject || !this.session.api) return;
    await this.session.run(
      'count',
      (signal) => this.session.api!.notifications.unreadCount({ signal }),
      (value) => this.unread.set(value.unread),
    );
  }
}
