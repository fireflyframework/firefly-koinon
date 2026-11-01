// Copyright 2026 Firefly Software Foundation SPDX-License-Identifier: Apache-2.0
import { KoinonTextPipe } from '../foundations/i18n';
import {
  Component,
  Input,
  Output,
  EventEmitter,
  ChangeDetectionStrategy,
  inject,
  HostListener,
} from '@angular/core';
import { BreakpointObserver } from '@angular/cdk/layout';
import { toSignal } from '@angular/core/rxjs-interop';
import { map } from 'rxjs';
import type { CatalogEntry, DatasetSchema, PublicActor } from '@fireflyframework/koinon-sdk';
import { KoinonI18n } from '../foundations/i18n';
import { KoinonButton } from '../atoms/button';
import { KoinonSkeleton } from '../atoms/skeleton';
import { KoinonInspectorContent } from './inspector-content';
import { friendlyStatus, friendlyKind, resourceIcon, isSystemManaged } from '../services/library-tree';
@Component({
  selector: 'ffk-inspector',
  imports: [KoinonTextPipe, KoinonButton, KoinonSkeleton, KoinonInspectorContent],
  template: `@defer (on immediate) {
      <ffk-inspector-content [view]="this" />
    } @loading {
      <ffk-skeleton width="100%" height="180px" [label]="'Loading details…' | ffkText" />
    } @error {
      <p role="alert">{{ 'Details could not be opened. Close and try again.' | ffkText }}</p>
      <ffk-button variant="quiet" (click)="closed.emit()">{{
        'Close details' | ffkText
      }}</ffk-button>
    }`,
  styles: ':host{display:block;min-width:0}',
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
  @Output() moveRequested = new EventEmitter<void>();
  @Output() archiveRequested = new EventEmitter<void>();
  systemManaged() { return isSystemManaged(this.entry); }
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
