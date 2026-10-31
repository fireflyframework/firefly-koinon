// Copyright 2026 Firefly Software Foundation SPDX-License-Identifier: Apache-2.0
import { KoinonTextPipe, KoinonDatePipe } from '../foundations/i18n';
import {
  Component,
  Input,
  Output,
  EventEmitter,
  ChangeDetectionStrategy,
  inject,
} from '@angular/core';
import type {
  CatalogEntry,
  CatalogFilter,
  CatalogSummary,
  PublicActor,
} from '@fireflyframework/koinon-sdk';
import { KoinonI18n } from '../foundations/i18n';
import { KoinonIcon } from '../atoms/icon';
import { KoinonBadge } from '../atoms/badge';
import { KoinonSkeleton } from '../atoms/skeleton';
import { friendlyStatus, friendlyKind, isFolder, resourceIcon } from '../services/library-tree';
@Component({
  selector: 'ffk-resource-list',
  imports: [KoinonTextPipe, KoinonDatePipe, KoinonIcon, KoinonBadge, KoinonSkeleton],
  templateUrl: './resource-list.html',
  styleUrl: './resource-list.scss',
  changeDetection: ChangeDetectionStrategy.OnPush,
})
export class KoinonResourceList {
  private readonly i18n = inject(KoinonI18n);
  private readonly languageNames = new Map<string, Intl.DisplayNames>();
  @Input() summaries: Record<string, CatalogSummary> = {};
  @Output() tagSelected = new EventEmitter<string>();
  contents(item: CatalogEntry) {
    const summary = this.summaries[item.id];
    if (!summary) return '';
    const parts: string[] = [];
    const count = (value: number | null, singular: string, plural: string) => {
      if (value !== null && Number.isSafeInteger(value) && value >= 0)
        parts.push(
          new Intl.NumberFormat(this.i18n.preferences().locale).format(value) +
            ' ' +
            this.i18n.text(value === 1 ? singular : plural),
        );
    };
    if (isFolder(item)) count(summary.child_count, 'item', 'items');
    else if (item.kind === 'dataset') {
      count(summary.table_count, 'table', 'tables');
      count(summary.row_count, 'row', 'rows');
      count(summary.column_count, 'column', 'columns');
    } else count(summary.page_count, 'page', 'pages');
    if (
      summary.size_bytes !== null &&
      Number.isFinite(summary.size_bytes) &&
      summary.size_bytes >= 0
    ) {
      const unit = summary.size_bytes >= 1048576 ? 1048576 : summary.size_bytes >= 1024 ? 1024 : 1;
      parts.push(
        new Intl.NumberFormat(this.i18n.preferences().locale, { maximumFractionDigits: 1 }).format(
          summary.size_bytes / unit,
        ) +
          ' ' +
          (unit === 1048576 ? 'MB' : unit === 1024 ? 'KB' : 'B'),
      );
    }
    return parts.join(', ');
  }
  tagLabel(item: CatalogEntry, tag: string) {
    const summary = this.summaries[item.id];
    const key = tag.toLowerCase();
    if (summary?.format && key === summary.format.toLowerCase()) return tag.toUpperCase();
    if (!summary?.language || key !== summary.language.toLowerCase()) return tag;
    const locale = this.i18n.preferences().locale;
    try {
      let names = this.languageNames.get(locale);
      if (!names) {
        names = new Intl.DisplayNames([locale], { type: 'language', fallback: 'none' });
        this.languageNames.set(locale, names);
      }
      const language = names.of(summary.language);
      return language ? language[0].toLocaleUpperCase(locale) + language.slice(1) : tag;
    } catch {
      return tag;
    }
  }
  tags(item: CatalogEntry) {
    return this.summaries[item.id]?.tags ?? [];
  }
  @Input() sortable = false;
  @Input() sort: CatalogFilter['sort'] = 'name';
  @Input() order: CatalogFilter['order'] = 'asc';
  @Output() sortRequested = new EventEmitter<NonNullable<CatalogFilter['sort']>>();
  sortState(key: CatalogFilter['sort']) {
    return this.sortable && this.sort === key
      ? this.order === 'desc'
        ? 'descending'
        : 'ascending'
      : 'none';
  }
  sortMark(key: CatalogFilter['sort']) {
    return this.sort === key ? (this.order === 'desc' ? '↓' : '↑') : '↕';
  }
  @Input() actors: Record<string, PublicActor> = {};
  actorName(subject: string | undefined) {
    return subject ? this.actors[subject]?.display_name || this.i18n.text('Name unavailable') : '';
  }
  @Input() items: CatalogEntry[] = [];
  @Input() selectedId = '';
  @Input() loading = false;
  @Input() emptyTitle = 'This folder is ready for knowledge';
  @Input() emptyDescription = 'Add files here to make them available to your team.';
  @Output() opened = new EventEmitter<CatalogEntry>();
  @Output() selected = new EventEmitter<CatalogEntry>();
  readonly status = friendlyStatus;
  readonly kind = friendlyKind;
  readonly icon = resourceIcon;
  readonly isFolder = isFolder;
}
