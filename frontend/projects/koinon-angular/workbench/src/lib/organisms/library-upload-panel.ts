// Copyright 2026 Firefly Software Foundation
// SPDX-License-Identifier: Apache-2.0
import {
  ChangeDetectionStrategy,
  Component,
  DestroyRef,
  Input,
  OnInit,
  DoCheck,
  computed,
  inject,
  signal,
} from '@angular/core';
import { DecimalPipe } from '@angular/common';
import type { FileBatchItemView } from '@fireflyframework/koinon-sdk';
import type { KoinonWorkbench } from '../koinon-angular';
import type { LibraryUploadRuntime } from '../services/library-upload';
import { transferProgress } from '../services/library-upload-selection';
import { effectiveUploadLimits } from '../services/library-upload-coordinator';
import { KoinonButton } from '@fireflyframework/koinon-angular/workbench/core';
import { KoinonFileTypeIcon } from '@fireflyframework/koinon-angular/workbench/core';
import { KoinonIcon } from '@fireflyframework/koinon-angular/workbench/core';
import { KoinonFileFormats } from '@fireflyframework/koinon-angular/workbench/core';
import { KoinonBadge } from '@fireflyframework/koinon-angular/workbench/core';
import { KoinonSkeleton } from '@fireflyframework/koinon-angular/workbench/core';
import { KoinonFolderTree } from '@fireflyframework/koinon-angular/workbench/panels';
import {
  KoinonI18n,
  KoinonTextPipe,
  KoinonDatePipe,
  registerKoinonSpanish,
} from '@fireflyframework/koinon-angular/workbench/core';
registerKoinonSpanish({
  'Search document content': 'Buscar en el contenido del documento',
  'Analyze rows and columns': 'Analizar filas y columnas',
  'How to use': 'Cómo usar',
  'Your upload': 'Tu carga',
  Transferred: 'Transferidos',
  of: 'de',
  'Bytes transferred': 'Bytes transferidos',
  'files processed': 'archivos procesados',
  'Continue in background': 'Continuar en segundo plano',
  'Upload more files': 'Subir más archivos',
  'Uploading files': 'Subiendo archivos',
  'Upload needs attention': 'La carga necesita atención',
  'Processing files': 'Procesando archivos',
  'Upload updated': 'Carga actualizada',
  'View upload': 'Ver carga',
  'View uploads': 'Ver cargas',
  'Status updates automatically. You can close this panel and find your files in Uploads.':
    'El estado se actualiza automáticamente. Puedes cerrar este panel y encontrar tus archivos en Cargas.',
  'Keep this browser tab open until transfer finishes. Processing continues after upload.':
    'Mantén esta pestaña abierta hasta terminar la transferencia. El procesamiento continúa después de la carga.',
  'Word, PDF and presentations are prepared for reading and search. Spreadsheets and CSV are prepared for questions about rows and totals.':
    'Word, PDF y presentaciones se preparan para leer y buscar. Hojas de cálculo y CSV se preparan para preguntas sobre filas y totales.',

  Upload: 'Subir',
  'Add files': 'Añadir archivos',
  'Add more files': 'Añadir más archivos',
  'Supported file types and limits': 'Formatos y límites de archivo',
  'Upload details': 'Detalles de la carga',
  'Upload options': 'Opciones de carga',
  'Try updating status': 'Intentar actualizar el estado',
  'Open this .ppt file in PowerPoint and use Save As .pptx, then upload the converted file.':
    'Abre este archivo .ppt en PowerPoint y usa Guardar como .pptx; después carga el archivo convertido.',
  Failed: 'Error',
  Cancelled: 'Cancelado',
  'Review recovery options': 'Revisar opciones de recuperación',
  bytes: 'bytes',
  'This processing mode is unavailable.': 'Este modo de procesamiento no está disponible.',
  'Supported file types': 'Tipos de archivo admitidos',
  'Maximum files': 'Máximo de archivos',
  'Files transferred': 'Archivos transferidos',
  'Uploading and processing': 'Cargando y procesando',
  'Transferring original': 'Transfiriendo original',
  'This file is empty.': 'Este archivo está vacío.',
  'This file exceeds the maximum file size.': 'Este archivo supera el tamaño máximo.',
  'This file type is not supported for the selected use.':
    'Este tipo de archivo no se admite para el uso seleccionado.',
  'Too many files selected for one upload.':
    'Se han seleccionado demasiados archivos para una carga.',
  'Selected files exceed the maximum batch size.':
    'Los archivos seleccionados superan el tamaño máximo del lote.',
  'Remove files that cannot be uploaded before continuing.':
    'Elimina los archivos que no se pueden cargar antes de continuar.',
  'Choose a destination folder to see supported files and limits.':
    'Elige una carpeta de destino para ver los archivos admitidos y los límites.',
  'Create a space, project and folder in Library, then return to upload.':
    'Crea un espacio, un proyecto y una carpeta en la Biblioteca y vuelve para cargar archivos.',
  'Back to Library': 'Volver a la Biblioteca',
  Indexing: 'Indexando',
  Searchable: 'Disponible para buscar',
  'Available to query': 'Disponible para consultar',
  'Availability not checked': 'Disponibilidad sin verificar',
  'Text available; search pending': 'Texto disponible; búsqueda pendiente',
  'Text available; search not checked': 'Texto disponible; búsqueda sin verificar',
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
  'The synchronous upload did not confirm every result. Inspect the current folder before recovery. No files were sent again.':
    'La carga síncrona no ha confirmado todos los resultados. Revisa la carpeta actual antes de recuperar. No se han vuelto a enviar archivos.',
  'Worker state not verified': 'Estado del proceso sin verificar',
  'Worker started': 'Proceso iniciado',
  'Current availability': 'Disponibilidad actual',
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
  'Your files are being prepared. Search availability is checked separately.':
    'Tus archivos se están preparando. La disponibilidad para buscar se comprueba por separado.',
  'A previous request is not confirmed. Check status or reconcile the retained original; do not send it again.':
    'Una solicitud anterior no está confirmada. Comprueba el estado o concilia el original conservado; no lo vuelvas a enviar.',
  'Finish uploading your files to start processing.':
    'Termina de subir tus archivos para iniciar el procesamiento.',
  'No accepted batch could be confirmed. The original request was not repeated. Keep this page open and ask an administrator to inspect retained uploads.':
    'No se ha podido confirmar un lote aceptado. La solicitud original no se ha repetido. Mantén esta página abierta y pide a un administrador que revise las cargas conservadas.',
  'After upload, files are processed for reading or queries. Search availability is checked separately.':
    'Después de la carga, los archivos se procesan para lectura o consultas. La disponibilidad para buscar se comprueba por separado.',
  'Configured limits are checked before transfer.':
    'Los límites configurados se comprueban antes de transferir.',
  'Maximum per file': 'Máximo por archivo',
  'Maximum batch': 'Máximo por lote',
  'Cancellation stops pending work; already published effects can remain.':
    'La cancelación detiene el trabajo pendiente; los efectos ya publicados pueden permanecer.',
  'This upload panel could not be connected. Close it and try again.':
    'No se ha podido conectar este panel de carga. Ciérralo y vuelve a intentarlo.',
});
@Component({
  selector: 'ffk-library-upload-panel',
  imports: [
    KoinonFileTypeIcon,
    DecimalPipe,
    KoinonButton,
    KoinonIcon,
    KoinonBadge,
    KoinonFileFormats,
    KoinonSkeleton,
    KoinonFolderTree,
    KoinonTextPipe,
    KoinonDatePipe,
  ],
  templateUrl: './library-upload-panel.html',
  styleUrl: './library-upload-panel.scss',
  changeDetection: ChangeDetectionStrategy.OnPush,
})
export class KoinonLibraryUploadPanel implements OnInit, DoCheck {
  @Input({ required: true }) w!: KoinonWorkbench;
  readonly runtime = signal<LibraryUploadRuntime | null>(null);
  private readonly i18n = inject(KoinonI18n);
  size(value: number) {
    const unit = value >= 1000000 ? 1000000 : value >= 1000 ? 1000 : 1;
    return (
      new Intl.NumberFormat(this.i18n.preferences().locale, { maximumFractionDigits: 1 }).format(
        value / unit,
      ) +
      ' ' +
      (unit === 1000000 ? 'MB' : unit === 1000 ? 'KB' : this.i18n.text('bytes'))
    );
  }
  readonly error = signal('');
  readonly view = computed(() => this.runtime()?.coordinator.view());
  readonly progress = computed(() => transferProgress(this.view()?.items || []));
  readonly processed = computed(
    () => (this.view()?.items || []).filter((item) => item.status === 'succeeded').length,
  );
  readonly limits = computed(() => {
    const capabilities = this.view()?.capabilities;
    return capabilities ? effectiveUploadLimits(capabilities) : null;
  });
  readonly retained = computed(
    () => !!this.view()?.batch || !!this.view()?.uncertain || this.view()?.stage === 'observed',
  );
  private destination = '';
  ngDoCheck() {
    const destination = this.w.formParent;
    if (this.runtime() && destination !== this.destination) {
      this.destination = destination;
      void this.runtime()?.coordinator.inspect();
    }
  }
  unavailableFormats() {
    return (
      this.view()
        ?.capabilities?.formats?.filter((format) => !format.available)
        .flatMap((format) => format.extensions) || []
    );
  }
  accept() {
    return (
      this.view()
        ?.capabilities?.formats?.filter(
          (format) => format.available && !!this.view()?.capabilities?.modes.includes(format.mode),
        )
        .flatMap((format) => format.extensions)
        .join(',') || ''
    );
  }
  issue(file: File) {
    const caps = this.view()?.capabilities,
      limits = this.limits();
    if (!caps || !limits) return '';
    if (!file.size) return 'This file is empty.';
    if (file.name.toLowerCase().endsWith('.ppt') && !this.accept().split(',').includes('.ppt'))
      return 'Open this .ppt file in PowerPoint and use Save As .pptx, then upload the converted file.';
    if (file.size > limits.max_file_bytes) return 'This file exceeds the maximum file size.';
    if (!this.runtime()?.mode(file)) return 'This file type is not supported for the selected use.';
    return '';
  }
  selectionIssue() {
    const limits = this.limits();
    if (!limits) return '';
    if (this.w.files.length > limits.max_files) return 'Too many files selected for one upload.';
    if (this.w.files.reduce((total, file) => total + file.size, 0) > limits.max_batch_bytes)
      return 'Selected files exceed the maximum batch size.';
    return this.w.files.some((file) => this.issue(file))
      ? 'Remove files that cannot be uploaded before continuing.'
      : '';
  }
  addFiles(event: Event) {
    if (this.view()?.busy) return;
    const input = event.target as HTMLInputElement;
    this.w.files = [...this.w.files, ...Array.from(input.files || [])];
    input.value = '';
  }
  addDrop(event: DragEvent) {
    event.preventDefault();
    if (!this.view()?.busy)
      this.w.files = [...this.w.files, ...Array.from(event.dataTransfer?.files || [])];
  }
  removeFile(index: number) {
    if (!this.view()?.busy) this.w.files = this.w.files.filter((_, position) => position !== index);
  }
  private destroyed = false;
  constructor() {
    inject(DestroyRef).onDestroy(() => {
      this.destroyed = true;
    });
  }
  async ngOnInit() {
    try {
      const runtime = await this.w.uploadRuntime();
      if (!this.destroyed) {
        this.runtime.set(runtime);
        this.destination = this.w.formParent;
        await runtime.coordinator.inspect();
      }
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
          failed: 'Failed',
          cancelled: 'Cancelled',
          expired: 'Upload expired',
          reconciling: 'Reconciliation required',
          staged: 'Original staged',
          awaiting_upload: 'Awaiting original',
        } as Record<string, string>
      )[status] || 'Availability not checked'
    );
  }
  fresh() {
    if (!this.runtime()?.fresh()) return;
    this.w.files = [];
    this.w.uploadedFiles.set(new Set());
    this.w.uploadedCount.set(0);
    this.w.uploadState.set('select');
    void this.runtime()?.coordinator.inspect();
  }
  check() {
    return this.runtime()?.coordinator.refresh();
  }
}
