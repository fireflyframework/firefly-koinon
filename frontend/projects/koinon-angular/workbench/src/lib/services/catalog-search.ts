// Copyright 2026 Firefly Software Foundation
// SPDX-License-Identifier: Apache-2.0
import { Injectable, computed, effect, inject, signal, untracked } from '@angular/core';
import type { CatalogEntry, ContextResponse, Page } from '@fireflyframework/koinon-sdk';
import { KoinonI18n } from '../foundations/i18n';
import { KoinonFacade } from '../koinon-facade';
import { KoinonClientContext } from './client-context';

interface SearchSnapshot {
  key: string;
  context: ContextResponse | null;
}
interface SearchResult extends SearchSnapshot {
  page: Page<CatalogEntry>;
  error: string;
}
const EMPTY_PAGE: Page<CatalogEntry> = { items: [] };
const PAGE_SIZE = 8;

@Injectable()
export class KoinonCatalogSearch {
  private readonly facade = inject(KoinonFacade);
  private readonly clients = inject(KoinonClientContext);
  private readonly i18n = inject(KoinonI18n);
  readonly requiresSignIn = computed(() => this.facade.authRequired());
  private readonly opened = signal(false);
  readonly query = signal('');
  readonly canSearch = computed(() =>
    Boolean(
      this.facade.tenantId() &&
      this.facade.context()?.subject &&
      this.facade.permissions().has('catalog:read') &&
      !this.facade.authRequired(),
    ),
  );
  private readonly key = computed(() =>
    JSON.stringify([
      this.facade.tenantId(),
      this.facade.workspaceId(),
      this.facade.projectId(),
      this.facade.context()?.subject,
      this.clients.revision(),
      this.canSearch(),
      this.query().trim(),
    ]),
  );
  private readonly result = signal<SearchResult | null>(null);
  private readonly loading = signal<SearchSnapshot | null>(null);
  readonly page = computed(() => {
    const result = this.result();
    return result && this.current(result) ? result.page : EMPTY_PAGE;
  });
  readonly error = computed(() => {
    const result = this.result();
    return result && this.current(result) ? result.error : '';
  });
  readonly pending = computed(() => {
    const loading = this.loading();
    return Boolean(loading && this.current(loading));
  });
  readonly scopeLabel = computed(() => {
    const context = this.facade.context(),
      names = [
        context?.tenants.find((tenant) => tenant.id === this.facade.tenantId())?.name ||
          this.i18n.text('Organization'),
      ];
    if (this.facade.workspaceId())
      names.push(
        context?.workspaces.find((entry) => entry.id === this.facade.workspaceId())?.name ||
          this.i18n.text('Space'),
      );
    if (this.facade.projectId())
      names.push(
        this.facade.entries().find((entry) => entry.id === this.facade.projectId())?.name ||
          this.i18n.text('Project'),
      );
    return names.join(' / ');
  });
  private sequence = 0;
  private read?: AbortController;

  constructor() {
    effect((onCleanup) => {
      const opened = this.opened(),
        allowed = this.canSearch(),
        key = this.key(),
        context = this.facade.context(),
        query = this.query().trim();
      untracked(() => {
        this.cancel();
        this.result.set(null);
      });
      if (!opened || !allowed || !query) return;
      untracked(() => this.loading.set({ key, context }));
      const timer = setTimeout(() => {
        void this.load(1, { key, context });
      }, 250);
      onCleanup(() => {
        clearTimeout(timer);
        this.cancel();
      });
    });
  }
  setOpen(opened: boolean) {
    this.cancel();
    this.result.set(null);
    this.opened.set(opened);
    if (!opened) this.query.set('');
  }
  setQuery(query: string) {
    const bounded = Array.from(query).slice(0, 255).join('');
    if (bounded === this.query()) return;
    this.cancel();
    this.result.set(null);
    this.query.set(bounded);
  }
  isCurrent(entry: CatalogEntry): boolean {
    return this.page().items.some((item) => item === entry) && this.inScope(entry);
  }
  async goToPage(page: number): Promise<void> {
    const observed = this.page();
    if (
      this.pending() ||
      !Number.isInteger(page) ||
      page < 1 ||
      observed.pages === undefined ||
      page > observed.pages ||
      page === observed.page
    )
      return;
    await this.load(page, this.snapshot());
  }
  async retry(): Promise<void> {
    await this.load(1, this.snapshot());
  }
  private snapshot(): SearchSnapshot {
    return { key: this.key(), context: this.facade.context() };
  }
  private current(snapshot: SearchSnapshot): boolean {
    return (
      this.opened() &&
      this.canSearch() &&
      snapshot.key === this.key() &&
      snapshot.context === this.facade.context()
    );
  }
  private inScope(entry: CatalogEntry): boolean {
    return (
      entry.tenant_id === this.facade.tenantId() &&
      entry.status !== 'archived' &&
      (!this.facade.workspaceId() || entry.workspace_id === this.facade.workspaceId()) &&
      (!this.facade.projectId() || entry.project_id === this.facade.projectId())
    );
  }
  private cancel() {
    ++this.sequence;
    this.read?.abort();
    this.read = undefined;
    this.loading.set(null);
  }
  private async load(page: number, snapshot: SearchSnapshot): Promise<void> {
    if (!this.current(snapshot) || !this.query().trim()) return;
    this.cancel();
    const sequence = this.sequence,
      controller = new AbortController();
    this.read = controller;
    this.result.set(null);
    this.loading.set(snapshot);
    try {
      const result = await this.clients.get().catalog.list(
        this.facade.tenantId(),
        {
          q: this.query().trim(),
          workspace_id: this.facade.workspaceId() || undefined,
          project_id: this.facade.projectId() || undefined,
          view: 'library',
          page,
          page_size: PAGE_SIZE,
          sort: 'name',
          order: 'asc',
        },
        { signal: controller.signal },
      );
      if (sequence !== this.sequence || !this.current(snapshot) || controller.signal.aborted)
        return;
      if (
        result.items.length > PAGE_SIZE ||
        result.items.some((entry) => !this.inScope(entry)) ||
        (result.page !== undefined && result.page !== page)
      )
        throw Error('Search returned a result outside the current scope or requested page.');
      this.result.set({ ...snapshot, page: result, error: '' });
    } catch (error) {
      if (sequence !== this.sequence || !this.current(snapshot) || controller.signal.aborted)
        return;
      if (error instanceof Error && 'status' in error && error.status === 401)
        this.facade.authRequired.set(true);
      this.result.set({
        ...snapshot,
        page: EMPTY_PAGE,
        error: error instanceof Error ? error.message : 'Catalog search could not be completed.',
      });
    } finally {
      if (sequence === this.sequence) this.loading.set(null);
    }
  }
}
