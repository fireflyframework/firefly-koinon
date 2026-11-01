// Copyright 2026 Firefly Software Foundation SPDX-License-Identifier: Apache-2.0
import {
  AfterViewInit,
  ChangeDetectionStrategy,
  Component,
  ElementRef,
  EventEmitter,
  Input,
  Output,
  inject,
} from '@angular/core';
import { CdkMenu, CdkMenuItem } from '@angular/cdk/menu';
import { KoinonTextPipe } from '../foundations/i18n';
import { KoinonIcon } from '../atoms/icon';
@Component({
  selector: 'ffk-account-menu',
  imports: [CdkMenu, CdkMenuItem, KoinonTextPipe, KoinonIcon],
  template: `<div class="account-menu" cdkMenu [attr.aria-label]="'Account menu' | ffkText">
    <div class="account-summary">
      <strong>{{ displayName || ('Your account' | ffkText) }}</strong
      ><small>{{ roleLabel | ffkText }}</small>
    </div>
    <button cdkMenuItem (click)="accountRequested.emit('profile')">
      <ffk-icon name="users" />{{ 'Your account' | ffkText }}
    </button>
    <button cdkMenuItem (click)="accountRequested.emit('tokens')">
      <ffk-icon name="shield" />{{ 'API tokens' | ffkText }}
    </button>
    <button cdkMenuItem (click)="accountRequested.emit('applications')">
      <ffk-icon name="link" />{{ 'Authorized applications' | ffkText }}
    </button>
    @if (canConfigure) {
      <button cdkMenuItem (click)="destinationRequested.emit('activity')">
        <ffk-icon name="history" />{{ 'Activity' | ffkText }}
      </button>
      <button cdkMenuItem (click)="destinationRequested.emit('settings')">
        <ffk-icon name="settings" />{{ 'Settings' | ffkText }}
      </button>
    }
    <button cdkMenuItem (click)="themeRequested.emit()">
      <ffk-icon [name]="theme === 'light' ? 'moon' : 'sun'" />{{
        (theme === 'light' ? 'Use dark theme' : 'Use light theme') | ffkText
      }}
    </button>
    <button cdkMenuItem (click)="signOutRequested.emit()">
      <ffk-icon name="logout" />{{ 'Sign out' | ffkText }}
    </button>
  </div>`,
  styleUrl: './account-menu.scss',
  host: { style: 'display:contents' },
  changeDetection: ChangeDetectionStrategy.OnPush,
})
export class KoinonAccountMenu implements AfterViewInit {
  @Input() displayName = '';
  @Input() roleLabel = 'Member';
  @Input() theme: 'light' | 'dark' = 'light';
  @Input() canConfigure = false;
  @Output() destinationRequested = new EventEmitter<'activity' | 'settings'>();
  @Output() accountRequested = new EventEmitter<'profile' | 'tokens' | 'applications'>();
  @Output() themeRequested = new EventEmitter<void>();
  @Output() signOutRequested = new EventEmitter<void>();
  private readonly host = inject<ElementRef<HTMLElement>>(ElementRef);
  ngAfterViewInit() {
    this.host.nativeElement.querySelector<HTMLElement>('[role=menuitem]')?.focus();
  }
}
