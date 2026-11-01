// Copyright 2026 Firefly Software Foundation
// SPDX-License-Identifier: Apache-2.0
import {
  ChangeDetectionStrategy,
  Component,
  DestroyRef,
  Input,
  OnInit,
  computed,
  effect,
  inject,
  signal,
} from '@angular/core';
import { DecimalPipe } from '@angular/common';
import type { FileBatchItemView } from '@fireflyframework/koinon-sdk';
import type { KoinonWorkbench } from '../koinon-angular';
import type { LibraryUploadRuntime } from '../services/library-upload';
import { KoinonButton } from '../atoms/button';
import { KoinonIcon } from '../atoms/icon';
import { KoinonBadge } from '../atoms/badge';
import { KoinonSkeleton } from '../atoms/skeleton';
import { KoinonFolderTree } from './folder-tree';
import { KoinonTextPipe, KoinonDatePipe, registerKoinonSpanish } from '../foundations/i18n';
registerKoinonSpanish({
  Upload: 'Subir',
  Indexing: 'Indexando',
  Searchable: 'Disponible para buscar',
  'Available to query': 'Disponible para consultar',
  'Availability not checked': 'Disponibilidad sin verificar',
  'Text available; search pending': 'Texto disponible; búsqueda pendiente',
  'Text available; search not checked': 'Texto disponible; búsqueda sin verificar',
  'Automatic checks paused. Check status for a fresh observation.':
    'Comprobaciones automáticas en pausa. Comprueba el estado para obtener una observación actual.',
  file: 'archivo',
  files: 'archivos',
  'file received': 'archivo recibido',
  'files received': 'archivos recibidos',
  'Open current folder': 'Abrir carpeta actual',
  'Outcome not confirmed': 'Resultado sin confirmar',
  'Only folders where you can add knowledge are selectable.':
    'Solo se pueden seleccionar carpetas donde puedas añadir conocimiento.',
  'Status could not be refreshed. Last observations are retained.':
    'No se ha podido actualizar el estado. Se conservan las últimas observaciones.',
  'Preparing upload': 'Preparando la carga',
  'Current upload access could not be verified. Refresh your account access before continuing.':
    'No se ha podido verificar el acceso actual a la carga. Actualiza el acceso de tu cuenta antes de continuar.',
  'Choose document or dataset mode before uploading.':
    'Elige el modo documento o conjunto de datos antes de cargar.',
  'The synchronous upload did not confirm every result. Inspect the current folder before recovery. No files were sent again.':
    'La carga síncrona no ha confirmado todos los resultados. Revisa la carpeta actual antes de recuperar. No se han vuelto a enviar archivos.',
  'Worker state not verified': 'Estado del proceso sin verificar',
  'Worker started': 'Proceso iniciado',
  'Current availability': 'Disponibilidad actual',
  'Documents for reading': 'Documentos para leer',
  'Checking upload readiness': 'Comprobando la preparación de la carga',
  'Checking original integrity': 'Comprobando la integridad del original',
  'Registering this upload': 'Registrando esta carga',
  'Transferring originals': 'Transfiriendo originales',
  'Submitting for worker processing': 'Enviando al procesamiento en segundo plano',
  'Upload outcome not confirmed': 'Resultado de la carga sin confirmar',
  'Last observed state': 'Último estado observado',
  'Extraction complete': 'Extracción finalizada',
  'Some files need attention': 'Algunos archivos necesitan atención',
  'Upload expired': 'La carga ha caducado',
  'Reconciliation required': 'Requiere conciliación',
  'Original staged': 'Original preparado',
  'Awaiting original': 'Esperando el original',
  'Check status': 'Comprobar estado',
  'Continue upload': 'Continuar la carga',
  'Submit for processing': 'Enviar para procesar',
  'Request cancellation': 'Solicitar cancelación',
  'Reconcile retained original': 'Conciliar el original conservado',
  'Choose more files': 'Elegir más archivos',
  'The upload outcome is not confirmed. Check status before taking another action. Files were not sent again.':
    'El resultado de la carga no está confirmado. Comprueba su estado antes de actuar. Los archivos no se han vuelto a enviar.',
  'Upload readiness could not be verified. No files were sent.':
    'No se ha podido comprobar la preparación de la carga. No se han enviado archivos.',
  'Choose files and a connected destination folder before uploading.':
    'Elige archivos y una carpeta de destino conectada antes de cargar.',
  'These files exceed the observed upload limits or use an unavailable processing mode.':
    'Estos archivos superan los límites observados o utilizan un modo de procesamiento no disponible.',
  'Large files need configured queued storage. They were not sent to synchronous processing.':
    'Los archivos grandes requieren almacenamiento configurado para la cola. No se han enviado al procesamiento síncrono.',
  'Files received. Check their observed availability in the Library.':
    'Archivos recibidos. Comprueba su disponibilidad observada en la Biblioteca.',
  'Processing status comes from the worker. Completed extraction does not establish search readiness.':
    'El estado de procesamiento procede del proceso en segundo plano. Una extracción finalizada no confirma la disponibilidad para buscar.',
  'A previous request is not confirmed. Check status or reconcile the retained original; do not send it again.':
    'Una solicitud anterior no está confirmada. Comprueba el estado o concilia el original conservado; no lo vuelvas a enviar.',
  'Files are processed only after their originals are staged and the batch is submitted.':
    'Los archivos solo se procesan después de preparar sus originales y enviar el lote.',
  'No accepted batch could be confirmed. The original request was not repeated. Keep this page open and ask an administrator to inspect retained uploads.':
    'No se ha podido confirmar un lote aceptado. La solicitud original no se ha repetido. Mantén esta página abierta y pide a un administrador que revise las cargas conservadas.',
  'Worker extraction records text or tables. Search availability is checked separately.':
    'La extracción en segundo plano registra texto o tablas. La disponibilidad para buscar se comprueba por separado.',
  'Configured limits are checked before transfer.':
    'Los límites configurados se comprueban antes de transferir.',
  'Maximum per file': 'Máximo por archivo',
  'Maximum batch': 'Máximo por lote',
  'Closing this panel stops its automatic checks. It does not cancel submitted work.':
    'Cerrar este panel detiene sus comprobaciones automáticas. No cancela el trabajo enviado.',
  'Cancellation stops pending work; already published effects can remain.':
    'La cancelación detiene el trabajo pendiente; los efectos ya publicados pueden permanecer.',
  'This upload panel could not be connected. Close it and try again.':
    'No se ha podido conectar este panel de carga. Ciérralo y vuelve a intentarlo.',
});
@Component({
  selector: 'ffk-library-upload-panel',
  imports: [
    DecimalPipe,
    KoinonButton,
    KoinonIcon,
    KoinonBadge,
    KoinonSkeleton,
    KoinonFolderTree,
    KoinonTextPipe,
    KoinonDatePipe,
  ],
  templateUrl: './library-upload-panel.html',
  styleUrl: './library-upload-panel.scss',
  changeDetection: ChangeDetectionStrategy.OnPush,
})
export class KoinonLibraryUploadPanel implements OnInit {
  @Input({ required: true }) w!: KoinonWorkbench;
  readonly runtime = signal<LibraryUploadRuntime | null>(null);
  readonly error = signal('');
  readonly view = computed(() => this.runtime()?.coordinator.view());
  readonly retained = computed(
    () => !!this.view()?.batch || !!this.view()?.uncertain || this.view()?.stage === 'observed',
  );
  private destroyed = false;
  private polls = 0;
  private timer?: ReturnType<typeof setTimeout>;
  constructor() {
    effect(() => {
      clearTimeout(this.timer);
      const value = this.view();
      if (
        value?.batch &&
        ['queued', 'running'].includes(value.batch.status) &&
        !value.busy &&
        this.polls < 12
      ) {
        this.timer = setTimeout(() => {
          ++this.polls;
          void this.runtime()?.coordinator.refresh();
        }, 5000);
      }
    });
    inject(DestroyRef).onDestroy(() => {
      this.destroyed = true;
      clearTimeout(this.timer);
    });
  }
  async ngOnInit() {
    try {
      const runtime = await this.w.uploadRuntime();
      if (!this.destroyed) this.runtime.set(runtime);
    } catch {
      if (!this.destroyed)
        this.error.set('This upload panel could not be connected. Close it and try again.');
    }
  }
  readonly itemStaged = (item: { status: string }) => item.status === 'staged';
  readonly selectedFolder = (entry: { id: string }) => entry.id === this.w.formParent;
  treeStart() {
    if (this.w.formParent) return this.w.formParent;
    if (this.w.f.workspaceId()) return this.w.f.workspaceId();
    const roots = this.w.allEntries().filter((entry) => entry.kind === 'workspace');
    return roots.length === 1 ? roots[0]!.id : '';
  }
  batchLabel(status: string) {
    if (status === 'running')
      return this.view()?.items.some(
        (item) => this.view()?.availability[item.asset_id]?.phase === 'processing',
      )
        ? 'Processing'
        : 'Worker state not verified';
    return this.label(status);
  }
  currentLabel(item: FileBatchItemView) {
    const value = this.view()?.availability[item.asset_id];
    if (!value) return 'Availability not checked';
    if (value.phase === 'processing') return 'Processing';
    if (value.phase === 'indexing') return 'Indexing';
    if (value.phase === 'queued') return 'Queued';
    if (value.phase === 'failed') return 'Needs attention';
    if (value.search?.state === 'ready') return 'Searchable';
    if (value.query?.state === 'ready') return 'Available to query';
    if (value.read?.state === 'ready')
      return value.search?.state === 'pending'
        ? 'Text available; search pending'
        : 'Text available; search not checked';
    return 'Availability not checked';
  }
  label(status: string, progress = false) {
    if (status === 'staging' && progress) return 'Transferring originals';
    return (
      (
        {
          checking: 'Checking upload readiness',
          hashing: 'Checking original integrity',
          creating: 'Registering this upload',
          staging: 'Preparing upload',
          submitting: 'Submitting for worker processing',
          observed: 'Preparing upload',
          unknown: 'Upload outcome not confirmed',
          queued: 'Queued',
          running: 'Worker started',
          succeeded: 'Extraction complete',
          partial: 'Some files need attention',
          failed: 'Needs attention',
          cancelled: 'Stopped',
          expired: 'Upload expired',
          reconciling: 'Reconciliation required',
          staged: 'Original staged',
          awaiting_upload: 'Awaiting original',
        } as Record<string, string>
      )[status] || 'Availability not checked'
    );
  }
  fresh() {
    if (!this.runtime()?.coordinator.reset()) return;
    this.polls = 0;
    this.w.files = [];
    this.w.uploadedFiles.set(new Set());
    this.w.uploadedCount.set(0);
    this.w.uploadState.set('select');
  }
  checksPaused() {
    return this.polls >= 12;
  }
  check() {
    this.polls = 0;
    return this.runtime()?.coordinator.refresh();
  }
}
