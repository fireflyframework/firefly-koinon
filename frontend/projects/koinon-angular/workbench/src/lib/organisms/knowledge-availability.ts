// Copyright 2026 Firefly Software Foundation
// SPDX-License-Identifier: Apache-2.0
import {
  ChangeDetectionStrategy,
  Component,
  computed,
  effect,
  inject,
  input,
  untracked,
} from '@angular/core';
import type { CatalogEntry } from '@fireflyframework/koinon-sdk';
import { KoinonFacade } from '../koinon-facade';
import { KoinonClientContext } from '../services/client-context';
import { availabilitySession } from '../services/availability-session';
import { KoinonBadge } from '../atoms/badge';
import { registerKoinonSpanish, KoinonDatePipe, KoinonTextPipe } from '../foundations/i18n';

registerKoinonSpanish({
  'Query preparation pending': 'Preparación de consulta pendiente',
  'Availability not checked': 'Disponibilidad sin verificar',
  Indexing: 'Indexando',
  Searchable: 'Disponible para buscar',
  'Available to query': 'Disponible para consultar',
  'Text available; search pending': 'Texto disponible; búsqueda pendiente',
  'Text available; search not checked': 'Texto disponible; búsqueda sin verificar',
  'Observed version remains available': 'La versión observada sigue disponible',
  'Observed serving version': 'Versión disponible observada',
  Checked: 'Comprobado',
});
@Component({
  selector: 'ffk-knowledge-availability',
  imports: [KoinonBadge, KoinonTextPipe, KoinonDatePipe],
  template: `<span role="status"
    ><ffk-badge [tone]="attention() ? 'attention' : 'neutral'">{{ label() | ffkText }}</ffk-badge>
    @if (value()?.latest_attempt?.state === 'failed' && value()?.read?.state === 'ready') {
      <small>{{ 'Observed version remains available' | ffkText }}</small>
    }
    @if (details()) {
      @if (value()?.revision; as revision) {
        @if (revision.source_version_id || revision.snapshot_id) {
          <small
            >{{ 'Observed serving version' | ffkText }}:
            {{ revision.source_version_id || revision.snapshot_id }}</small
          >
        }
        @if (observedAt()) {
          <small
            >{{ 'Checked' | ffkText }}: {{ observedAt() | ffkDate: undefined : 'datetime' }}</small
          >
        }
      }
    }
  </span>`,
  styles: `
    :host {
      display: block;
      margin-top: 4px;
    }
    small {
      display: block;
      color: var(--ui-muted);
      font-size: 12px;
      overflow-wrap: anywhere;
    }
  `,
  changeDetection: ChangeDetectionStrategy.OnPush,
})
export class KoinonKnowledgeAvailability {
  readonly entry = input.required<CatalogEntry>();
  readonly details = input(false);
  private readonly facade = inject(KoinonFacade, { optional: true });
  private readonly clients = inject(KoinonClientContext, { optional: true });
  private readonly session =
    this.facade && this.clients ? availabilitySession(this.facade, this.clients) : null;
  readonly observedAt = computed(() => (this.value() ? this.session?.observedAt() : ''));
  readonly value = computed(() => this.session?.get(this.entry().id));
  readonly attention = computed(() =>
    ['failed', 'reconciliation_required'].includes(this.value()?.phase ?? ''),
  );
  readonly label = computed(() => {
    const value = this.value();
    if (!value) return 'Availability not checked';
    if (value.phase === 'failed') return 'Needs attention';
    if (value.phase === 'reconciliation_required') return 'Review required';
    if (value.phase === 'cancelled') return 'Stopped';
    if (value.phase === 'queued') return 'Queued';
    if (value.phase === 'processing') return 'Processing';
    if (value.phase === 'indexing') return 'Indexing';
    if (value.search?.state === 'ready') return 'Searchable';
    if (value.query?.state === 'ready') return 'Available to query';
    if (['dataset', 'table'].includes(this.entry().kind) && value.query?.state === 'pending')
      return 'Query preparation pending';
    if (value.read?.state === 'ready')
      return value.search?.state === 'pending'
        ? 'Text available; search pending'
        : 'Text available; search not checked';
    return 'Availability not checked';
  });
  constructor() {
    effect((onCleanup) => {
      const entry = this.entry();
      if (this.session) {
        this.session.sync();
        untracked(() => onCleanup(this.session!.watch(entry.id)));
      }
    });
  }
}
