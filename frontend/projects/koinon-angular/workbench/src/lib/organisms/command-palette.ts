// Copyright 2026 Firefly Software Foundation
// SPDX-License-Identifier: Apache-2.0
import { Component, ChangeDetectionStrategy, Input, Output, EventEmitter } from '@angular/core';
import type { CatalogEntry } from '@fireflyframework/koinon-sdk';
import { KoinonCommandPaletteContent } from './command-palette-content';
import { KoinonTextPipe } from '../foundations/i18n';
export interface KoinonCommand {
  id: string;
  title: string;
  description?: string;
  icon?: string;
  disabled?: boolean;
}
@Component({
  selector: 'ffk-command-palette',
  imports: [KoinonCommandPaletteContent, KoinonTextPipe],
  template: ` @if (open) {
    @defer (on immediate) {
      <ffk-command-palette-content
        [open]="open"
        [commands]="commands"
        (closed)="closed.emit()"
        (commandSelected)="commandSelected.emit($event)"
        (resourceSelected)="resourceSelected.emit($event)"
        (searchRequested)="searchRequested.emit($event)"
      />
    } @loading {
      <span role="status">{{ 'Loading search…' | ffkText }}</span>
    } @error {
      <button type="button" (click)="closed.emit()">
        {{ 'Search could not be opened. Close and try again.' | ffkText }}
      </button>
    }
  }`,
  changeDetection: ChangeDetectionStrategy.OnPush,
})
export class KoinonCommandPalette {
  @Input() open = false;
  @Input() commands: readonly KoinonCommand[] = [];
  @Output() readonly closed = new EventEmitter<void>();
  @Output() readonly commandSelected = new EventEmitter<string>();
  @Output() readonly resourceSelected = new EventEmitter<CatalogEntry>();
  @Output() readonly searchRequested = new EventEmitter<string>();
}
