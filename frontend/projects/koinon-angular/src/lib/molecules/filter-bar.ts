// Copyright 2026 Firefly Software Foundation
// SPDX-License-Identifier: Apache-2.0
import { ChangeDetectionStrategy, Component, EventEmitter, Input, Output } from '@angular/core';
import { NgTemplateOutlet } from '@angular/common';
import { KoinonButton } from '@fireflyframework/koinon-angular/workbench';
import { KoinonIcon } from '@fireflyframework/koinon-angular/workbench';
import { KoinonTextPipe } from '@fireflyframework/koinon-angular/workbench';
let nextFilterBar = 0;
@Component({
  selector: 'ffk-filter-bar',
  imports: [NgTemplateOutlet, KoinonButton, KoinonIcon, KoinonTextPipe],
  template: ` <ng-template #actions
      ><div class="actions">
        @if (draftChanges) {
          <ffk-button variant="quiet" [disabled]="loading" (click)="resetRequested.emit()">{{
            'Reset changes' | ffkText
          }}</ffk-button>
        }
        <ffk-button
          variant="primary"
          [disabled]="loading || !draftChanges"
          (click)="applyRequested.emit()"
          >{{ 'Apply filters' | ffkText }}</ffk-button
        >
      </div></ng-template
    >
    <section class="filter-bar" [attr.aria-label]="label | ffkText">
      <div class="main"><ng-content select="[filterMain]" /></div>
      <div class="toolbar">
        <button
          type="button"
          class="toggle"
          [attr.aria-label]="'More filters' | ffkText"
          (click)="expandedChange.emit(!expanded)"
          [attr.aria-expanded]="expanded"
          [attr.aria-controls]="expanded ? regionId : null"
        >
          <ffk-icon name="filter" />{{ 'Filters' | ffkText }}
          @if (activeCount) {
            <span class="count">{{ activeCount }}</span>
          }
        </button>
        @if (!expanded) {
          <ng-container [ngTemplateOutlet]="actions" />
        }
      </div>
      @if (expanded) {
        <div class="expanded" [id]="regionId">
          <ng-content select="[filterFields]" />
          <div class="footer">
            @if (draftChanges) {
              <p class="draft" role="status">
                {{ 'Filters changed. Apply to update the list.' | ffkText }}
              </p>
            }
            <ng-container [ngTemplateOutlet]="actions" />
          </div>
        </div>
      } @else if (draftChanges) {
        <p class="draft" role="status">
          {{ 'Filters changed. Apply to update the list.' | ffkText }}
        </p>
      }
      @if (activeCount) {
        <div class="active">
          <div class="chips" [attr.aria-label]="'Active filters' | ffkText">
            <ng-content select="[filterChips]" />
          </div>
          <ffk-button variant="quiet" [disabled]="loading" (click)="clearRequested.emit()">{{
            'Clear filters' | ffkText
          }}</ffk-button>
        </div>
      }
    </section>`,
  styleUrl: './filter-bar.scss',
  changeDetection: ChangeDetectionStrategy.OnPush,
})
export class KoinonFilterBar {
  @Input() label = 'Audit filters';
  @Input() expanded = false;
  @Input() draftChanges = false;
  @Input() activeCount = 0;
  @Input() loading = false;
  @Output() expandedChange = new EventEmitter<boolean>();
  @Output() applyRequested = new EventEmitter<void>();
  @Output() resetRequested = new EventEmitter<void>();
  @Output() clearRequested = new EventEmitter<void>();
  readonly regionId = 'koinon-filter-fields-' + ++nextFilterBar;
}
