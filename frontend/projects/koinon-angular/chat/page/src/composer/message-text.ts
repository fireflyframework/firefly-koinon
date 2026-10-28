// Copyright 2026 Firefly Software Foundation
// SPDX-License-Identifier: Apache-2.0
import {
  ChangeDetectionStrategy,
  Component,
  EventEmitter,
  Input,
  OnChanges,
  Output,
} from '@angular/core';
import type { AttachmentHistorySummary } from '@fireflyframework/koinon-sdk';
import { KoinonTextPipe } from '@fireflyframework/koinon-angular';
interface Part { text: string; file?: AttachmentHistorySummary }
@Component({
  selector: 'ffk-message-text',
  imports: [KoinonTextPipe],
  changeDetection: ChangeDetectionStrategy.OnPush,
  template: `@for (part of parts; track $index) {
    @if (part.file; as file) {
      <button
        type="button"
        [disabled]="!file.available"
        [title]="(file.available ? 'Download source file' : 'File no longer available') | ffkText"
        (click)="sourceSelected.emit(file)"
        [textContent]="part.text"
      ></button>
    } @else {
      <span [textContent]="part.text"></span>
    }
  }`,
  styles: `
    :host {
      display: contents;
    }
    button {
      display: inline;
      padding: 0;
      border: 0;
      border-radius: 2px;
      background: transparent;
      color: var(--ui-accent, #855414);
      font: inherit;
      text-align: inherit;
      white-space: inherit;
      overflow-wrap: anywhere;
      text-decoration: underline;
      text-underline-offset: 3px;
      cursor: pointer;
    }
    button:disabled {
      color: inherit;
      text-decoration-style: dotted;
      cursor: default;
    }
    button:focus-visible {
      outline: 2px solid var(--ui-focus, var(--ui-accent));
      outline-offset: 3px;
    }
  `,
})
export class KoinonMessageText implements OnChanges {
  @Input() text = '';
  @Input() references: readonly AttachmentHistorySummary[] = [];
  @Output() sourceSelected = new EventEmitter<AttachmentHistorySummary>();
  parts: Part[] = [];
  ngOnChanges() {
    const files = new Map(this.references.map((file) => [file.id, file]));
    const parts: Part[] = [];
    let cursor = 0;
    for (const match of this.text.matchAll(/Attachment ([^\s:]{1,128}): /g)) {
      const file = files.get(match[1]);
      const start = match.index ?? 0,
        end = start + match[0].length;
      if (!file || !this.text.startsWith(file.filename, end) || start < cursor) continue;
      if (start > cursor) parts.push({ text: this.text.slice(cursor, start) });
      parts.push({ text: file.filename, file });
      cursor = end + file.filename.length;
    }
    if (cursor < this.text.length || !parts.length) parts.push({ text: this.text.slice(cursor) });
    this.parts = parts;
  }
}
