// Copyright 2026 Firefly Software Foundation
// SPDX-License-Identifier: Apache-2.0
import {
  ChangeDetectionStrategy,
  Component,
  DestroyRef,
  computed,
  effect,
  inject,
  signal,
  untracked,
} from '@angular/core';
import { registerKoinonSpanish } from '@fireflyframework/koinon-angular/workbench';
import {
  KoinonBadge,
  KoinonButton,
  KoinonClientContext,
  KoinonDatePipe,
  KoinonFacade,
  KoinonTextPipe,
} from '@fireflyframework/koinon-angular';
import { UploadObservationLoop } from '@fireflyframework/koinon-angular/workbench/availability';
import { KoinonError } from '@fireflyframework/koinon-sdk';
import { statusTone } from '@fireflyframework/koinon-angular/workbench/core';
import { activityAdministrator } from './activity-access';
import { createAvailabilityApi } from '@fireflyframework/koinon-sdk/availability';
import type { ProcessingResponse } from '@fireflyframework/koinon-sdk/availability';
registerKoinonSpanish({
  'Current jobs and recorded content attempts. Earlier unrecorded stages are unavailable.':
    'Trabajos actuales e intentos de contenido registrados. Las etapas anteriores sin registro no están disponibles.',
  'Text remains available from the observed version':
    'El texto de la versión observada sigue disponible',
  'No recorded processing was returned for this page.':
    'No se han devuelto procesos registrados para esta página.',
  'Processing observations could not be verified.':
    'No se han podido verificar los estados de procesamiento.',
  'Status not verified': 'Estado sin verificar',
  'Processing failed': 'Error de procesamiento',
});
@Component({
  selector: 'ffk-processing-history',
  imports: [KoinonBadge, KoinonButton, KoinonTextPipe, KoinonDatePipe],
  template: `<section aria-label="Current knowledge processing">
    <h2>{{ 'Knowledge processing' | ffkText }}</h2>
    <p>
      {{
        'Current jobs and recorded content attempts. Earlier unrecorded stages are unavailable.'
          | ffkText
      }}
    </p>
    @if (error()) {
      <p role="status">{{ error() | ffkText }}</p>
      @if (!denied) {
        <ffk-button variant="quiet" icon="refresh" (click)="load(page())" [loading]="pending()">{{
          'Try again' | ffkText
        }}</ffk-button>
      }
    }
    <div class="records">
      @for (row of current()?.items || []; track row.id) {
        <article>
          <strong>{{ name(row.resource_id) }}</strong>
          <p>{{ row.operation }}</p>
          <ffk-badge [tone]="stale() ? 'attention' : tone(row.state)">{{
            (stale() ? 'Status not verified' : label(row.state)) | ffkText
          }}</ffk-badge>
          @if (!stale() && row.availability.read?.state === 'ready') {
            <p>{{ 'Text remains available from the observed version' | ffkText }}</p>
          }
          @if (!stale() && row.availability.search?.state === 'ready') {
            <p>{{ 'Searchable' | ffkText }}</p>
          }
          <small>{{ row.updated_at | ffkDate: undefined : 'datetime' }}</small>
        </article>
      } @empty {
        <p>{{ 'No recorded processing was returned for this page.' | ffkText }}</p>
      }
    </div>
    @if (page() > 1) {
      <ffk-button (click)="load(page() - 1)" [disabled]="pending()">{{
        'Previous' | ffkText
      }}</ffk-button>
    }
    @if (current()?.next_page; as next) {
      <ffk-button (click)="load(next)" [disabled]="pending()">{{ 'Next' | ffkText }}</ffk-button>
    }
  </section>`,
  styles: `
    section {
      margin-top: 32px;
    }
    .records {
      display: grid;
      gap: 12px;
      margin: 16px 0;
    }
    article {
      padding: 16px;
      border: 1px solid var(--ui-line);
      border-radius: 8px;
      overflow-wrap: anywhere;
    }
    p {
      color: var(--ui-muted);
      font-size: 13px;
    }
    small {
      color: var(--ui-muted);
    }
  `,
  changeDetection: ChangeDetectionStrategy.OnPush,
})
export class KoinonProcessingHistory {
  readonly tone = statusTone;
  private facade = inject(KoinonFacade);
  private clients = inject(KoinonClientContext);
  private request?: AbortController;
  private result = signal<{ key: string; value: ProcessingResponse } | null>(null);
  readonly page = signal(1);
  readonly pending = signal(false);
  readonly error = signal('');
  readonly stale = signal(false);
  protected denied = false;
  private alive = true;
  private expiry?: ReturnType<typeof setTimeout>;
  readonly now = signal(Date.now());
  readonly allowed = computed(
    () =>
      activityAdministrator(this.facade.context(), this.facade.tenantId(), this.now()) &&
      this.facade.tenantPermissions().has('jobs:manage'),
  );
  private identity: object | null = null;
  private epoch = 0;
  readonly key = computed(() => {
    const context = this.facade.context();
    if (context !== this.identity) {
      this.identity = context;
      ++this.epoch;
    }
    return JSON.stringify([
      this.epoch,
      this.clients.revision(),
      this.facade.tenantId(),
      this.facade.workspaceId(),
      this.allowed(),
    ]);
  });
  readonly current = computed(() =>
    this.allowed() && this.result()?.key === this.key() ? this.result()!.value : null,
  );
  private readonly visible = signal(
    typeof document === 'undefined' || document.visibilityState !== 'hidden',
  );
  private readonly polling = new UploadObservationLoop({
    active: () =>
      this.alive &&
      !this.denied &&
      !this.pending() &&
      !!this.clients.getTransport() &&
      !!this.facade.context()?.subject &&
      !!this.facade.tenantId() &&
      this.allowed(),
    visible: () => this.visible(),
    interval: () =>
      this.current()?.items.some(
        (row) =>
          ['queued', 'processing', 'indexing'].includes(row.state) ||
          ['queued', 'processing', 'indexing'].includes(row.availability.phase ?? '') ||
          row.availability.search?.state === 'pending' ||
          row.availability.query?.state === 'pending',
      )
        ? 5000
        : 30000,
    read: async () => {
      await this.load(this.page(), true);
      return !this.error();
    },
  });
  private readonly reenter = () => {
    this.visible.set(document.visibilityState !== 'hidden');
    this.now.set(Date.now());
    this.polling.reset();
  };
  constructor() {
    effect(() => {
      this.now();
      clearTimeout(this.expiry);
      const times = (this.facade.context()?.memberships ?? [])
        .map((grant) => (grant.expires_at ? Date.parse(grant.expires_at) : NaN))
        .filter((time) => time > Date.now());
      if (times.length)
        this.expiry = setTimeout(
          () => this.now.set(Date.now()),
          Math.min(Math.max(1, Math.min(...times) - Date.now() + 1), 2147483647),
        );
    });
    if (typeof document !== 'undefined') {
      document.addEventListener('visibilitychange', this.reenter);
      window.addEventListener('focus', this.reenter);
    }
    effect(() => {
      this.key();
      this.pending();
      this.visible();
      this.facade.tenantPermissions();
      this.polling.update();
    });
    effect(() => {
      this.key();
      untracked(() => {
        this.request?.abort();
        this.result.set(null);
        this.denied = false;
        this.stale.set(false);
        this.polling.reset();
        void this.load(1);
      });
    });
    inject(DestroyRef).onDestroy(() => {
      this.alive = false;
      this.polling.dispose();
      clearTimeout(this.expiry);
      this.request?.abort();
      if (typeof document !== 'undefined') {
        document.removeEventListener('visibilitychange', this.reenter);
        window.removeEventListener('focus', this.reenter);
      }
    });
  }
  name(id: string) {
    return this.facade.entries().find((row) => row.id === id)?.name || 'Knowledge processing';
  }
  label(state: string) {
    return (
      (
        {
          queued: 'Queued',
          processing: 'Processing',
          indexing: 'Indexing',
          complete: 'Complete',
          failed: 'Processing failed',
          cancelled: 'Stopped',
          reconciliation_required: 'Review required',
        } as Record<string, string>
      )[state] || 'Status not verified'
    );
  }
  async load(page: number, background = false) {
    if (!this.alive || this.denied || (background && this.pending())) return;
    this.request?.abort();
    if (!this.stale()) this.error.set('');
    if (!background) this.result.set(null);
    const transport = this.clients.getTransport();
    if (!transport || !this.facade.tenantId() || !this.allowed()) {
      this.pending.set(false);
      return;
    }
    const key = this.key();
    const controller = new AbortController();
    this.request = controller;
    this.pending.set(true);
    const current = () =>
      this.alive &&
      !controller.signal.aborted &&
      this.request === controller &&
      this.key() === key &&
      this.allowed();
    try {
      const value = await createAvailabilityApi(transport).processing(
        this.facade.tenantId(),
        { page, page_size: 25, workspace_id: this.facade.workspaceId() || undefined },
        { signal: controller.signal },
      );
      if (current()) {
        if (!Array.isArray(value.items) || value.items.length > 25)
          throw new Error('Invalid processing observation page');
        this.result.set({ key, value });
        this.page.set(page);
        this.stale.set(false);
        this.error.set('');
      }
    } catch (error) {
      if (current()) {
        this.stale.set(true);
        this.error.set('Processing observations could not be verified.');
        if (error instanceof KoinonError && [401, 403].includes(error.status)) {
          this.denied = true;
          this.result.set(null);
          if (error.status === 401) this.facade.authRequired.set(true);
        }
      }
    } finally {
      if (this.request === controller) {
        this.request = undefined;
        this.pending.set(false);
        this.polling.update();
      }
    }
  }
}
