// Copyright 2026 Firefly Software Foundation SPDX-License-Identifier: Apache-2.0
import { Component, inject, signal } from '@angular/core';
import { DOCUMENT } from '@angular/common';
import { KoinonFontLoader, KoinonWorkbench } from '@fireflyframework/koinon-angular/workbench';
import { SessionService } from './session.service';
import { SessionNotice } from './session-notice';
import type { BrandingValues } from '@fireflyframework/koinon-sdk';
import { PendingInvitation } from './pending-invitation';
import { PendingShare } from './pending-share';
import { AccountNavigation } from './account-navigation';
import { OrganizationSelection } from './organization-selection';
import {readNavigationPreference,saveNavigationPreference} from './navigation-preference';
@Component({
  selector: 'app-root',
  imports: [KoinonWorkbench, SessionNotice],
  providers: [KoinonFontLoader],
  template: `@if (session.error()) {
      <div class="session-error" role="alert">{{ session.error() }}</div>
    }
    <ng-template #sessionNotice>
      @defer (on idle) {
        <app-session-notice [workbench]="workbench" />
      }
    </ng-template>
    <ffk-workbench
      #workbench
      [sessionNotice]="sessionNotice"
      [managementBaseUrl]="managementBaseUrl"
      (brandingChange)="applyIdentity($event)"
      [navigationCollapsed]="navigationCollapsed()"
      (navigationCollapsedChange)="setNavigationCollapsed($event)"
      [view]="navigation.view()"
      (viewChange)="navigation.navigate($event)"
      [accountSection]="navigation.section()"
      (accountSectionChange)="$event ? navigation.open($event) : navigation.section.set(null)"
      [tenantId]="entryTenant"
      (contextChange)="organization.remember($event)"
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
        13px var(--ffk-font, system-ui),
        sans-serif;
    }
  `,
})
export class App {
  private readonly document = inject(DOCUMENT);
  private readonly font = inject(KoinonFontLoader);
  applyIdentity(value: BrandingValues) {
    this.font.load('/assets/brand', value.font_family);
    this.document.title =
      value.product_name === 'koinon' ? 'firefly koinon' : value.product_name || 'koinon';
    const icon = this.document.querySelector<HTMLLinkElement>('link[rel="icon"]');
    if (icon) {
      icon.href =
        value.favicon ||
        (value.product_name === 'koinon'
          ? '/assets/brand/logos/koinon-symbol-color.svg'
          : 'data:image/svg+xml,%3Csvg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 32 32"%3E%3Ccircle cx="16" cy="16" r="12" fill="%2362645b"/%3E%3C/svg%3E');
      icon.type = value.favicon
        ? value.favicon.slice(5, value.favicon.indexOf(';'))
        : 'image/svg+xml';
    }
  }
  readonly managementBaseUrl = new URL('.', inject(DOCUMENT).baseURI).toString();
  readonly session = inject(SessionService);
  readonly invitation = inject(PendingInvitation);
  readonly share = inject(PendingShare);
  readonly navigation = inject(AccountNavigation);
  readonly organization = inject(OrganizationSelection);
  readonly entryTenant = this.share.tenantId();
  readonly theme = signal<'light' | 'dark'>(this.initialTheme());
  readonly navigationCollapsed = signal(readNavigationPreference(this.document.defaultView));
  setNavigationCollapsed(value:boolean) {this.navigationCollapsed.set(value);saveNavigationPreference(this.document.defaultView,value);}
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
    if (await this.session.signOut()) {
      this.invitation.clear();
      this.share.clear();
      window.location.assign('/');
    }
  }
}
