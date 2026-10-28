// Copyright 2026 Firefly Software Foundation
// SPDX-License-Identifier: Apache-2.0
import { DOCUMENT } from '@angular/common';
import { Injectable, OnDestroy, inject, signal } from '@angular/core';
const storageKey = 'koinon.pending-share';
const retention = 60 * 60 * 1000;
interface PendingShareLink {
  shareId: string;
  tenantId: string;
  expiresAt: number;
}
@Injectable({ providedIn: 'root' })
export class PendingShare implements OnDestroy {
  private readonly window = inject(DOCUMENT).defaultView;
  readonly shareId = signal('');
  readonly tenantId = signal('');
  private timer?: ReturnType<typeof setTimeout>;
  constructor() {
    if (!this.window) return;
    const url = new URL(this.window.location.href);
    const fragment = new URLSearchParams(url.hash.slice(1));
    if (fragment.has('share')) {
      const shares = fragment.getAll('share'),
        tenants = fragment.getAll('tenant');
      fragment.delete('share');
      fragment.delete('tenant');
      url.hash = fragment.toString();
      this.window.history.replaceState(
        this.window.history.state,
        '',
        url.pathname + url.search + url.hash,
      );
      this.clear();
      if (
        shares.length === 1 &&
        tenants.length === 1 &&
        this.identifier(shares[0]) &&
        this.identifier(tenants[0])
      )
        this.retain({
          shareId: shares[0],
          tenantId: tenants[0],
          expiresAt: Date.now() + retention,
        });
    } else {
      try {
        const raw = this.window.sessionStorage.getItem(storageKey);
        if (raw) {
          const saved: unknown = JSON.parse(raw);
          if (this.valid(saved)) this.retain(saved);
          else this.clear();
        }
      } catch {
        this.clear();
      }
    }
  }
  private identifier(value: unknown): value is string {
    return typeof value === 'string' && /^[A-Za-z0-9][A-Za-z0-9_-]{0,127}$/.test(value);
  }
  private valid(value: unknown): value is PendingShareLink {
    if (
      !value ||
      typeof value !== 'object' ||
      !('shareId' in value) ||
      !('tenantId' in value) ||
      !('expiresAt' in value)
    )
      return false;
    return (
      this.identifier(value.shareId) &&
      this.identifier(value.tenantId) &&
      typeof value.expiresAt === 'number' &&
      value.expiresAt > Date.now() &&
      value.expiresAt <= Date.now() + retention
    );
  }
  private retain(link: PendingShareLink) {
    this.shareId.set(link.shareId);
    this.tenantId.set(link.tenantId);
    try {
      this.window?.sessionStorage.setItem(storageKey, JSON.stringify(link));
    } catch {
      /* Retain only in memory when storage is unavailable. */
    }
    this.timer = setTimeout(() => this.clear(), Math.max(0, link.expiresAt - Date.now()));
  }
  clear() {
    clearTimeout(this.timer);
    this.shareId.set('');
    this.tenantId.set('');
    try {
      this.window?.sessionStorage.removeItem(storageKey);
    } catch {
      /* Storage may be disabled. */
    }
  }
  ngOnDestroy() {
    clearTimeout(this.timer);
  }
}
