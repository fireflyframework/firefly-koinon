// Copyright 2026 Firefly Software Foundation SPDX-License-Identifier: Apache-2.0
import { DOCUMENT } from '@angular/common';
import { Injectable, OnDestroy, inject, signal } from '@angular/core';
import type { PrimaryDestination } from '@fireflyframework/koinon-angular/workbench';
type AccountSection = 'profile' | 'tokens' | 'applications' | 'notifications' | 'notification-preferences';
const pendingKey = 'koinon.pending-account-navigation';
interface PendingNavigation {
  view: PrimaryDestination;
  accountSection: AccountSection | null;
}
@Injectable({ providedIn: 'root' })
export class AccountNavigation implements OnDestroy {
  private readonly document = inject(DOCUMENT);
  private readonly window = this.document.defaultView;
  private readonly base = new URL('.', this.document.baseURI).pathname;
  readonly section = signal<AccountSection | null>(null);
  readonly view = signal<PrimaryDestination>('library');
  private readonly restore = () => {
    const pathname = this.window?.location.pathname ?? '';
    const path = pathname.startsWith(this.base) ? pathname.slice(this.base.length) : '';
    const section = /^account\/(profile|tokens|applications|notifications|notification-preferences)\/?$/.exec(path)?.[1];
    this.section.set((section as AccountSection) || null);
    this.view.set(
      ['chat', 'activity', 'settings'].includes(path) ? (path as PrimaryDestination) : 'library',
    );
  };
  constructor() {
    this.consumePending();
    this.restore();
    this.window?.addEventListener('popstate', this.restore);
  }
  retainForSignIn() {
    const navigation: PendingNavigation = {
      view: this.section() ? 'library' : this.view(),
      accountSection: this.section(),
    };
    try {
      if (this.validPending(navigation))
        this.window?.sessionStorage.setItem(pendingKey, JSON.stringify(navigation));
    } catch {
      // Sign-in remains available when tab storage is disabled.
    }
  }
  clearPending() {
    try {
      this.window?.sessionStorage.removeItem(pendingKey);
    } catch {
      // Browser policy may disable tab storage.
    }
  }
  private validPending(value: unknown): value is PendingNavigation {
    return (
      !!value &&
      typeof value === 'object' &&
      Object.keys(value).length === 2 &&
      'view' in value &&
      'accountSection' in value &&
      typeof value.view === 'string' &&
      ['library', 'chat', 'activity', 'settings'].includes(value.view) &&
      (value.accountSection === null ||
        (typeof value.accountSection === 'string' &&
          ['profile', 'tokens', 'applications', 'notifications', 'notification-preferences'].includes(value.accountSection)))
    );
  }
  private consumePending() {
    if (!this.window) return;
    let saved: unknown;
    try {
      const raw = this.window.sessionStorage.getItem(pendingKey);
      this.clearPending();
      if (!raw) return;
      saved = JSON.parse(raw);
    } catch {
      return;
    }
    if (!this.validPending(saved)) return;
    const url = new URL(this.window.location.href);
    const fragment = new URLSearchParams(url.hash.slice(1));
    if (url.pathname !== this.base || fragment.has('invite') || fragment.has('share')) return;
    const path = saved.accountSection
      ? 'account/' + saved.accountSection
      : saved.view === 'library'
        ? ''
        : saved.view;
    url.pathname = this.base + path;
    if (url.href !== this.window.location.href)
      this.window.history.replaceState(
        this.window.history.state,
        '',
        url.pathname + url.search + url.hash,
      );
  }
  open(section: AccountSection) {
    this.section.set(section);
    this.write('account/' + section);
  }
  navigate(view: PrimaryDestination) {
    this.section.set(null);
    this.view.set(view);
    this.write(view === 'library' ? '' : view);
  }
  private write(path: string) {
    if (!this.window) return;
    const url = new URL(this.window.location.href);
    url.pathname = this.base + path;
    if (url.href !== this.window.location.href)
      this.window.history.pushState(
        this.window.history.state,
        '',
        url.pathname + url.search + url.hash,
      );
  }
  ngOnDestroy() {
    this.window?.removeEventListener('popstate', this.restore);
  }
}
