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
import type { CatalogEntry, PublicActor } from '@fireflyframework/koinon-sdk';
import { KoinonI18n } from '../foundations/i18n';
import { KoinonIcon } from '../atoms/icon';
import { KoinonBadge } from '../atoms/badge';
import { KoinonSkeleton } from '../atoms/skeleton';
import { friendlyStatus, friendlyKind, isFolder, resourceIcon } from '../services/library-tree';
@Component({
  selector: 'ffk-resource-list',
  imports: [KoinonTextPipe, KoinonDatePipe, KoinonIcon, KoinonBadge, KoinonSkeleton],
  template: ` @if (loading) {
      <div role="status" [attr.aria-label]="'Loading library' | ffkText" class="loading">
        @for (row of [1, 2, 3, 4]; track row) {
          <div>
            <ffk-skeleton width="32px" height="32px" /><ffk-skeleton width="65%" height="14px" />
          </div>
        }
      </div>
    } @else if (!items.length) {
      <div class="empty">
        <ffk-icon name="folder" />
        <h3>{{ emptyTitle | ffkText }}</h3>
        <p>{{ emptyDescription | ffkText }}</p>
      </div>
    } @else {
      <div class="table" role="table" [attr.aria-label]="'Library items' | ffkText">
        <div class="row header" role="row">
          <span role="columnheader">{{ 'Name' | ffkText }}</span
          ><span role="columnheader" class="kind">{{ 'Type' | ffkText }}</span
          ><span role="columnheader" class="updated">{{ 'Updated' | ffkText }}</span
          ><span role="columnheader" class="sr-only">{{ 'Details' | ffkText }}</span>
        </div>
        @for (item of items; track item.id) {
          <div role="row" class="row" [class.selected]="item.id === selectedId">
            <div role="cell" class="name-cell">
              <span
                class="resource-icon"
                [class.folder]="isFolder(item)"
                [class.dataset]="item.kind === 'dataset'"
                ><ffk-icon [name]="icon(item.kind)"
              /></span>
              <div class="name-wrap">
                <button class="name" (click)="opened.emit(item)" [title]="item.name">
                  {{ item.name }}</button
                ><span class="mobile-kind">{{ kind(item.kind) | ffkText }}</span>
                @if (item.status && item.status !== 'ready' && item.status !== 'active') {
                  <ffk-badge [tone]="item.status === 'failed' ? 'attention' : 'neutral'">{{
                    status(item.status) | ffkText
                  }}</ffk-badge>
                }
              </div>
            </div>
            <span role="cell" class="kind">{{ kind(item.kind) | ffkText }}</span
            ><span role="cell" class="updated" [title]="item.updated_at || item.created_at"
              ><span>{{ item.updated_at || item.created_at | ffkDate }}</span
              ><small>{{ actorName(item.updated_by || item.created_by) }}</small></span
            >
            <div role="cell" class="detail-cell">
              <button
                class="details"
                [attr.aria-label]="'Details for ' + item.name"
                (click)="selected.emit(item)"
              >
                <ffk-icon name="info" />
              </button>
            </div>
          </div>
        }
      </div>
    }`,
  styles: `
    :host {
      display: block;
      min-width: 0;
      container: koinon-resources / inline-size;
      --resource-action-size: 36px;
    }
    .table {
      width: 100%;
      min-width: 0;
    }
    .row {
      display: grid;
      grid-template-columns: minmax(0, 1fr) 100px 125px var(--resource-action-size);
      gap: 16px;
      align-items: center;
      min-height: 69px;
      border-bottom: 1px solid var(--ui-line, #d8d4ca);
      padding: 0 12px;
      border-radius: 6px;
    }
    .header {
      min-height: 42px;
      border-radius: 0;
      color: var(--ui-muted);
      font-size: 11px;
      font-weight: 500;
    }
    .name-cell {
      display: flex;
      align-items: center;
      gap: 14px;
      min-width: 0;
    }
    .name-wrap {
      display: flex;
      align-items: flex-start;
      flex-direction: column;
      gap: 3px;
      min-width: 0;
    }
    .resource-icon {
      display: flex;
      align-items: center;
      justify-content: center;
      width: 36px;
      height: 40px;
      color: var(--ui-muted);
      font-size: 22px;
      flex-shrink: 0;
    }
    .resource-icon.folder {
      color: var(--ui-accent, var(--ffk-gold, #855414));
      font-size: 25px;
    }
    .resource-icon.dataset {
      color: var(--ffk-slate, #6b8795);
    }
    .name {
      font: 500 13px/1.5 var(--ffk-font, 'Manrope Variable', sans-serif);
      border: 0;
      background: transparent;
      color: var(--ui-text, #272820);
      max-width: 100%;
      padding: 3px 0;
      text-align: left;
      overflow: hidden;
      text-overflow: ellipsis;
      white-space: nowrap;
      cursor: pointer;
    }
    .name:hover {
      text-decoration: underline;
    }
    .kind,
    .updated {
      font-size: 12px;
      color: var(--ui-muted);
    }
    .updated small {
      display: block;
      font-size: 10px;
      margin-top: 4px;
      max-width: 100%;
      overflow: hidden;
      text-overflow: ellipsis;
      white-space: nowrap;
    }
    .details {
      display: flex;
      align-items: center;
      justify-content: center;
      border: 0;
      background: transparent;
      color: var(--ui-muted);
      width: var(--resource-action-size);
      height: var(--resource-action-size);
      border-radius: 6px;
      cursor: pointer;
      font-size: 15px;
    }
    .details:hover {
      background: var(--ui-subtle);
    }
    button:focus-visible {
      outline: 2px solid var(--ui-accent, var(--ffk-gold));
      outline-offset: 3px;
    }
    .row:not(.header):hover,
    .row.selected {
      background: var(--ui-subtle, #f3f1eb);
    }
    .mobile-kind {
      display: none;
    }
    .empty {
      padding: 72px 24px;
      display: flex;
      flex-direction: column;
      align-items: center;
      gap: 10px;
      text-align: center;
    }
    .empty > ffk-icon {
      color: var(--ui-muted);
      font-size: 35px;
    }
    .empty h3 {
      font-size: 15px;
      font-weight: 550;
      margin: 8px 0 0;
    }
    .empty p {
      font-size: 13px;
      line-height: 1.8;
      color: var(--ui-muted);
      max-width: 38ch;
      margin: 0;
    }
    .loading {
      padding: 20px 12px;
    }
    .loading > div {
      display: flex;
      align-items: center;
      gap: 16px;
      padding: 16px 0;
    }
    .sr-only {
      position: absolute;
      width: 1px;
      height: 1px;
      overflow: hidden;
      clip: rect(0, 0, 0, 0);
    }
    @container koinon-resources (max-width: 1000px) {
      .row {
        grid-template-columns: minmax(0, 1fr) 100px var(--resource-action-size);
      }
      .updated {
        display: none;
      }
    }
    @container koinon-resources (max-width: 700px) {
      .row {
        grid-template-columns: minmax(0, 1fr) var(--resource-action-size);
        padding: 0 4px;
        gap: 8px;
        min-height: 76px;
      }
      .kind {
        display: none;
      }
      .mobile-kind {
        display: block;
        font-size: 11px;
        color: var(--ui-muted);
      }
      .header {
        position: absolute;
        width: 1px;
        height: 1px;
        min-height: 0;
        padding: 0;
        margin: -1px;
        overflow: hidden;
        clip-path: inset(50%);
        white-space: nowrap;
        border: 0;
      }
      .resource-icon {
        width: 28px;
      }
      .name-cell {
        gap: 10px;
      }
      .name {
        font-size: 13px;
      }
      .empty {
        padding: 56px 16px;
      }
    }
    @media (pointer: coarse) {
      :host {
        --resource-action-size: 44px;
      }
    }
  `,
  changeDetection: ChangeDetectionStrategy.OnPush,
})
export class KoinonResourceList {
  private readonly i18n = inject(KoinonI18n);
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
