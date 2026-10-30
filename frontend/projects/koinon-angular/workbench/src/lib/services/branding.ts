// Copyright 2026 Firefly Software Foundation
// SPDX-License-Identifier: Apache-2.0
import { Injectable, PendingTasks, computed, effect, inject, signal } from '@angular/core';
import type { BrandingValues, OrganizationBranding } from '@fireflyframework/koinon-sdk';
import { KoinonClientContext } from './client-context';
import { KoinonFacade } from '../koinon-facade';
import { DEFAULT_BRANDING, resolveBranding, validateBranding } from './branding-values';
@Injectable({ providedIn: 'root' })
export class KoinonBranding {
  private readonly clients = inject(KoinonClientContext);
  private readonly facade = inject(KoinonFacade);
  private readonly tasks = inject(PendingTasks);
  private epoch = 0;
  private defaultEpoch = 0;
  private key = '';
  readonly assetBase = signal('/assets/brand');
  readonly defaultsReady = signal(false);
  readonly defaultsError = signal(false);
  private defaultsRequest?: { revision: number; promise: Promise<void> };
  readonly deployment = signal<BrandingValues>(DEFAULT_BRANDING);
  readonly current = signal<OrganizationBranding | null>(null);
  readonly override = signal<BrandingValues | null>(null);
  readonly value = computed(() =>
    resolveBranding(this.override() ?? this.current()?.branding ?? this.deployment()),
  );
  constructor() {
    effect(() => {
      const f = this.facade,
        revision = this.clients.revision();
      const tenant = f.context() && !f.authRequired() ? f.tenantId() : '';
      const key = revision + ':' + tenant + ':' + (f.context()?.subject || '');
      if (key === this.key) return;
      this.key = key;
      const epoch = ++this.epoch;
      this.current.set(null);
      this.tasks.run(async () => {
        try {
          const client = this.clients.get();
          if (tenant) {
            const settings = await client.branding.get(tenant);
            if (
              epoch === this.epoch &&
              settings.tenant_id === tenant &&
              !validateBranding(settings.branding).length
            )
              this.current.set(settings);
          }
        } catch {
          /* The default identity remains available when organization settings are inaccessible. */
        }
      });
    });
  }
  loadDefaults(force = false): Promise<void> {
    const revision = this.clients.revision();
    if (!force && this.defaultsRequest?.revision === revision) return this.defaultsRequest.promise;
    const epoch = ++this.defaultEpoch;
    this.defaultsReady.set(false);
    this.defaultsError.set(false);
    if (this.defaultsRequest?.revision !== revision) this.deployment.set(DEFAULT_BRANDING);
    const promise = (async () => {
      try {
        const value = await this.clients.get().branding.defaults();
        if (epoch !== this.defaultEpoch) return;
        if (validateBranding(value).length) throw new Error('Invalid deployment identity');
        this.deployment.set(value);
        this.defaultsReady.set(true);
      } catch {
        if (epoch === this.defaultEpoch) this.defaultsError.set(true);
      }
    })();
    this.defaultsRequest = { revision, promise };
    return promise;
  }
  setOverride(value: BrandingValues | null) {
    if (value && validateBranding(value).length)
      throw new Error(
        'The embedded identity is invalid. Review its names, images and palette contrast.',
      );
    this.override.set(value);
  }
  accept(value: OrganizationBranding) {
    if (value.tenant_id === this.facade.tenantId() && !validateBranding(value.branding).length) {
      ++this.epoch;
      this.current.set(value);
    }
  }
}
