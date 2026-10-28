// Copyright 2026 Firefly Software Foundation SPDX-License-Identifier: Apache-2.0
import { KoinonTextPipe, KoinonI18n } from '@fireflyframework/koinon-angular';
import type { Presentation } from '@fireflyframework/koinon-sdk';
import { DOCUMENT } from '@angular/common';
import { KoinonIcon } from '@fireflyframework/koinon-angular';
import { Component, Input, ChangeDetectionStrategy, inject } from '@angular/core';
@Component({
  imports: [KoinonTextPipe, KoinonIcon],
  selector: 'ffk-evidence-table',
  template: ` <div
      class="table-wrap"
      [class.unframed]="!framed"
      tabindex="0"
      role="region"
      [attr.aria-label]="label"
    >
      <table>
        <thead>
          <tr>
            @for (column of columns(); track column) {
              <th>{{ column }}</th>
            }
          </tr>
        </thead>
        <tbody>
          @for (row of rows.slice(0, 500); track $index) {
            <tr>
              @for (column of columns(); track column) {
                <td [title]="rawValue(row[column])">{{ value(row[column], column) }}</td>
              }
            </tr>
          } @empty {
            <tr>
              <td [attr.colspan]="columns().length || 1">No rows were returned.</td>
            </tr>
          }
        </tbody>
      </table>
    </div>
    <div class="table-footer">
      <span>{{ rows.length }} {{ 'returned rows' | ffkText }}</span>
      <button
        type="button"
        [disabled]="!rows.length"
        [attr.aria-label]="'Download returned data (JSON)' | ffkText"
        (click)="download()"
      >
        <ffk-icon name="download" /> JSON
      </button>
    </div>
    @if (rows.length > 500) {
      <p class="limit">{{ 'Showing the first 500 returned rows.' | ffkText }}</p>
    }`,
  styles: `
    :host {
      display: block;
      min-width: 0;
    }
    .table-wrap {
      max-width: 100%;
      overflow: auto;
      max-height: 300px;
      border: 1px solid var(--ui-line, #d8d4ca);
      border-radius: 8px;
    }
    .table-wrap.unframed {
      border: 0;
      border-radius: 0;
    }
    .table-footer {
      display: flex;
      align-items: center;
      justify-content: space-between;
      gap: 12px;
      padding: 6px 12px;
      font: 400 10px/1.5 var(--ffk-font, 'Manrope Variable', sans-serif);
      color: var(--ui-muted);
    }
    .table-footer button {
      display: inline-flex;
      align-items: center;
      gap: 5px;
      min-height: 28px;
      padding: 4px 6px;
      border: 0;
      border-radius: 5px;
      background: transparent;
      color: var(--ui-muted);
      font: inherit;
      cursor: pointer;
    }
    .table-footer button:hover {
      background: var(--ui-subtle);
      color: var(--ui-text);
    }
    .table-footer button:disabled {
      cursor: default;
      opacity: 0.5;
    }
    .table-footer ffk-icon {
      font-size: 13px;
    }
    .table-footer button:focus-visible {
      outline: 2px solid var(--ui-focus, var(--ui-accent));
      outline-offset: 2px;
    }
    @media (pointer: coarse) {
      .table-footer button {
        min-height: 44px;
      }
    }
    .table-wrap:focus-visible {
      outline: 2px solid var(--ui-accent, #855414);
      outline-offset: 3px;
    }
    table {
      width: 100%;
      border-collapse: collapse;
      text-align: left;
      font: 400 12px/1.6 var(--ffk-font, 'Manrope Variable', sans-serif);
      color: var(--ui-text, #272820);
    }
    th,
    td {
      padding: 11px 14px;
      border-bottom: 1px solid var(--ui-line, #d8d4ca);
      min-width: 90px;
      max-width: 360px;
      overflow-wrap: anywhere;
      vertical-align: top;
    }
    th {
      font-size: 11px;
      font-weight: 550;
      color: var(--ui-muted, #62645b);
      background: var(--ui-subtle, #f6f5f1);
    }
    tr:last-child td {
      border-bottom: 0;
    }
    .limit {
      font-size: 10px;
      color: var(--ui-muted);
      margin-top: 10px;
    }
  `,
  changeDetection: ChangeDetectionStrategy.OnPush,
})
export class KoinonEvidenceTable {
  private readonly i18n = inject(KoinonI18n);
  private readonly document = inject(DOCUMENT);
  @Input() presentation?: Presentation;
  @Input() columnTypes: Record<string, string> = {};
  @Input() rows: Record<string, unknown>[] = [];
  @Input() label = 'Evidence results';
  @Input() framed = true;
  columns() {
    return Object.keys(this.rows[0] ?? {});
  }
  value(value: unknown, column: string) {
    return this.i18n.value(value, this.columnTypes[column], this.presentation);
  }
  rawValue(value: unknown) {
    return value === null || value === undefined
      ? ''
      : typeof value === 'object'
        ? JSON.stringify(value)
        : String(value);
  }
  rawJson() {
    return JSON.stringify(this.rows, null, 2);
  }
  download() {
    const url = URL.createObjectURL(new Blob([this.rawJson()], { type: 'application/json' }));
    const link = this.document.createElement('a');
    link.href = url;
    link.download = 'evidence-preview.json';
    link.click();
    setTimeout(() => URL.revokeObjectURL(url), 0);
  }
}
