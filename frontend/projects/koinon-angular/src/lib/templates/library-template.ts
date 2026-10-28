// Copyright 2026 Firefly Software Foundation SPDX-License-Identifier: Apache-2.0
import { KoinonTextPipe } from '../foundations/i18n';
import { Component, Input, Output, EventEmitter, ChangeDetectionStrategy } from '@angular/core';
import { FormsModule } from '@angular/forms';
import type { CatalogEntry, CatalogFilter, Page, ResourceKind } from '@fireflyframework/koinon-sdk';
import { KoinonPagination } from '../molecules/pagination';
import { KoinonButton } from '../atoms/button';
import { KoinonBreadcrumb } from '../molecules/breadcrumb';
import { KoinonSearchField } from '../molecules/search-field';
import { KoinonResourceList } from '../organisms/resource-list';
@Component({
  selector: 'ffk-library-template',
  imports: [
    KoinonTextPipe,
    FormsModule,
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
        <p>{{ description }}</p>
      </div>
      @if (canAdd) {
        <ffk-button variant="primary" icon="plus" (click)="addRequested.emit()">{{
          'Add knowledge' | ffkText
        }}</ffk-button>
      }
    </header>
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
          @if (filter.q) {
            <ffk-button
              variant="quiet"
              icon="close"
              [label]="'Clear folder filter' | ffkText"
              (click)="filterChanged.emit({ q: '', page: 1 })"
            />
          }
        </div>
        @if (allowedKinds.length > 1) {
          <label class="sort"
            ><span>{{ 'Type' | ffkText }}</span
            ><select
              [attr.aria-label]="'Filter library type' | ffkText"
              [ngModel]="filter.kind || ''"
              (ngModelChange)="filterChanged.emit({ kind: $event || undefined, page: 1 })"
            >
              <option value="">{{ 'All types' | ffkText }}</option>
              @for (kind of allowedKinds; track kind.value) {
                <option [value]="kind.value">{{ kind.label | ffkText }}</option>
              }
            </select></label
          >
        }
        <label class="sort"
          ><span>{{ 'Sort' | ffkText }}</span
          ><select
            [attr.aria-label]="'Sort library items' | ffkText"
            [ngModel]="sortKey()"
            (ngModelChange)="sort($event)"
          >
            <option value="name.asc">{{ 'Name · A to Z' | ffkText }}</option>
            <option value="name.desc">{{ 'Name · Z to A' | ffkText }}</option>
            <option value="updated_at.desc">{{ 'Recently updated' | ffkText }}</option>
            <option value="created_at.desc">{{ 'Recently added' | ffkText }}</option>
          </select></label
        >
      }
      <span class="item-count"
        >{{ pageInfo?.total ?? items.length }}
        {{ ((pageInfo?.total ?? items.length) === 1 ? 'item' : 'items') | ffkText }}</span
      >
    </div>
    <div class="list">
      <ffk-resource-list
        [items]="items"
        [actors]="pageInfo?.actors || {}"
        [selectedId]="selectedId"
        [loading]="loading"
        [emptyTitle]="filter.q ? 'No matching items' : emptyTitle"
        [emptyDescription]="
          filter.q ? 'Try another name or clear the folder filter.' : emptyDescription
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
  </section>`,
  styleUrl: './library-template.scss',
  changeDetection: ChangeDetectionStrategy.OnPush,
})
export class KoinonLibraryTemplate {
  @Input() allowedKinds: { value: ResourceKind; label: string }[] = [];
  @Input() title = 'Library';
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
    this.activeFilter = value;
    this.nameFilter = value.q ?? '';
  }
  get filter() {
    return this.activeFilter;
  }
  private activeFilter: CatalogFilter = {};
  nameFilter = '';
  @Input() emptyTitle = 'Your knowledge starts here';
  @Input() emptyDescription = 'Create a space to bring your team’s documents and data together.';
  @Output() folderSelected = new EventEmitter<string>();
  @Output() opened = new EventEmitter<CatalogEntry>();
  @Output() selected = new EventEmitter<CatalogEntry>();
  @Output() addRequested = new EventEmitter<void>();
  @Output() browseRequested = new EventEmitter<void>();
  @Output() archivedRequested = new EventEmitter<void>();
  @Output() filterChanged = new EventEmitter<CatalogFilter>();
  sortKey() {
    return (this.filter.sort ?? 'name') + '.' + (this.filter.order ?? 'asc');
  }
  sort(value: string) {
    const [sort, order] = value.split('.');
    if (['name', 'updated_at', 'created_at'].includes(sort) && ['asc', 'desc'].includes(order))
      this.filterChanged.emit({
        sort: sort as CatalogFilter['sort'],
        order: order as 'asc' | 'desc',
        page: 1,
      });
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
