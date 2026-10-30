// Copyright 2026 Firefly Software Foundation SPDX-License-Identifier: Apache-2.0
import { KoinonTextPipe, KoinonDatePipe } from '../foundations/i18n';
import {
  Component,
  Input,
  Output,
  EventEmitter,
  ChangeDetectionStrategy,
  inject,
  HostListener,
} from '@angular/core';
import { CdkTrapFocus } from '@angular/cdk/a11y';
import { BreakpointObserver } from '@angular/cdk/layout';
import { toSignal } from '@angular/core/rxjs-interop';
import { map } from 'rxjs';
import type { CatalogEntry, DatasetSchema, PublicActor } from '@fireflyframework/koinon-sdk';
import { KoinonI18n } from '../foundations/i18n';
import { KoinonButton } from '../atoms/button';
import { KoinonBadge } from '../atoms/badge';
import { KoinonIcon } from '../atoms/icon';
import { friendlyStatus, friendlyKind, resourceIcon } from '../services/library-tree';
@Component({
  selector: 'ffk-inspector',
  imports: [KoinonTextPipe, KoinonDatePipe, CdkTrapFocus, KoinonButton, KoinonBadge, KoinonIcon],
  template: `@if (drawer()) {
      <button
        class="drawer-shade"
        aria-hidden="true"
        tabindex="-1"
        (click)="closed.emit()"
      ></button>
    }
    <aside
      [attr.role]="drawer() ? 'dialog' : 'complementary'"
      [attr.aria-modal]="drawer() ? true : null"
      [cdkTrapFocus]="drawer()"
      [cdkTrapFocusAutoCapture]="drawer()"
      [attr.aria-label]="'Resource details' | ffkText"
    >
      <header>
        <span>{{ 'Details' | ffkText }}</span
        ><ffk-button
          variant="quiet"
          icon="close"
          [label]="'Close details' | ffkText"
          (click)="closed.emit()"
        />
      </header>
      <div class="resource-mark"><ffk-icon [name]="icon(entry.kind)" /></div>
      <span class="eyebrow">{{ kind(entry.kind) | ffkText }}</span>
      <h2>{{ entry.name }}</h2>
      <p class="description">{{ entry.description || 'No description yet.' }}</p>
      <ffk-badge [tone]="entry.status === 'failed' ? 'attention' : 'neutral'">{{
        status(entry.status) | ffkText
      }}</ffk-badge>
      <dl>
        <dt>{{ 'Location' | ffkText }}</dt>
        <dd>{{ parentName || 'Library' }}</dd>
        <dt>{{ 'Added' | ffkText }}</dt>
        <dd [title]="entry.created_at">{{ entry.created_at | ffkDate }}</dd>
        @if (entry.created_by) {
          <dt>{{ 'Added by' | ffkText }}</dt>
          <dd>{{ actorName(entry.created_by) }}</dd>
        }
        @if (entry.updated_at) {
          <dt>{{ 'Modified' | ffkText }}</dt>
          <dd [title]="entry.updated_at">{{ entry.updated_at | ffkDate }}</dd>
        }
        @if (entry.updated_by) {
          <dt>{{ 'Updated by' | ffkText }}</dt>
          <dd>{{ actorName(entry.updated_by) }}</dd>
        }
      </dl>
      @if (entry.kind === 'dataset') {
        <ffk-button icon="table" (click)="explored.emit()">{{
          'Explore dataset' | ffkText
        }}</ffk-button>
        @if (schema) {
          <section>
            <h3>{{ 'Tables' | ffkText }}</h3>
            @for (table of schema.tables; track table.id) {
              <div class="table-row">
                <ffk-icon name="table" /><span>{{ table.name }}</span
                ><small>{{ table.columns.length }} columns</small>
                <ffk-button variant="quiet" icon="history" [label]="('History & lineage' | ffkText) + ', ' + table.name"
                  (click)="tableHistoryRequested.emit({ id: table.id, name: table.name })"/>
              </div>
            }
          </section>
        }
      }
      <section class="actions">
        @if (entry.kind === 'table' && entry.parent_id) {
          <ffk-button variant="quiet" icon="history" (click)="tableHistoryRequested.emit({ id: entry.id, name: entry.name })">{{ 'History & lineage' | ffkText }}</ffk-button>
        }
        <ffk-button variant="quiet" icon="lineage" (click)="lineageRequested.emit()">{{
          'Where this came from' | ffkText
        }}</ffk-button>
        @if (canEdit) {
          <ffk-button variant="quiet" (click)="editRequested.emit()">{{
            'Edit details' | ffkText
          }}</ffk-button
          ><ffk-button variant="quiet" (click)="archiveRequested.emit()">{{
            'Archive' | ffkText
          }}</ffk-button>
        }
      </section>
      <details>
        <summary>{{ 'Technical details' | ffkText }}</summary>
        <dl>
          <dt>{{ 'Resource identifier' | ffkText }}</dt>
          <dd class="identifier">{{ entry.id }}</dd>
        </dl>
        @for (item of metadataEntries(); track item[0]) {
          <p class="metadata">
            <strong>{{ item[0] }}</strong
            ><span>{{ item[1] }}</span>
          </p>
        }
      </details>
    </aside>`,
  styleUrl: './inspector.scss',
  changeDetection: ChangeDetectionStrategy.OnPush,
})
export class KoinonInspector {
  private readonly i18n = inject(KoinonI18n);
  @Input() actors: Record<string, PublicActor> = {};
  actorName(subject: string) {
    return this.actors[subject]?.display_name || this.i18n.text('Name unavailable');
  }
  private readonly breakpoints = inject(BreakpointObserver);
  readonly drawer = toSignal(
    this.breakpoints.observe('(max-width:1000px)').pipe(map((state) => state.matches)),
    { initialValue: this.breakpoints.isMatched('(max-width:1000px)') },
  );
  @HostListener('keydown.escape') escape() {
    if (this.drawer()) this.closed.emit();
  }
  @Input({ required: true }) entry!: CatalogEntry;
  @Input() parentName = '';
  @Input() canEdit = false;
  @Input() schema: DatasetSchema | null = null;
  @Output() closed = new EventEmitter<void>();
  @Output() explored = new EventEmitter<void>();
  @Output() lineageRequested = new EventEmitter<void>();
  @Output() tableHistoryRequested = new EventEmitter<{ id: string; name: string }>();
  @Output() editRequested = new EventEmitter<void>();
  @Output() archiveRequested = new EventEmitter<void>();
  readonly status = friendlyStatus;
  readonly kind = friendlyKind;
  readonly icon = resourceIcon;
  metadataEntries() {
    return Object.entries(this.entry.metadata ?? {}).map(([key, value]) => [
      key.replaceAll('_', ' '),
      typeof value === 'object' ? JSON.stringify(value) : String(value),
    ]);
  }
}
