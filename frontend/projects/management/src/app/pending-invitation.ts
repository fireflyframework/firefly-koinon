// Copyright 2026 Firefly Software Foundation
// SPDX-License-Identifier: Apache-2.0
import { DOCUMENT } from '@angular/common';
import { Injectable, OnDestroy, inject, signal } from '@angular/core';
const storageKey = 'koinon.pending-invitation';
const retention = 60 * 60 * 1000;
interface PendingLink {
  token: string;
  expiresAt: number;
}
@Injectable({ providedIn: 'root' })
export class PendingInvitation implements OnDestroy {
  private readonly window = inject(DOCUMENT).defaultView;
  private readonly value = signal('');
  readonly token = this.value.asReadonly();
  private timer?: ReturnType<typeof setTimeout>;
  constructor() {
    if (!this.window) return;
    const url = new URL(this.window.location.href);
    const fragment = new URLSearchParams(url.hash.slice(1));
    if (fragment.has('invite')) {
      const tokens = fragment.getAll('invite');
      fragment.delete('invite');
      url.hash = fragment.toString();
      this.window.history.replaceState(
        this.window.history.state,
        '',
        url.pathname + url.search + url.hash,
      );
      this.clear();
      if (tokens.length === 1 && this.validToken(tokens[0]))
        this.retain({ token: tokens[0], expiresAt: Date.now() + retention });
    } else {
      try {
        const raw = this.window.sessionStorage.getItem(storageKey);
        if (raw) {
          const saved: unknown = JSON.parse(raw);
          if (this.validLink(saved)) this.retain(saved);
          else this.clear();
        }
      } catch {
        this.clear();
      }
    }
  }
  private validToken(token: unknown): token is string {
    return typeof token === 'string' && /^[A-Za-z0-9_-]{40,128}$/.test(token);
  }
  private validLink(value: unknown): value is PendingLink {
    if (!value || typeof value !== 'object' || !('token' in value) || !('expiresAt' in value))
      return false;
    return (
      this.validToken(value.token) &&
      typeof value.expiresAt === 'number' &&
      value.expiresAt > Date.now() &&
      value.expiresAt <= Date.now() + retention
    );
  }
  private retain(link: PendingLink) {
    this.value.set(link.token);
    try {
      this.window?.sessionStorage.setItem(storageKey, JSON.stringify(link));
    } catch {
      /* Keep the current link usable when browser storage is unavailable. */
    }
    this.timer = setTimeout(() => this.clear(), Math.max(0, link.expiresAt - Date.now()));
  }
  clear() {
    clearTimeout(this.timer);
    this.value.set('');
    try {
      this.window?.sessionStorage.removeItem(storageKey);
    } catch {
      /* Browser storage may be disabled. */
    }
  }
  ngOnDestroy() {
    clearTimeout(this.timer);
  }
}
