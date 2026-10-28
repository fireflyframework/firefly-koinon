// Copyright 2026 Firefly Software Foundation SPDX-License-Identifier: Apache-2.0
import { Component, inject, signal } from '@angular/core';
import { DOCUMENT } from '@angular/common';
import { KoinonWorkbench } from '@fireflyframework/koinon-angular';
import { SessionService } from './session.service';
import { PendingInvitation } from './pending-invitation';
import { PendingShare } from './pending-share';
@Component({
  selector: 'app-root',
  imports: [KoinonWorkbench],
  template: `@if (session.error()) {
      <div class="session-error" role="alert">{{ session.error() }}</div>
    }
    <ffk-workbench
      [managementBaseUrl]="managementBaseUrl"
      [tenantId]="entryTenant"
      [sharedConversationId]="share.shareId()"
      (sharedConversationDismissed)="share.clear()"
      [invitationToken]="invitation.token()"
      (invitationAccepted)="invitation.clear()"
      (invitationDismissed)="invitation.clear()"
      [theme]="theme()"
      (themeChange)="setTheme($event)"
      (authenticationRequired)="session.signIn()"
      (signOutRequested)="signOut()"
    />`,
  styles: `
    :host {
      display: block;
    }
    .session-error {
      background: #f3f1eb;
      border-bottom: 2px solid #855414;
      color: #272820;
      padding: 12px 24px;
      font:
        13px 'Manrope Variable',
        sans-serif;
    }
  `,
})
export class App {
  readonly managementBaseUrl = new URL('.', inject(DOCUMENT).baseURI).toString();
  readonly session = inject(SessionService);
  readonly invitation = inject(PendingInvitation);
  readonly share = inject(PendingShare);
  readonly entryTenant = this.share.tenantId();
  readonly theme = signal<'light' | 'dark'>(this.initialTheme());
  private initialTheme(): 'light' | 'dark' {
    const saved = localStorage.getItem('koinon-theme');
    return saved === 'light' || saved === 'dark'
      ? saved
      : matchMedia('(prefers-color-scheme:dark)').matches
        ? 'dark'
        : 'light';
  }
  setTheme(theme: 'light' | 'dark'): void {
    this.theme.set(theme);
    localStorage.setItem('koinon-theme', theme);
    document.documentElement.style.colorScheme = theme;
  }
  async signOut(): Promise<void> {
    this.invitation.clear();
    this.share.clear();
    if (await this.session.signOut()) window.location.assign('/');
  }
}
