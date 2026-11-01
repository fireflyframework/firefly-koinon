// Copyright 2026 Firefly Software Foundation SPDX-License-Identifier: Apache-2.0
import {
  ChangeDetectionStrategy,
  Component,
  DestroyRef,
  EventEmitter,
  Input,
  OnInit,
  Output,
  effect,
  inject,
  signal,
} from '@angular/core';
import { KoinonError, type CatalogEntry } from '@fireflyframework/koinon-sdk';
import { KoinonButton } from '../atoms/button';
import { KoinonTextPipe } from '../foundations/i18n';
import { KoinonFacade } from '../koinon-facade';
import { KoinonClientContext } from '../services/client-context';
import { isFolder, isSystemManaged } from '../services/library-tree';
import { KoinonFolderTree } from './folder-tree';

export function canMoveFolderTo(
  source: CatalogEntry,
  destination: CatalogEntry,
  entries: CatalogEntry[],
): boolean {
  if (
    isSystemManaged(source) ||
    !['collection', 'corpus'].includes(source.kind) ||
    !['project', 'collection', 'corpus'].includes(destination.kind) ||
    destination.status === 'archived' ||
    source.tenant_id !== destination.tenant_id ||
    !source.workspace_id ||
    !source.project_id ||
    source.workspace_id !== destination.workspace_id ||
    source.project_id !==
      (destination.kind === 'project' ? destination.id : destination.project_id) ||
    destination.id === source.parent_id
  )
    return false;
  const seen = new Set<string>();
  let entry: CatalogEntry | undefined = destination;
  while (entry && !seen.has(entry.id)) {
    if (entry.id === source.id) return false;
    seen.add(entry.id);
    entry = entries.find((row) => row.id === entry?.parent_id);
  }
  return true;
}

@Component({
  selector: 'ffk-move-folder',
  imports: [KoinonButton, KoinonTextPipe, KoinonFolderTree],
  template: ` <p>{{ 'Choose a destination in the same space and project.' | ffkText }}</p>
    @if (error()) {
      <p role="alert">{{ error() | ffkText }}</p>
    }
    @if (fresh(); as current) {
      <p>
        <strong>{{ current.name }}</strong>
      </p>
      <ffk-folder-tree
        [entries]="entries()"
        [currentId]="current.parent_id || ''"
        [contextKey]="tenant"
        [loadChildren]="loadChildren"
        [canSelect]="canSelect"
        (selected)="choose($event)"
      />
      @if (destination(); as chosen) {
        <p>
          {{ 'Destination folder' | ffkText }}: <strong>{{ chosen.name }}</strong>
        </p>
      }
    } @else if (loading()) {
      <p role="status">{{ 'Loading folder' | ffkText }}</p>
    }
    <div class="actions">
      <ffk-button variant="quiet" [disabled]="pending()" (click)="closed.emit()">{{
        'Cancel' | ffkText
      }}</ffk-button>
      <ffk-button
        variant="primary"
        [loading]="pending()"
        [disabled]="!destination() || !fresh()"
        (click)="move()"
        >{{ 'Move Library folder' | ffkText }}</ffk-button
      >
    </div>`,
  styles: `
    p {
      font-size: 13px;
      line-height: 1.7;
      margin: 16px 0;
    }
    p[role='alert'] {
      color: var(--ui-danger, var(--ui-text));
    }
    .actions {
      display: flex;
      justify-content: flex-end;
      gap: 12px;
      margin-top: 24px;
    }
  `,
  changeDetection: ChangeDetectionStrategy.OnPush,
})
export class KoinonMoveFolder implements OnInit {
  @Input({ required: true }) source!: CatalogEntry;
  @Output() closed = new EventEmitter<void>();
  readonly facade = inject(KoinonFacade);
  private readonly clients = inject(KoinonClientContext);
  readonly fresh = signal<CatalogEntry | null>(null);
  readonly destination = signal<CatalogEntry | null>(null);
  readonly loading = signal(true);
  readonly pending = signal(false);
  readonly error = signal('');
  tenant = '';
  private owner: object | null = null;
  private revision = -1;
  private scope = '';
  private started = false;
  private readonly request = new AbortController();
  constructor() {
    effect(() => {
      this.facade.context();
      this.facade.tenantId();
      this.facade.workspaceId();
      this.facade.projectId();
      this.facade.parentId();
      this.clients.revision();
      if (this.started && !this.current()) {
        this.request.abort();
        this.fresh.set(null);
        this.destination.set(null);
        this.pending.set(false);
        this.loading.set(false);
        this.error.set('Your account or organization changed. Close this panel and try again.');
      }
    });
    inject(DestroyRef).onDestroy(() => this.request.abort());
  }
  private current() {
    return (
      !this.request.signal.aborted &&
      this.owner === this.facade.context() &&
      this.tenant === this.facade.tenantId() &&
      this.scope === this.scopeKey() &&
      this.revision === this.clients.revision()
    );
  }
  private scopeKey() {
    return JSON.stringify([
      this.facade.workspaceId(),
      this.facade.projectId(),
      this.facade.parentId(),
    ]);
  }
  entries() {
    return [
      ...new Map(
        [...(this.facade.context()?.workspaces ?? []), ...this.facade.entries()].map((row) => [
          row.id,
          row,
        ]),
      ).values(),
    ];
  }
  readonly canSelect = (entry: CatalogEntry) =>
    !!this.fresh() && canMoveFolderTo(this.fresh()!, entry, this.entries());
  readonly loadChildren = (id: string, page = 1) => this.facade.loadChildren(id, page);
  choose(id: string) {
    const entry = this.entries().find((row) => row.id === id);
    if (entry && this.canSelect(entry)) this.destination.set(entry);
  }
  async ngOnInit() {
    this.owner = this.facade.context();
    this.tenant = this.facade.tenantId();
    this.revision = this.clients.revision();
    this.scope = this.scopeKey();
    this.started = true;
    try {
      const entry = await this.clients
        .get()
        .catalog.get(this.tenant, this.source.id, { signal: this.request.signal });
      if (!this.current()) return;
      if (
        !this.facade.canWrite() ||
        !isFolder(entry) ||
        isSystemManaged(entry) ||
        !entry.updated_at ||
        !entry.parent_id ||
        !['collection', 'corpus'].includes(entry.kind)
      )
        throw new Error('This folder cannot be moved. Refresh the Library and try again.');
      this.fresh.set(entry);
    } catch (error) {
      if (this.current())
        this.error.set(
          error instanceof KoinonError
            ? error.message
            : 'This folder cannot be moved. Refresh the Library and try again.',
        );
    } finally {
      if (this.current()) this.loading.set(false);
    }
  }
  async move() {
    const source = this.fresh(),
      destination = this.destination();
    if (
      this.pending() ||
      !this.current() ||
      !source?.updated_at ||
      !source.parent_id ||
      !destination ||
      !this.canSelect(destination) ||
      !this.facade.canWrite()
    )
      return;
    this.pending.set(true);
    this.error.set('');
    try {
      const entry = await this.clients.get().catalog.move(
        this.tenant,
        source.id,
        {
          parent_id: destination.id,
          expected_parent_id: source.parent_id,
          expected_updated_at: source.updated_at,
        },
        { signal: this.request.signal },
      );
      if (!this.current()) return;
      await this.facade.loadLibrary({ page: 1 });
      if (!this.current()) return;
      this.facade.selected.set(entry);
      this.closed.emit();
    } catch (error) {
      if (this.current())
        this.error.set(
          error instanceof KoinonError
            ? error.message
            : 'The folder could not be moved. Refresh the Library before trying again.',
        );
    } finally {
      if (this.current()) this.pending.set(false);
    }
  }
}
