// Copyright 2026 Firefly Software Foundation
// SPDX-License-Identifier: Apache-2.0
import { ChangeDetectionStrategy, Component, Input } from '@angular/core';
import { KoinonTextPipe, registerKoinonSpanish } from '../foundations/i18n';

const families: readonly [string, readonly string[]][] = [
  ['Word', ['.docx', '.doc', '.dotx']],
  ['Excel', ['.xlsx', '.xls', '.xlsm']],
  ['PowerPoint', ['.pptx', '.ppt']],
  ['PDF', ['.pdf']],
  ['Text', ['.txt', '.text', '.md', '.markdown', '.rtf', '.html', '.htm', '.xml']],
  [
    'Datasets',
    [
      '.csv',
      '.tsv',
      '.json',
      '.jsonl',
      '.ndjson',
      '.parquet',
      '.orc',
      '.arrow',
      '.ipc',
      '.feather',
      '.avro',
    ],
  ],
  ['OpenDocument', ['.odt', '.ods', '.odp']],
  [
    'Images',
    ['.png', '.jpg', '.jpeg', '.webp', '.gif', '.tif', '.tiff', '.bmp', '.svg', '.heic', '.avif'],
  ],
];

export function fileFormatGroups(extensions: readonly string[]) {
  const remaining = new Set(extensions.map((value) => value.toLowerCase()));
  const definitions: typeof families = [...families, ['Other formats', []]];
  return definitions.flatMap(([label, known]) => {
    const selected = [...remaining].filter(
      (extension) =>
        label === 'Other formats' || known.includes(extension.replace(/\.(gz|bz2|zip)$/, '')),
    );
    selected.forEach((extension) => remaining.delete(extension));
    const base = [
      ...new Set(selected.map((extension) => extension.replace(/\.(gz|bz2|zip)$/, ''))),
    ];
    const summary =
      label === 'Datasets'
        ? base.slice(0, 2).join(', ') + (base.length > 2 ? ', …' : '')
        : ['Word', 'Excel', 'PowerPoint', 'PDF'].includes(label) || selected.length <= 2
          ? [
              ...new Set(selected.map((extension) => extension.replace(/\.(gz|bz2|zip)$/, ''))),
            ].join(', ')
          : '';
    return selected.length ? [{ label, extensions: selected, summary }] : [];
  });
}

registerKoinonSpanish({
  'Supported file types': 'Tipos de archivo admitidos',
  'All file formats': 'Todos los formatos de archivo',
  'Other formats': 'Otros formatos',
  Datasets: 'Conjuntos de datos',
  Text: 'Texto',
  Images: 'Imágenes',
  'Unavailable on this server': 'No disponibles en este servidor',
  'Open this .ppt file in PowerPoint and use Save As .pptx, then upload the converted file.':
    'Abre este archivo .ppt en PowerPoint y usa Guardar como .pptx; después carga el archivo convertido.',
  'For older .ppt files, use Save As in PowerPoint to create a .pptx file. Renaming the file does not convert it.':
    'Para archivos .ppt antiguos, usa Guardar como en PowerPoint para crear un archivo .pptx. Cambiar el nombre no convierte el archivo.',
});

@Component({
  selector: 'ffk-file-formats',
  imports: [KoinonTextPipe],
  templateUrl: './file-formats.html',
  styleUrl: './file-formats.scss',
  changeDetection: ChangeDetectionStrategy.OnPush,
})
export class KoinonFileFormats {
  @Input() extensions: readonly string[] = [];
  @Input() unavailable: readonly string[] = [];
  @Input() showDetails = true;
  groups() {
    return fileFormatGroups(this.extensions);
  }
  unavailableGroups() {
    return fileFormatGroups(this.unavailable);
  }
  legacyPowerPoint() {
    return this.extensions.includes('.pptx') && !this.extensions.includes('.ppt');
  }
}
