// Copyright 2026 Firefly Software Foundation SPDX-License-Identifier: Apache-2.0
import { KoinonTextPipe, KoinonI18n } from '../foundations/i18n';
import {
  Component,
  Input,
  Output,
  EventEmitter,
  ChangeDetectionStrategy,
  inject,
} from '@angular/core';
import { FormsModule } from '@angular/forms';
import type { Page } from '@fireflyframework/koinon-sdk';
import { KoinonButton } from '../atoms/button';
@Component({
  selector: 'ffk-pagination',
  imports: [KoinonTextPipe, FormsModule, KoinonButton],
  template: `@if (
    page &&
    page.page !== undefined &&
    page.pages !== undefined &&
    page.total !== undefined &&
    page.total > 0
  ) {
    <nav [attr.aria-label]="(label | ffkText) + ' ' + ('pagination' | ffkText)">
      <span>{{ range() }} {{ 'of' | ffkText }} {{ page.total }} {{ 'items' | ffkText }}</span>
      @if (showPageSize) {
        <label
          >{{ 'Per page' | ffkText
          }}<select
            [attr.aria-label]="(label | ffkText) + ' ' + ('Items per page' | ffkText)"
            [ngModel]="page.page_size || 25"
            (ngModelChange)="sizeChanged.emit(+$event)"
          >
            <option [value]="25">25</option>
            <option [value]="50">50</option>
            <option [value]="100">100</option>
          </select></label
        >
      }
      <div>
        <ffk-button
          variant="quiet"
          icon="chevron-left"
          [label]="pageLabel('Previous')"
          [disabled]="loading || page.page <= 1"
          (click)="pageChanged.emit(page.page - 1)"
        /><span>{{ 'Page' | ffkText }} {{ page.page }} {{ 'of' | ffkText }} {{ page.pages }}</span
        ><ffk-button
          variant="quiet"
          icon="chevron"
          [label]="pageLabel('Next')"
          [disabled]="loading || page.page >= page.pages"
          (click)="pageChanged.emit(page.page + 1)"
        />
      </div>
    </nav>
  }`,
  styles: `
    :host {
      display: block;
      min-width: 0;
    }
    nav {
      display: flex;
      align-items: center;
      gap: 18px;
      flex-wrap: wrap;
      padding: 20px 4px;
      font: 400 10px/1.6 var(--ffk-font, 'Manrope Variable', sans-serif);
      color: var(--ui-muted);
    }
    nav > div {
      display: flex;
      align-items: center;
      gap: 7px;
      margin-left: auto;
    }
    label {
      display: flex;
      align-items: center;
      gap: 8px;
      font-size: 10px;
    }
    select {
      font: 500 10px var(--ffk-font, 'Manrope Variable', sans-serif);
      border: 1px solid var(--ui-line);
      border-radius: 5px;
      background: var(--ui-surface);
      color: var(--ui-text);
      padding: 5px;
      cursor: pointer;
    }
    select:focus-visible {
      outline: 2px solid var(--ui-accent);
      outline-offset: 3px;
    }
    @media (max-width: 700px) {
      nav {
        gap: 12px;
        justify-content: space-between;
      }
      label {
        display: none;
      }
    }
  `,
  changeDetection: ChangeDetectionStrategy.OnPush,
})
export class KoinonPagination {
  private readonly i18n = inject(KoinonI18n);
  pageLabel(direction: 'Next' | 'Previous') {
    return this.i18n.preferences().locale.startsWith('es')
      ? this.i18n.text(direction + ' page') + ' · ' + this.i18n.text(this.label)
      : direction + ' ' + this.label.toLowerCase() + ' page';
  }
  @Input() page: Page<unknown> | null = null;
  @Input() label = 'Results';
  @Input() loading = false;
  @Input() showPageSize = true;
  @Output() pageChanged = new EventEmitter<number>();
  @Output() sizeChanged = new EventEmitter<number>();
  range() {
    if (!this.page?.total) return '0';
    const start = ((this.page.page ?? 1) - 1) * (this.page.page_size ?? 25) + 1;
    return start + '–' + Math.min(this.page.total, start + this.page.items.length - 1);
  }
}
