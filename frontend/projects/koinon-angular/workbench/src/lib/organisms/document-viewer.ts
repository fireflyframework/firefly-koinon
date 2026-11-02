// Copyright 2026 Firefly Software Foundation
// SPDX-License-Identifier: Apache-2.0
import {
  ChangeDetectionStrategy,
  Component,
  effect,
  inject,
  input,
  output,
  untracked,
} from '@angular/core';
import type { CatalogEntry } from '@fireflyframework/koinon-sdk';
import { KoinonDocumentViewer } from '../services/document-viewer';
import { KoinonSidePanel } from '@fireflyframework/koinon-angular/workbench/panels';
import { KoinonButton } from '@fireflyframework/koinon-angular/workbench/core';
import { KoinonSkeleton } from '@fireflyframework/koinon-angular/workbench/core';
import { KoinonTextPipe, KoinonDatePipe, registerKoinonSpanish } from '@fireflyframework/koinon-angular/workbench/core';
registerKoinonSpanish({
  'This original exceeds the 128 MiB download limit. Its extracted text remains readable. Contact your administrator for an approved transfer.':
    'Este original supera el límite de descarga de 128 MiB. Su texto extraído sigue disponible. Contacta con tu administrador para transferirlo de forma autorizada.',
  'This original exceeds the 16 MiB preview limit. Download it to open it with a compatible application.':
    'Este original supera el límite de vista previa de 16 MiB. Descárgalo para abrirlo con una aplicación compatible.',
  'Prepare PDF': 'Preparar PDF',
  'Open PDF in browser tab': 'Abrir PDF en una pestaña del navegador',
  'This PDF opens in a separate browser tab. You can also download the original or return to its extracted text.':
    'Este PDF se abre en una pestaña independiente del navegador. También puedes descargar el original o volver a su texto extraído.',
  'Read document': 'Leer documento',
  'Download original': 'Descargar original',
  'Preview original': 'Vista previa del original',
  'Extracted text': 'Texto extraído',
  'Original preview': 'Vista previa del original',
  'This is extracted text, not the original page layout.':
    'Este es texto extraído, no el diseño de página original.',
  'No extracted text is available for this version. You can download the original.':
    'No hay texto extraído disponible para esta versión. Puedes descargar el original.',
  'The latest processing attempt did not replace this readable version.':
    'El último intento de procesamiento no sustituyó esta versión legible.',
  'This document is not yet available to read. Inspect its processing status and try again.':
    'Este documento aún no está disponible para leer. Revisa su estado de procesamiento e inténtalo de nuevo.',
  'Your current access does not allow opening this document.':
    'Tu acceso actual no permite abrir este documento.',
  'The document could not be opened. Close it and try again.':
    'No se pudo abrir el documento. Ciérralo e inténtalo de nuevo.',
  'This file type cannot be previewed here. Download the original to open it with a compatible application.':
    'Este tipo de archivo no se puede previsualizar aquí. Descarga el original para abrirlo con una aplicación compatible.',
  'Document version': 'Versión del documento',
  Extraction: 'Extracción',
  'Original SHA256': 'SHA256 del original',
  'Text parts': 'Partes del texto',
  'Text part': 'Parte del texto',
  'Previous parts': 'Partes anteriores',
  'Next parts': 'Partes siguientes',
  'Recorded page': 'Página registrada',
  'Loading document': 'Cargando documento',
  'The preview uses your browser’s PDF or image viewer. Download the original if it cannot be displayed.':
    'La vista previa utiliza el visor de PDF o imágenes de tu navegador. Descarga el original si no se puede mostrar.',
});
@Component({
  selector: 'ffk-document-viewer',
  imports: [KoinonSidePanel, KoinonButton, KoinonSkeleton, KoinonTextPipe, KoinonDatePipe],
  providers: [KoinonDocumentViewer],
  templateUrl: './document-viewer.html',
  styleUrl: './document-viewer.scss',
  host: { style: '--koinon-panel-width:1040px' },
  changeDetection: ChangeDetectionStrategy.OnPush,
})
export class KoinonDocumentViewerPanel {
  readonly entry = input.required<CatalogEntry>();
  readonly closed = output<void>();
  readonly state = inject(KoinonDocumentViewer);
  constructor() {
    effect(() => {
      const entry = this.entry();
      untracked(() => void this.state.open(entry));
    });
  }
  close() {
    this.state.close();
    this.closed.emit();
  }
}
