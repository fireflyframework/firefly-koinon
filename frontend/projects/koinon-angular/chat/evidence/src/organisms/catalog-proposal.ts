// Copyright 2026 Firefly Software Foundation
// SPDX-License-Identifier: Apache-2.0
import {
  ChangeDetectionStrategy,
  Component,
  EventEmitter,
  Input,
  OnChanges,
  Output,
  PendingTasks,
  inject,
  computed,
} from '@angular/core';
import {
  KoinonButton,
  KoinonI18n,
  KoinonSkeleton,
  KoinonTextPipe,
} from '@fireflyframework/koinon-angular';
import type { CatalogProposal } from '@fireflyframework/koinon-sdk';
import { KoinonCatalogProposals } from '../services/catalog-proposals';
@Component({
  selector: 'ffk-catalog-proposal',
  imports: [KoinonButton, KoinonSkeleton, KoinonTextPipe],
  providers: [KoinonCatalogProposals],
  templateUrl: './catalog-proposal.html',
  styleUrl: './catalog-proposal.scss',
  changeDetection: ChangeDetectionStrategy.OnPush,
})
export class KoinonCatalogProposal implements OnChanges {
  @Input() runId = '';
  @Input() resultId = '';
  @Output() readonly resourceRequested = new EventEmitter<string>();
  @Output() readonly proposalUpdated = new EventEmitter<CatalogProposal>();
  readonly state = inject(KoinonCatalogProposals);
  private readonly tasks = inject(PendingTasks);
  private readonly i18n = inject(KoinonI18n);
  readonly copy = computed(() =>
    this.i18n.preferences().locale.toLowerCase().startsWith('es')
      ? {
          writePermission:
            'Se necesita permiso para editar el catálogo para aplicar estos cambios.',
          title: 'Revisar cambios sugeridos',
          before: 'Antes de la propuesta',
          proposed: 'Cambio propuesto',
          name: 'Nombre',
          description: 'Descripción',
          empty: 'Sin descripción',
          apply: 'Aplicar cambios',
          cancel: 'Cancelar propuesta',
          open: 'Abrir recurso',
          refresh: 'Actualizar propuesta',
          pending: 'Pendiente de revisión',
          applied: 'Aplicado',
          cancelled: 'Cancelado',
          loading: 'Cargando propuesta…',
          working: 'Registrando tu decisión…',
          unavailable: 'Se necesita acceso al chat y al catálogo para revisar esta propuesta.',
          signIn: 'Inicia sesión para revisar esta propuesta.',
          newProposal: 'El recurso cambió. Solicita una nueva propuesta antes de aplicar cambios.',
          review: 'Revisa los cambios de nombre y descripción antes de aplicarlos.',
          load: 'Cargar propuesta',
        }
      : {
          writePermission: 'Catalog edit permission is required to apply these changes.',
          title: 'Review suggested changes',
          before: 'Before the proposal',
          proposed: 'Proposed change',
          name: 'Name',
          description: 'Description',
          empty: 'No description',
          apply: 'Apply changes',
          cancel: 'Cancel proposal',
          open: 'Open resource',
          refresh: 'Refresh proposal',
          pending: 'Pending review',
          applied: 'Applied',
          cancelled: 'Cancelled',
          loading: 'Loading proposal…',
          working: 'Recording your decision…',
          unavailable: 'Chat and catalog access are required to review this proposal.',
          signIn: 'Sign in to review this proposal.',
          newProposal: 'The resource changed. Request a new proposal before applying changes.',
          review: 'Review the name and description changes before applying them.',
          load: 'Load proposal',
        },
  );
  ngOnChanges() {
    this.load();
  }
  load() {
    this.tasks.run(() => this.state.load(this.runId, this.resultId).then(() => undefined));
  }
  apply() {
    this.tasks.run(async () => {
      const value = await this.state.apply();
      if (value && this.state.proposal() === value) this.proposalUpdated.emit(value);
    });
  }
  cancel() {
    this.tasks.run(async () => {
      const value = await this.state.cancel();
      if (value && this.state.proposal() === value) this.proposalUpdated.emit(value);
    });
  }
  resource() {
    const value = this.state.proposal();
    if (value && this.state.canRead()) this.resourceRequested.emit(value.asset_id);
  }
  status(value: CatalogProposal) {
    return value.status === 'applied'
      ? this.copy().applied
      : value.status === 'cancelled'
        ? this.copy().cancelled
        : this.copy().pending;
  }
}
