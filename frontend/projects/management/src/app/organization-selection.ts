// Copyright 2026 Firefly Software Foundation SPDX-License-Identifier: Apache-2.0
import { DOCUMENT } from '@angular/common';
import { inject, Injectable } from '@angular/core';
import type { ContextResponse } from '@fireflyframework/koinon-sdk';
import type { KoinonScope } from '@fireflyframework/koinon-angular/workbench';

@Injectable({ providedIn: 'root' })
export class OrganizationSelection {
  private readonly document = inject(DOCUMENT);
  private readonly window = this.document.defaultView;
  private readonly base = new URL('.', this.document.baseURI).pathname;
  private readonly selections = new Map<string, string>();
  private context?: ContextResponse;

  resolve(context: ContextResponse, requested: string): string {
    this.context = context;
    const key = this.key(context);
    const preferred = requested || this.selections.get(key) || this.read(key);
    const authorized = context.tenants.find((tenant) => tenant.id === preferred)?.id;
    if (preferred && !authorized) this.remove(key);
    const selected = authorized || context.tenants[0]?.id || '';
    this.selections.set(key, selected);
    return selected;
  }
  remember(scope: KoinonScope): void {
    const context = this.context;
    if (!context?.tenants.some((tenant) => tenant.id === scope.tenantId)) return;
    const key = this.key(context);
    this.selections.set(key, scope.tenantId);
    try {
      this.window?.sessionStorage.setItem(key, JSON.stringify(scope.tenantId));
    } catch {
      // The current tab can still retry its selection when storage is disabled.
    }
  }
  private key(context: ContextResponse): string {
    return 'koinon.organization:' + this.base + ':' + encodeURIComponent(context.subject);
  }
  private read(key: string): string {
    try {
      const raw = this.window?.sessionStorage.getItem(key);
      if (!raw) return '';
      const saved: unknown = JSON.parse(raw);
      if (typeof saved === 'string' && /^[A-Za-z0-9][A-Za-z0-9_-]{0,127}$/.test(saved))
        return saved;
    } catch {
      // Invalid state and browser storage policy cannot choose an organization.
    }
    this.remove(key);
    return '';
  }
  private remove(key: string): void {
    try {
      this.window?.sessionStorage.removeItem(key);
    } catch {
      // Storage may be disabled.
    }
  }
}
