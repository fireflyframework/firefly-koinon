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
  KoinonButton,
  KoinonClientContext,
  KoinonDatePipe,
  KoinonFacade,
  KoinonTextPipe,
} from '@fireflyframework/koinon-angular';
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
});
@Component({
  selector: 'ffk-processing-history',
  imports: [KoinonButton, KoinonTextPipe, KoinonDatePipe],
  template: `<section aria-label="Current knowledge processing">
    <h2>{{ 'Knowledge processing' | ffkText }}</h2>
    <p>
      {{
        'Current jobs and recorded content attempts. Earlier unrecorded stages are unavailable.'
          | ffkText
      }}
    </p>
    <ffk-button (click)="load(page())" [loading]="pending()">{{ 'Refresh' | ffkText }}</ffk-button>
    @if (error()) {
      <p role="status">{{ error() | ffkText }}</p>
    }
    <div class="records">
      @for (row of current()?.items || []; track row.id) {
        <article>
          <strong>{{ name(row.resource_id) }}</strong>
          <p>{{ row.operation }}</p>
          <p>{{ label(row.state) | ffkText }}</p>
          @if (row.availability.read?.state === 'ready') {
            <p>{{ 'Text remains available from the observed version' | ffkText }}</p>
          }
          @if (row.availability.search?.state === 'ready') {
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
  private facade = inject(KoinonFacade);
  private clients = inject(KoinonClientContext);
  private request?: AbortController;
  private result = signal<{ key: string; value: ProcessingResponse } | null>(null);
  readonly page = signal(1);
  readonly pending = signal(false);
  readonly error = signal('');
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
    ]);
  });
  readonly current = computed(() =>
    this.result()?.key === this.key() ? this.result()!.value : null,
  );
  constructor() {
    effect(() => {
      this.key();
      untracked(() => {
        this.request?.abort();
        this.result.set(null);
        void this.load(1);
      });
    });
    inject(DestroyRef).onDestroy(() => this.request?.abort());
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
          failed: 'Needs attention',
          cancelled: 'Stopped',
          reconciliation_required: 'Review required',
        } as Record<string, string>
      )[state] || 'Status not verified'
    );
  }
  async load(page: number) {
    this.request?.abort();
    this.error.set('');
    this.result.set(null);
    const transport = this.clients.getTransport();
    if (
      !transport ||
      !this.facade.tenantId() ||
      !this.facade.tenantPermissions().has('jobs:manage')
    ) {
      this.pending.set(false);
      return;
    }
    const key = this.key();
    const controller = new AbortController();
    this.request = controller;
    this.pending.set(true);
    const current = () =>
      !controller.signal.aborted && this.request === controller && this.key() === key;
    try {
      const value = await createAvailabilityApi(transport).processing(
        this.facade.tenantId(),
        { page, page_size: 25, workspace_id: this.facade.workspaceId() || undefined },
        { signal: controller.signal },
      );
      if (current()) {
        this.result.set({ key, value });
        this.page.set(page);
      }
    } catch {
      if (current()) this.error.set('Processing observations could not be verified.');
    } finally {
      if (current()) this.pending.set(false);
    }
  }
}
