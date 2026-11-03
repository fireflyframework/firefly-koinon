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
import { KoinonFacade } from '@fireflyframework/koinon-angular/workbench/core';
import { KoinonClientContext } from '@fireflyframework/koinon-angular/workbench/core';
import { availabilityStatus } from '../services/availability-status';
import { availabilitySession } from '../services/availability-session';
import { KoinonBadge } from '@fireflyframework/koinon-angular/workbench/core';
import { registerKoinonSpanish, KoinonDatePipe, KoinonTextPipe } from '@fireflyframework/koinon-angular/workbench/core';

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
  'Processing failed': 'El procesamiento falló',
  'Status temporarily unavailable': 'Estado temporalmente no disponible',
  'Last known status': 'Último estado conocido',
});
@Component({
  selector: 'ffk-knowledge-availability',
  imports: [KoinonBadge, KoinonTextPipe, KoinonDatePipe],
  template: `<span><span role="status"><ffk-badge [tone]="stale() ? 'attention' : presentation().tone">{{ label() | ffkText }}</ffk-badge>
    @if (stale() && value()) { <small>{{ 'Last known status' | ffkText }}: {{ presentation().label | ffkText }}</small> }
    </span>
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
  readonly stale = computed(() => this.session?.stale() ?? false);
  readonly presentation = computed(() => availabilityStatus(this.value(), this.entry().kind));
  readonly label = computed(() => this.stale() ? 'Status temporarily unavailable' : this.presentation().label);
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
