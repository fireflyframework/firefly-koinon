// Copyright 2026 Firefly Software Foundation
// SPDX-License-Identifier: Apache-2.0
import {
  AfterViewInit,
  ChangeDetectionStrategy,
  Component,
  ElementRef,
  EventEmitter,
  Input,
  OnChanges,
  OnDestroy,
  Output,
  SimpleChanges,
  ViewChild,
  computed,
  effect,
  inject,
  signal,
  untracked,
} from '@angular/core';
import { CdkTrapFocus } from '@angular/cdk/a11y';
import type { CatalogEntry } from '@fireflyframework/koinon-sdk';
import { KoinonIcon } from '../atoms/icon';
import { KoinonI18n, KoinonTextPipe } from '../foundations/i18n';
import { KoinonCatalogSearch } from '../services/catalog-search';
import { friendlyKind, resourceIcon } from '../services/library-tree';

export interface KoinonCommand {
  id: string;
  title: string;
  description?: string;
  icon?: string;
  disabled?: boolean;
}
type PaletteOption =
  | { kind: 'command'; key: string; command: KoinonCommand }
  | { kind: 'resource'; key: string; entry: CatalogEntry }
  | { kind: 'search'; key: string; query: string };
let nextPalette = 0;
@Component({
  selector: 'ffk-command-palette',
  imports: [CdkTrapFocus, KoinonIcon, KoinonTextPipe],
  providers: [KoinonCatalogSearch],
  templateUrl: './command-palette.html',
  styleUrl: './command-palette.scss',
  changeDetection: ChangeDetectionStrategy.OnPush,
})
export class KoinonCommandPalette implements AfterViewInit, OnChanges, OnDestroy {
  @Input() open = false;
  @Input() set commands(commands: readonly KoinonCommand[]) {
    this.allowed.set(commands ?? []);
  }
  @Output() readonly closed = new EventEmitter<void>();
  @Output() readonly commandSelected = new EventEmitter<string>();
  @Output() readonly resourceSelected = new EventEmitter<CatalogEntry>();
  @Output() readonly searchRequested = new EventEmitter<string>();
  @ViewChild('dialog') private dialog?: ElementRef<HTMLDialogElement>;
  @ViewChild('queryInput') private input?: ElementRef<HTMLInputElement>;
  readonly search = inject(KoinonCatalogSearch);
  readonly i18n = inject(KoinonI18n);
  readonly id = 'koinon-command-palette-' + ++nextPalette;
  readonly visible = signal(false);
  readonly active = signal(-1);
  private readonly allowed = signal<readonly KoinonCommand[]>([]);
  private previous: HTMLElement | null = null;
  readonly options = computed<PaletteOption[]>(() => {
    const query = this.search.query().trim(),
      match = query.toLocaleLowerCase(this.i18n.preferences().locale);
    const seen = new Set<string>();
    const commands: PaletteOption[] = this.allowed()
      .filter((command) => {
        if (!command.id || seen.has(command.id)) return false;
        seen.add(command.id);
        return (
          !match ||
          (command.title + ' ' + (command.description ?? ''))
            .toLocaleLowerCase(this.i18n.preferences().locale)
            .includes(match)
        );
      })
      .map((command) => ({ kind: 'command', key: 'command:' + command.id, command }));
    const resources: PaletteOption[] = this.search
      .page()
      .items.map((entry) => ({ kind: 'resource', key: 'resource:' + entry.id, entry }));
    return [
      ...commands,
      ...resources,
      ...(query && this.search.canSearch()
        ? [{ kind: 'search' as const, key: 'search', query }]
        : []),
    ];
  });
  readonly activeId = computed(() =>
    this.options()[this.active()] ? this.id + '-option-' + this.active() : null,
  );
  readonly copy = computed(() =>
    this.i18n.preferences().locale.toLowerCase().startsWith('es')
      ? {
          heading: 'Buscar y navegar',
          placeholder: 'Buscar archivos o una acción',
          commands: 'Acciones',
          resources: 'Recursos',
          prompt: 'Escribe un nombre para buscar en este contexto.',
          empty: 'No hay recursos que coincidan.',
          loading: 'Buscando en este contexto…',
          fullSearch: 'Buscar conocimiento',
          searchDescription: 'Abrir la búsqueda completa con este texto',
          unavailable: 'Selecciona una organización con acceso al catálogo.',
          navigate: 'Navegar',
          select: 'Seleccionar',
          results: 'Resultados',
          signIn: 'Inicia sesión para buscar.',
        }
      : {
          heading: 'Search and navigate',
          placeholder: 'Search files or run a command',
          commands: 'Commands',
          resources: 'Resources',
          prompt: 'Type a name to search within this scope.',
          empty: 'No matching resources.',
          loading: 'Searching this scope…',
          fullSearch: 'Search knowledge',
          searchDescription: 'Open full search with this query',
          unavailable: 'Select an organization with catalog access.',
          navigate: 'Navigate',
          select: 'Select',
          results: 'Results',
          signIn: 'Sign in to search.',
        },
  );
  constructor() {
    effect(() => {
      const options = this.options();
      untracked(() => this.active.set(options.findIndex((option) => this.enabled(option))));
    });
  }
  ngAfterViewInit() {
    this.sync();
  }
  ngOnChanges(changes: SimpleChanges) {
    if (changes['open']) this.sync();
  }
  private sync() {
    const dialog = this.dialog?.nativeElement;
    if (!dialog) return;
    if (this.open && !this.visible()) {
      this.previous = (dialog.getRootNode() as Document | ShadowRoot)
        .activeElement as HTMLElement | null;
      this.visible.set(true);
      this.search.setOpen(true);
      if (typeof dialog.showModal === 'function') dialog.showModal();
      else dialog.setAttribute('open', '');
      queueMicrotask(() => {
        if (this.visible() && dialog.open) this.input?.nativeElement.focus({ preventScroll: true });
      });
    } else if (!this.open) this.close();
  }
  private close() {
    this.visible.set(false);
    this.search.setOpen(false);
    const dialog = this.dialog?.nativeElement;
    if (dialog?.open) {
      if (typeof dialog.close === 'function') dialog.close();
      else dialog.removeAttribute('open');
    }
    if (this.previous?.isConnected) this.previous.focus({ preventScroll: true });
    this.previous = null;
  }
  dismiss() {
    if (!this.visible()) return;
    this.close();
    this.closed.emit();
  }
  cancel(event: Event) {
    event.preventDefault();
    event.stopPropagation();
    this.dismiss();
  }
  backdrop(event: MouseEvent) {
    const dialog = this.dialog?.nativeElement;
    if (!dialog || event.target !== dialog) return;
    const rect = dialog.getBoundingClientRect();
    if (
      event.clientX < rect.left ||
      event.clientX > rect.right ||
      event.clientY < rect.top ||
      event.clientY > rect.bottom
    )
      this.dismiss();
  }
  enabled(option: PaletteOption) {
    return option.kind !== 'command' || !option.command.disabled;
  }
  title(option: PaletteOption) {
    return option.kind === 'command'
      ? option.command.title
      : option.kind === 'resource'
        ? option.entry.name
        : this.copy().fullSearch;
  }
  description(option: PaletteOption) {
    return option.kind === 'command'
      ? (option.command.description ?? '')
      : option.kind === 'resource'
        ? this.i18n.text(friendlyKind(option.entry.kind)) +
          (option.entry.description ? ' — ' + option.entry.description : '')
        : this.copy().searchDescription;
  }
  icon(option: PaletteOption) {
    return option.kind === 'command'
      ? option.command.icon || 'grid'
      : option.kind === 'resource'
        ? resourceIcon(option.entry.kind)
        : 'search';
  }
  category(option: PaletteOption) {
    return option.kind === 'command'
      ? this.copy().commands
      : option.kind === 'resource'
        ? this.copy().resources
        : '';
  }
  choose(option: PaletteOption) {
    if (!this.visible()) return;
    if (option.kind === 'command') {
      const command = this.allowed().find((command) => command.id === option.command.id);
      if (!command || command.disabled) return;
      this.dismiss();
      this.commandSelected.emit(command.id);
    } else if (option.kind === 'resource') {
      if (!this.search.isCurrent(option.entry)) return;
      this.dismiss();
      this.resourceSelected.emit(option.entry);
    } else {
      if (!this.search.canSearch() || !option.query || option.query !== this.search.query().trim())
        return;
      this.dismiss();
      this.searchRequested.emit(option.query);
    }
  }
  keydown(event: KeyboardEvent) {
    if (event.isComposing || !this.visible()) return;
    if (event.key === 'Escape') {
      this.cancel(event);
      return;
    }
    if (event.target instanceof HTMLButtonElement && !event.target.dataset['kind']) return;
    const options = this.options(),
      enabled = options
        .map((option, index) => (this.enabled(option) ? index : -1))
        .filter((index) => index >= 0);
    if (!enabled.length || !['ArrowDown', 'ArrowUp', 'Home', 'End', 'Enter'].includes(event.key))
      return;
    event.preventDefault();
    event.stopPropagation();
    if (event.key === 'Enter') {
      const option = options[this.active()];
      if (option) this.choose(option);
      return;
    }
    const current = enabled.indexOf(this.active());
    const index =
      event.key === 'Home'
        ? 0
        : event.key === 'End'
          ? enabled.length - 1
          : event.key === 'ArrowDown'
            ? (current + 1) % enabled.length
            : (current - 1 + enabled.length) % enabled.length;
    this.active.set(enabled[index]);
    queueMicrotask(() =>
      this.dialog?.nativeElement
        .querySelector('[aria-selected="true"]')
        ?.scrollIntoView?.({ block: 'nearest' }),
    );
  }
  ngOnDestroy() {
    this.close();
  }
}
