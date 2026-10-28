// Copyright 2026 Firefly Software Foundation SPDX-License-Identifier: Apache-2.0
import { KoinonTextPipe } from '../foundations/i18n';
import { Component, Input, Output, EventEmitter, ChangeDetectionStrategy } from '@angular/core';
import type { CatalogEntry, CatalogFilter, Page, ResourceKind } from '@fireflyframework/koinon-sdk';
import { KoinonPagination } from '../molecules/pagination';
import { KoinonButton } from '../atoms/button';
import { KoinonBreadcrumb } from '../molecules/breadcrumb';
import { KoinonSearchField } from '../molecules/search-field';
import { KoinonResourceList } from '../organisms/resource-list';
import { friendlyStatus } from '../services/library-tree';
@Component({
  selector: 'ffk-library-template',
  imports: [
    KoinonTextPipe,
    KoinonPagination,
    KoinonButton,
    KoinonBreadcrumb,
    KoinonSearchField,
    KoinonResourceList,
  ],
  template: `<section class="library-grid" [attr.aria-label]="'Knowledge library' | ffkText">
    <div class="breadcrumb">
      <ffk-breadcrumb [items]="trail" (folderSelected)="folderSelected.emit($event)" />
      <div class="location-actions">
        @if (canAdd) {
          <ffk-button variant="quiet" icon="history" (click)="archivedRequested.emit()">{{
            'Archived' | ffkText
          }}</ffk-button>
        }
        @if (browseAvailable) {
          <ffk-button variant="quiet" icon="lineage" (click)="browseRequested.emit()">{{
            'Browse folders' | ffkText
          }}</ffk-button>
        }
      </div>
    </div>
    <header class="library-heading">
      <div>
        <h1>{{ title }}</h1>
        <p [class.generic-description]="descriptionIsGeneric">{{ description }}</p>
      </div>
      @if (canAdd) {
        <ffk-button
          class="desktop-add"
          variant="primary"
          icon="plus"
          (click)="addRequested.emit()"
          >{{ 'Add knowledge' | ffkText }}</ffk-button
        >
        <ffk-button
          class="compact-add"
          variant="primary"
          icon="plus"
          [label]="'Add knowledge' | ffkText"
          (click)="addRequested.emit()"
        />
      }
    </header>
    <div class="collection-surface">
      <div class="library-toolbar">
        @if (serverControls) {
          <div class="name-filter">
            <ffk-search-field
              [value]="nameFilter"
              (valueChange)="nameFilter = $event"
              [actionLabel]="'Apply folder filter' | ffkText"
              [label]="'Filter this folder by name' | ffkText"
              [placeholder]="'Filter this folder by name' | ffkText"
              (searchSubmitted)="filterChanged.emit({ q: $event, page: 1 })"
            />
          </div>
          @if (allowedKinds.length > 1) {
            <label class="sort"
              ><span>{{ 'Type' | ffkText }}</span
              ><select
                [attr.aria-label]="'Filter library type' | ffkText"
                [value]="filter.kind || ''"
                (change)="filterChanged.emit({ kind: $any($event.target).value || undefined, page: 1 })"
              >
                <option value="">{{ 'All types' | ffkText }}</option>
                @for (kind of allowedKinds; track kind.value) {
                  <option [value]="kind.value">{{ kind.label | ffkText }}</option>
                }
              </select></label
            >
          }
          <details class="filter-options">
            <summary>{{ 'More filters' | ffkText }}</summary>
            <form (submit)="applyMetadataFilters($event)">
              <label
                >{{ 'Status' | ffkText
                }}<select name="status" [value]="statusFilter" (change)="statusFilter=$any($event.target).value">
                  <option value="">{{ 'All statuses' | ffkText }}</option>
                  <option value="ready">{{ 'Ready' | ffkText }}</option>
                  <option value="processing">{{ 'Processing' | ffkText }}</option>
                  <option value="failed">{{ 'Needs attention' | ffkText }}</option>
                </select></label
              >
              <label
                >{{ 'Format' | ffkText
                }}<input
                  name="format"
                  [value]="formatFilter" (input)="formatFilter=$any($event.target).value"
                  [placeholder]="'e.g. pdf' | ffkText"
              /></label>
              <label
                >{{ 'Tag' | ffkText
                }}<input name="tag" [value]="tagFilter" (input)="tagFilter=$any($event.target).value" [placeholder]="'Exact tag' | ffkText"
              /></label>
              <label
                >{{ 'Sort' | ffkText
                }}<select name="sort" [value]="metadataSort" (change)="metadataSort=$any($event.target).value">
                  @for (option of sortOptions; track option.value) {
                    <option [value]="option.value">{{ option.label | ffkText }}</option>
                  }
                </select></label
              >
              <ffk-button variant="neutral" type="submit">{{
                'Apply filters' | ffkText
              }}</ffk-button>
            </form>
          </details>
          <label class="sort mobile-sort"
            ><span>{{ 'Sort' | ffkText }}</span
            ><select
              [attr.aria-label]="'Sort library items' | ffkText"
              [value]="sortKey()"
              (change)="sort($any($event.target).value)"
            >
              @for (option of sortOptions; track option.value) {
                <option [value]="option.value">{{ option.label | ffkText }}</option>
              }
            </select></label
          >
        }
        <span class="item-count"
          >{{ pageInfo?.total ?? items.length }}
          {{ ((pageInfo?.total ?? items.length) === 1 ? 'item' : 'items') | ffkText }}</span
        >
      </div>
      @if (serverControls && hasFilters()) {
        <div class="active-filters" [attr.aria-label]="'Active filters' | ffkText">
          @if (filter.q) {
            <button
              class="filter-chip"
              [attr.aria-label]="'Clear folder filter' | ffkText"
              (click)="filterChanged.emit({ q: '', page: 1 })"
            >
              {{ filter.q }} <span aria-hidden="true">×</span
              ><span class="sr-only">{{ 'Clear folder filter' | ffkText }}</span>
            </button>
          }
          @if (filter.kind) {
            <button class="filter-chip" (click)="filterChanged.emit({ kind: undefined, page: 1 })">
              {{ kindLabel() | ffkText }} <span aria-hidden="true">×</span
              ><span class="sr-only">{{ 'Clear type filter' | ffkText }}</span>
            </button>
          }
          @if (filter.tag) {
            <button class="filter-chip" (click)="filterChanged.emit({ tag: undefined, page: 1 })">
              {{ filter.tag }} <span aria-hidden="true">×</span
              ><span class="sr-only">{{ 'Clear tag filter' | ffkText }}</span>
            </button>
          }
          @if (filter.format) {
            <button
              class="filter-chip"
              (click)="filterChanged.emit({ format: undefined, page: 1 })"
            >
              {{ filter.format }} <span aria-hidden="true">×</span
              ><span class="sr-only">{{ 'Clear format filter' | ffkText }}</span>
            </button>
          }
          @if (filter.status) {
            <button
              class="filter-chip"
              (click)="filterChanged.emit({ status: undefined, page: 1 })"
            >
              {{ statusLabel(filter.status) | ffkText }} <span aria-hidden="true">×</span
              ><span class="sr-only">{{ 'Clear status filter' | ffkText }}</span>
            </button>
          }
          <button class="clear-filters" (click)="clearFilters()">
            {{ 'Clear filters' | ffkText }}
          </button>
        </div>
      }
      <div class="list">
        <ffk-resource-list
          [items]="items"
          [sortable]="serverControls"
          [sort]="filter.sort || 'name'"
          [order]="filter.order || 'asc'"
          (sortRequested)="sortColumn($event)"
          [actors]="pageInfo?.actors || {}"
          [summaries]="pageInfo?.summaries || {}"
          (tagSelected)="filterChanged.emit({ tag: $event, page: 1 })"
          [selectedId]="selectedId"
          [loading]="loading"
          [emptyTitle]="hasFilters() ? 'No matching items' : emptyTitle"
          [emptyDescription]="
            hasFilters() ? 'Try another name or clear the folder filter.' : emptyDescription
          "
          (opened)="opened.emit($event)"
          (selected)="selected.emit($event)"
        />
      </div>
      @if (serverControls) {
        <ffk-pagination
          class="pagination"
          [page]="pageInfo"
          [label]="'Library' | ffkText"
          [loading]="loading"
          (pageChanged)="filterChanged.emit({ page: $event })"
          (sizeChanged)="filterChanged.emit({ page_size: $event, page: 1 })"
        />
      }
    </div>
  </section>`,
  styleUrl: './library-template.scss',
  changeDetection: ChangeDetectionStrategy.OnPush,
})
export class KoinonLibraryTemplate {
  readonly statusLabel = friendlyStatus;
  readonly sortOptions = [
    { value: 'name.asc', label: 'Name · A to Z' },
    { value: 'name.desc', label: 'Name · Z to A' },
    { value: 'kind.asc', label: 'Type' },
    { value: 'kind.desc', label: 'Type · descending' },
    { value: 'updated_at.desc', label: 'Recently updated' },
    { value: 'updated_at.asc', label: 'Oldest update' },
    { value: 'created_at.desc', label: 'Recently added' },
  ];
  @Input() allowedKinds: { value: ResourceKind; label: string }[] = [];
  @Input() title = 'Library';
  @Input() descriptionIsGeneric = false;
  @Input() description = 'A shared home for your team’s documents and data.';
  @Input() trail: CatalogEntry[] = [];
  @Input() items: CatalogEntry[] = [];
  @Input() selectedId = '';
  @Input() loading = false;
  @Input() canAdd = false;
  @Input() browseAvailable = false;
  @Input() serverControls = false;
  @Input() pageInfo: Page<CatalogEntry> | null = null;
  @Input() set filter(value: CatalogFilter) {
    const orderChanged = this.sortKey() !== (value.sort ?? 'name') + '.' + (value.order ?? 'asc');
    this.activeFilter = value;
    this.nameFilter = value.q ?? '';
    this.statusFilter = value.status ?? '';
    this.formatFilter = value.format ?? '';
    this.tagFilter = value.tag ?? '';
    if (orderChanged) this.metadataSort = this.sortKey();
  }
  get filter() {
    return this.activeFilter;
  }
  private activeFilter: CatalogFilter = {};
  nameFilter = '';
  statusFilter = '';
  formatFilter = '';
  tagFilter = '';
  metadataSort = 'name.asc';
  applyMetadataFilters(event: Event) {
    event.preventDefault();
    const sorting = this.metadataSort !== this.sortKey() ? this.sorting(this.metadataSort) : null;
    this.filterChanged.emit({
      ...(sorting ?? {}),
      status: this.statusFilter || undefined,
      format: this.formatFilter.trim().toLowerCase() || undefined,
      tag: this.tagFilter.trim().toLowerCase() || undefined,
      page: 1,
    });
  }
  @Input() emptyTitle = 'Your knowledge starts here';
  @Input() emptyDescription = 'Create a space to bring your team’s documents and data together.';
  @Output() folderSelected = new EventEmitter<string>();
  @Output() opened = new EventEmitter<CatalogEntry>();
  @Output() selected = new EventEmitter<CatalogEntry>();
  @Output() addRequested = new EventEmitter<void>();
  @Output() browseRequested = new EventEmitter<void>();
  @Output() archivedRequested = new EventEmitter<void>();
  @Output() filterChanged = new EventEmitter<CatalogFilter>();
  hasFilters() {
    return !!(
      this.filter.q ||
      this.filter.kind ||
      this.filter.status ||
      this.filter.tag ||
      this.filter.format
    );
  }
  kindLabel() {
    return (
      this.allowedKinds.find((kind) => kind.value === this.filter.kind)?.label ??
      this.filter.kind ??
      ''
    );
  }
  clearFilters() {
    this.filterChanged.emit({
      q: '',
      kind: undefined,
      status: undefined,
      tag: undefined,
      format: undefined,
      page: 1,
    });
  }
  sortColumn(sort: NonNullable<CatalogFilter['sort']>) {
    this.filterChanged.emit({
      sort,
      order:
        (this.filter.sort ?? 'name') === sort && (this.filter.order ?? 'asc') !== 'desc'
          ? 'desc'
          : 'asc',
      page: 1,
    });
  }
  sortKey() {
    return (this.filter.sort ?? 'name') + '.' + (this.filter.order ?? 'asc');
  }
  private sorting(value: string): Pick<CatalogFilter, 'sort' | 'order'> | null {
    const [sort, order] = value.split('.');
    return ['name', 'kind', 'updated_at', 'created_at'].includes(sort) &&
      ['asc', 'desc'].includes(order)
      ? { sort: sort as CatalogFilter['sort'], order: order as 'asc' | 'desc' }
      : null;
  }
  sort(value: string) {
    const sorting = this.sorting(value);
    if (sorting) this.filterChanged.emit({ ...sorting, page: 1 });
  }
  pageChanged(delta: number) {
    this.filterChanged.emit({ page: (this.pageInfo?.page ?? 1) + delta });
  }
  range() {
    const page = this.pageInfo;
    if (!page?.total) return '0';
    const start = ((page.page ?? 1) - 1) * (page.page_size ?? 25) + 1;
    return start + '–' + Math.min(page.total, start + this.items.length - 1);
  }
}
