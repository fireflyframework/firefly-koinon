// Copyright 2026 Firefly Software Foundation SPDX-License-Identifier: Apache-2.0
import {
  ChangeDetectionStrategy,
  Component,
  EventEmitter,
  Input,
  OnChanges,
  OnDestroy,
  Output,
  PendingTasks,
  computed,
  effect,
  inject,
  signal,
} from '@angular/core';
import {
  KoinonClientContext,
  KoinonFacade,
  KoinonTextPipe,
  organizationContextKey,
} from '@fireflyframework/koinon-angular/workbench/core';
import { createContentSourcesApi } from '@fireflyframework/koinon-sdk/content-sources';
import type {
  SourceFolderPage,
  SourceItemOutput,
  SourceLocationPage,
} from '@fireflyframework/koinon-sdk';
import type { SourceConnection } from './source-contracts';
export interface SourceSelection {
  driveId: string;
  root: SourceItemOutput;
  excluded: SourceItemOutput[];
}
@Component({
  selector: 'ffk-source-browser',
  imports: [KoinonTextPipe],
  changeDetection: ChangeDetectionStrategy.OnPush,
  styleUrl: './source-controls.scss',
  template: ` <section [attr.aria-label]="'Choose content' | ffkText" [attr.aria-busy]="loading()">
    @if (connection?.provider === 'sharepoint') {
      <form (submit)="$event.preventDefault(); searchSites()">
        <label
          >{{ 'Find a SharePoint site' | ffkText
          }}<input
            name="site"
            [value]="query"
            (input)="query = $any($event.target).value"
            maxlength="256"
            required /></label
        ><button type="submit" [disabled]="loading()">{{ 'Search' | ffkText }}</button>
      </form>
    }
    @if (!driveId()) {
      @for (location of locations().items; track location.id) {
        <div class="source-row">
          <button
            type="button"
            (click)="location.kind === 'site' ? drives(location.id) : openDrive(location.id)"
          >
            {{ location.name }}
          </button>
        </div>
      }
      @if (locations().next_cursor) {
        <button type="button" [disabled]="loading()" (click)="moreLocations()">
          {{ 'Continue browsing' | ffkText }}
        </button>
      }
    } @else {
      <nav [attr.aria-label]="'Source folders' | ffkText">
        <button type="button" (click)="resetDrive()">{{ 'Choose another drive' | ffkText }}</button>
        @for (folder of breadcrumbs(); track folder.item_id) {
          <button type="button" (click)="openFolder(folder, true)">{{ folder.name }}</button>
        }
      </nav>
      @if (folderPage(); as page) {
        <div class="source-row">
          <strong>{{ page.folder.name }}</strong
          ><button type="button" (click)="select(page.folder)">
            {{ 'Use this folder' | ffkText }}
          </button>
        </div>
        <label
          >{{ 'Filter loaded items' | ffkText
          }}<input [value]="filter()" (input)="filter.set($any($event.target).value)"
        /></label>
        <div class="source-rows">
          @for (item of filteredItems(); track item.item_id) {
            <div class="source-row">
              <div>
                <strong>{{ item.name }}</strong
                ><small>{{ (item.kind === 'folder' ? 'Folder' : 'File') | ffkText }}</small>
              </div>
              <div class="actions">
                @if (item.kind === 'folder') {
                  <button type="button" (click)="openFolder(item)">
                    {{ 'Open folder' | ffkText }}: {{ item.name }}
                  </button>
                }
                @if (item.kind !== 'shortcut') {
                  <button type="button" (click)="select(item)">
                    {{ 'Select' | ffkText }}: {{ item.name }}</button
                  ><label class="choice" [hidden]="selected()?.kind === 'file'"
                    ><input
                      type="checkbox"
                      [checked]="excluded().some(isItem(item.item_id))"
                      (change)="exclude(item, $any($event.target).checked)"
                    />{{ 'Exclude' | ffkText }}: {{ item.name }}</label
                  >
                }
              </div>
            </div>
          } @empty {
            <p>
              {{
                (page.next_cursor ? 'No matching items on this page.' : 'No matching items.')
                  | ffkText
              }}
            </p>
          }
        </div>
        @if (page.next_cursor) {
          <button
            type="button"
            [disabled]="loading()"
            (click)="children(page.folder.item_id, true)"
          >
            {{ 'Continue browsing' | ffkText }}
          </button>
        }
      }
      @if (selected(); as root) {
        <p>
          <strong>{{ 'Selected source' | ffkText }}</strong
          >: {{ root.name }}
        </p>
      }
      @if (excluded().length) {
        <h3>{{ 'Excluded files and folders' | ffkText }}</h3>
        <p>{{ 'Excluded folders and their contents will not be imported.' | ffkText }}</p>
        @for (item of excluded(); track item.item_id) {
          <div class="source-row">
            <span>{{ item.name }}</span
            ><button type="button" (click)="exclude(item, false)">
              {{ 'Remove exclusion' | ffkText }}
            </button>
          </div>
        }
      }
    }
    @if (loading()) {
      <p role="status">{{ 'Loading folders…' | ffkText }}</p>
    }
    @if (error()) {
      <p role="alert">{{ error() | ffkText }}</p>
      <button type="button" (click)="reload()">{{ 'Try again' | ffkText }}</button>
    }
  </section>`,
})
export class KoinonSourceBrowser implements OnChanges, OnDestroy {
  @Input() connection: SourceConnection | null = null;
  @Output() selectionChange = new EventEmitter<SourceSelection | null>();
  private readonly f = inject(KoinonFacade);
  private readonly clients = inject(KoinonClientContext);
  private readonly tasks = inject(PendingTasks);
  private readonly key = signal('');
  private readonly context = signal<ReturnType<KoinonFacade['context']>>(null);
  private sequence = 0;
  private alive = true;
  private readonly page = signal<SourceFolderPage | null>(null);
  private readonly locationPage = signal<SourceLocationPage>({ items: [], next_cursor: null });
  readonly driveId = signal('');
  private siteId = '';
  private browsingSites = false;
  query = '';
  readonly filter = signal('');
  private readonly trail = signal<SourceItemOutput[]>([]);
  private readonly root = signal<SourceItemOutput | null>(null);
  private readonly exclusions = signal<SourceItemOutput[]>([]);
  private readonly busy = signal(false);
  private readonly failure = signal('');
  readonly folderPage = computed(() => (this.current() ? this.page() : null));
  readonly locations = computed(() =>
    this.current() ? this.locationPage() : { items: [], next_cursor: null },
  );
  readonly selected = computed(() => (this.current() ? this.root() : null));
  readonly excluded = computed(() => (this.current() ? this.exclusions() : []));
  readonly breadcrumbs = computed(() => (this.current() ? this.trail() : []));
  readonly loading = computed(() => this.current() && this.busy());
  readonly error = computed(() => (this.current() ? this.failure() : ''));
  readonly filteredItems = computed(
    () =>
      this.folderPage()?.items.filter((item) =>
        item.name.toLocaleLowerCase().includes(this.filter().toLocaleLowerCase()),
      ) ?? [],
  );
  constructor() {
    effect(() => {
      organizationContextKey(this.f, this.clients);
      this.f.context();
      this.f.authRequired();
      if (!this.current()) this.clear();
    });
  }
  private current() {
    return (
      this.alive &&
      !this.f.authRequired() &&
      this.key() === organizationContextKey(this.f, this.clients) &&
      this.context() === this.f.context()
    );
  }
  private capture() {
    this.key.set(organizationContextKey(this.f, this.clients));
    this.context.set(this.f.context());
  }
  private api() {
    return createContentSourcesApi(this.clients.getTransport()!);
  }
  private clear() {
    ++this.sequence;
    this.page.set(null);
    this.locationPage.set({ items: [], next_cursor: null });
    this.root.set(null);
    this.exclusions.set([]);
    this.trail.set([]);
    this.driveId.set('');
    this.busy.set(false);
    this.failure.set('');
    this.filter.set('');
    this.query = '';
  }
  ngOnChanges() {
    this.clear();
    this.capture();
    this.selectionChange.emit(null);
    if (this.connection && this.connection.provider !== 'sharepoint') this.drives();
  }
  private run<T>(operation: () => Promise<T>, accept: (result: T) => void) {
    this.capture();
    const sequence = ++this.sequence;
    this.busy.set(true);
    this.failure.set('');
    this.tasks.run(async () => {
      try {
        const result = await operation();
        if (this.current() && sequence === this.sequence) accept(result);
      } catch (error) {
        if (this.current() && sequence === this.sequence) {
          this.page.set(null);
          this.locationPage.set({ items: [], next_cursor: null });
          this.root.set(null);
          this.exclusions.set([]);
          this.trail.set([]);
          this.selectionChange.emit(null);
          if (error instanceof Error && 'status' in error && error.status === 401)
            this.f.authRequired.set(true);
          this.failure.set('Could not load folders. Try again.');
        }
      } finally {
        if (this.current() && sequence === this.sequence) this.busy.set(false);
      }
    });
  }
  searchSites(more = false) {
    if (!this.connection || !this.query.trim()) return;
    this.browsingSites = true;
    this.driveId.set('');
    const cursor = more ? this.locations().next_cursor : undefined;
    this.run(
      () =>
        this.api().sites(this.f.tenantId(), this.connection!.id, {
          q: this.query.trim(),
          ...(cursor ? { cursor } : {}),
        }),
      (page) =>
        this.locationPage.set({
          ...page,
          items: more ? [...this.locationPage().items, ...page.items] : page.items,
        }),
    );
  }
  drives(siteId = '', more = false) {
    if (!this.connection) return;
    this.siteId = siteId;
    this.browsingSites = false;
    const cursor = more ? this.locations().next_cursor : undefined;
    this.run(
      () =>
        this.api().drives(this.f.tenantId(), this.connection!.id, {
          ...(siteId ? { site_id: siteId } : {}),
          ...(cursor ? { cursor } : {}),
        }),
      (page) =>
        this.locationPage.set({
          ...page,
          items: more ? [...this.locationPage().items, ...page.items] : page.items,
        }),
    );
  }
  moreLocations() {
    if (this.browsingSites) this.searchSites(true);
    else this.drives(this.siteId, true);
  }
  openDrive(id: string) {
    this.driveId.set(id);
    this.trail.set([]);
    this.root.set(null);
    this.exclusions.set([]);
    this.selectionChange.emit(null);
    this.children();
  }
  resetDrive() {
    this.driveId.set('');
    this.page.set(null);
    this.drives(this.siteId);
  }
  openFolder(folder: SourceItemOutput, back = false) {
    if (back) {
      const index = this.trail().findIndex((item) => item.item_id === folder.item_id);
      this.trail.update((rows) => rows.slice(0, index + 1));
    }
    this.children(folder.item_id);
  }
  children(folderId?: string, more = false) {
    if (!this.connection || !this.driveId()) return;
    const cursor = more ? this.folderPage()?.next_cursor : null;
    this.filter.set('');
    if (!more) this.page.set(null);
    this.run(
      () =>
        this.api().children(this.f.tenantId(), this.connection!.id, {
          drive_id: this.driveId(),
          ...(folderId ? { folder_id: folderId } : {}),
          ...(cursor ? { cursor } : {}),
        }),
      (page) => {
        this.page.set({
          ...page,
          items: more ? [...(this.page()?.items ?? []), ...page.items] : page.items,
        });
        if (!more && !this.trail().some((item) => item.item_id === page.folder.item_id))
          this.trail.update((rows) => [...rows, page.folder]);
      },
    );
  }
  select(root: SourceItemOutput) {
    this.root.set(root);
    if (root.kind === 'file') this.exclusions.set([]);
    this.emit();
  }
  isItem(id: string) {
    return (item: SourceItemOutput) => item.item_id === id;
  }
  exclude(item: SourceItemOutput, checked: boolean) {
    if (this.selected()?.kind === 'file') return;
    this.exclusions.update((rows) =>
      checked
        ? [...rows.filter((row) => row.item_id !== item.item_id), item]
        : rows.filter((row) => row.item_id !== item.item_id),
    );
    this.emit();
  }
  private emit() {
    const root = this.selected();
    this.selectionChange.emit(
      root ? { driveId: this.driveId(), root, excluded: this.excluded() } : null,
    );
  }
  reload() {
    if (this.driveId()) this.children(this.trail().at(-1)?.item_id);
    else if (this.browsingSites) this.searchSites();
    else this.drives(this.siteId);
  }
  ngOnDestroy() {
    this.alive = false;
    ++this.sequence;
  }
}
