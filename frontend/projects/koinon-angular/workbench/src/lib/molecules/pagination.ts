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
import type { Page } from '@fireflyframework/koinon-sdk';
import { KoinonButton } from '../atoms/button';
@Component({
  selector: 'ffk-pagination',
  imports: [KoinonTextPipe, KoinonButton],
  template: `@if (
    page &&
    page.page !== undefined &&
    page.pages !== undefined &&
    page.total !== undefined &&
    page.total > 0
  ) {
    <nav [attr.aria-label]="(label | ffkText) + ' ' + ('pagination' | ffkText)">
      <span class="range"
        >{{ range() }} {{ 'of' | ffkText }} {{ page.total }}
        {{ (page.total === 1 ? 'item' : 'items') | ffkText }}</span
      >
      @if (showPageSize) {
        <label
          >{{ 'Per page' | ffkText
          }}<select
            [attr.aria-label]="(label | ffkText) + ' ' + ('Items per page' | ffkText)"
            [value]="page.page_size || 25"
            [disabled]="loading"
            (change)="changeSize($event)"
          >
            <option [value]="25">25</option>
            <option [value]="50">50</option>
            <option [value]="100">100</option>
          </select></label
        >
      }
      <div class="page-navigation">
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
      container: koinon-pagination / inline-size;
    }
    nav {
      display: flex;
      align-items: center;
      gap: 12px 20px;
      flex-wrap: wrap;
      padding: 16px 4px;
      font: 400 12px/1.5 var(--ffk-font, 'Manrope Variable', sans-serif);
      color: var(--ui-muted);
    }
    .page-navigation {
      display: flex;
      align-items: center;
      gap: 7px;
      margin-left: auto;
    }
    label {
      display: flex;
      align-items: center;
      gap: 8px;
      font-size: 12px;
      white-space: nowrap;
      flex-shrink: 0;
    }
    select {
      font: 500 12px var(--ffk-font, 'Manrope Variable', sans-serif);
      border: 1px solid var(--ui-line);
      border-radius: 5px;
      background: var(--ui-surface);
      color: var(--ui-text);
      padding: 6px 8px;
      min-height: 34px;
      cursor: pointer;
    }
    .range,
    .page-navigation {
      white-space: nowrap;
    }
    select:disabled {
      cursor: wait;
      opacity: 0.6;
    }
    select:focus-visible {
      outline: 2px solid var(--ui-accent);
      outline-offset: 3px;
    }
    @container koinon-pagination (max-width: 700px) {
      nav {
        gap: 12px;
        justify-content: space-between;
      }
      .page-navigation {
        flex-basis: 100%;
        justify-content: flex-end;
      }
      nav {
        padding-block: 14px;
        font-size: 11px;
      }
      label {
        font-size: 11px;
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
  changeSize(event: Event) {
    const size = Number((event.target as HTMLSelectElement).value);
    if (!this.loading && [25, 50, 100].includes(size)) this.sizeChanged.emit(size);
  }
  range() {
    if (!this.page?.total) return '0';
    const start = ((this.page.page ?? 1) - 1) * (this.page.page_size ?? 25) + 1;
    return start + '–' + Math.min(this.page.total, start + this.page.items.length - 1);
  }
}
