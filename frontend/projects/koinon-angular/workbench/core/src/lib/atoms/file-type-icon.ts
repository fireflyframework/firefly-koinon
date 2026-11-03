// Copyright 2026 Firefly Software Foundation
// SPDX-License-Identifier: Apache-2.0
import { ChangeDetectionStrategy, Component, Input } from '@angular/core';
import { KoinonTextPipe, registerKoinonSpanish } from '../foundations/i18n';

export function fileType(filename: string, format = '') {
  const extension = (
    format ||
    filename
      .replace(/\.(gz|bz2|zip)$/i, '')
      .split('.')
      .pop() ||
    ''
  )
    .toLowerCase()
    .replace(/^\./, '');
  if (extension === 'pdf') return { label: 'PDF file', mark: 'PDF', tone: 'pdf' };
  if (['odt', 'ods', 'odp'].includes(extension))
    return {
      label: 'OpenDocument file',
      mark: extension.toUpperCase(),
      tone: extension === 'ods' ? 'sheet' : extension === 'odp' ? 'slides' : 'word',
    };
  if (['docx', 'doc'].includes(extension))
    return { label: 'Word document', mark: 'W', tone: 'word' };
  if (['xlsx', 'xls'].includes(extension))
    return { label: 'Spreadsheet', mark: 'X', tone: 'sheet' };
  if (['pptx', 'ppt'].includes(extension))
    return { label: 'Presentation', mark: 'P', tone: 'slides' };
  if (['csv', 'tsv'].includes(extension))
    return { label: 'Delimited data file', mark: extension.toUpperCase(), tone: 'sheet' };
  return { label: 'File', mark: '', tone: 'file' };
}
registerKoinonSpanish({
  'PDF file': 'Archivo PDF',
  'OpenDocument file': 'Archivo OpenDocument',
  'Word document': 'Documento de Word',
  Spreadsheet: 'Hoja de cálculo',
  Presentation: 'Presentación',
  'Delimited data file': 'Archivo de datos delimitados',
});
@Component({
  selector: 'ffk-file-type-icon',
  imports: [KoinonTextPipe],
  template: `<svg
    viewBox="0 0 32 38"
    role="img"
    [attr.aria-label]="type().label | ffkText"
    [attr.data-type]="type().tone"
  >
    <path
      d="M5 1.5h14l8 8V34a2.5 2.5 0 0 1-2.5 2.5h-19A2.5 2.5 0 0 1 3 34V4A2.5 2.5 0 0 1 5 1.5Z"
    />
    <path d="M19 2v8h8" />
    <text x="15" y="27" text-anchor="middle">{{ type().mark }}</text>
    @if (!type().mark) {
      <path d="M9 19h12M9 24h12M9 29h8" />
    }
  </svg>`,
  styles: [
    `
      :host {
        display: inline-flex;
        width: 30px;
        height: 36px;
        flex: none;
      }
      svg {
        width: 100%;
        height: 100%;
        fill: none;
        stroke: currentColor;
        stroke-width: 1.5;
        color: var(--ui-muted);
      }
      text {
        fill: currentColor;
        stroke: none;
        font:
          700 9px Manrope,
          sans-serif;
      }
      svg[data-type='word'] {
        color: var(--ffk-slate, var(--ui-accent));
      }
      svg[data-type='sheet'] {
        color: var(--ffk-olive, var(--ui-accent));
      }
      svg[data-type='slides'] {
        color: var(--ffk-gold, var(--ui-accent));
      }
      svg[data-type='pdf'] {
        color: var(--ffk-amber, var(--ui-accent));
      }
    `,
  ],
  changeDetection: ChangeDetectionStrategy.OnPush,
})
export class KoinonFileTypeIcon {
  @Input() filename = '';
  @Input() format = '';
  type() {
    return fileType(this.filename, this.format);
  }
}
