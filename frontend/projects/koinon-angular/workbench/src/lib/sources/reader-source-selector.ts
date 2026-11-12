// Copyright 2026 Firefly Software Foundation SPDX-License-Identifier: Apache-2.0
import {
  ChangeDetectionStrategy,
  Component,
  EventEmitter,
  Input,
  Output,
  PendingTasks,
  effect,
  inject,
  input,
  signal,
} from '@angular/core';
import type { ReaderSourceSelection } from '@fireflyframework/koinon-sdk/content-sources';
import {
  KoinonFacade,
  KoinonI18n,
  KoinonTextPipe,
  registerKoinonSpanish,
} from '@fireflyframework/koinon-angular/workbench/core';
import { KoinonSourceAccounts, type ReaderMode } from './source-accounts';
import { SOURCE_SPANISH } from './source-spanish';
import { connectionStatus, providerName } from './source-presentation';
registerKoinonSpanish(SOURCE_SPANISH);
@Component({
  selector: 'ffk-reader-source-selector',
  imports: [KoinonTextPipe],
  providers: [KoinonSourceAccounts],
  changeDetection: ChangeDetectionStrategy.OnPush,
  styleUrl: './source-controls.scss',
  template: `<details class="reader-selector" [open]="openInitially" (toggle)="opened($event)">
    <summary>{{ label | ffkText }}: {{ summary() }}</summary>
    @if (expanded() && !f.authRequired()) {
      <div class="selector-body">
        <p>
          {{
            'Choose your accounts to verify access to imported knowledge. Local knowledge uses your Koinon permissions.'
              | ffkText
          }}
        </p>
        <fieldset [disabled]="disabled || state.pending()">
          <legend>{{ label | ffkText }}</legend>
          @for (option of modes; track option.value) {
            <label class="choice"
              ><input
                type="radio"
                [name]="group"
                [value]="option.value"
                [checked]="mode() === option.value"
                (change)="mode.set(option.value); validation.set('')"
              />{{ option.label | ffkText }}</label
            >
          }
          @if (mode() === 'saved' && state.preference()?.connections?.length === 0) {
            <p>{{ 'No source accounts saved. Imported knowledge will not be used.' | ffkText }}</p>
          }
          @if (mode() === 'explicit') {
            <div class="source-rows" [attr.aria-busy]="state.loading()">
              @for (account of state.page().items; track account.id; let index = $index) {
                <label class="choice account-choice"
                  ><input
                    type="checkbox"
                    [checked]="chosen().includes(account.id)"
                    [disabled]="account.status !== 'connected'"
                    (change)="toggle(account.id, $any($event.target).checked)"
                  /><span
                    ><strong
                      >{{ account.display_name || providerName(account.provider) }}
                      @if (!account.display_name) {
                        — {{ 'Connected account' | ffkText }} {{ index + 1 }}
                      }
                    </strong>
                    @if (account.display_address && account.display_address_verified) {
                      <small>{{ account.display_address }}</small>
                    }
                    <small>{{ connectionStatus(account.status) | ffkText }}</small></span
                  ></label
                >
              } @empty {
                @if (!state.loading() && !state.error()) {
                  <p>
                    {{
                      (state.page().next_cursor
                        ? 'No matching items on this page.'
                        : 'No matching items.'
                      ) | ffkText
                    }}
                  </p>
                }
              }
            </div>
            @if (state.page().next_cursor) {
              <button type="button" (click)="more()" [disabled]="state.loading()">
                {{ (state.loading() ? 'Loading more…' : 'Continue browsing') | ffkText }}
              </button>
            }
          }
          <div class="actions">
            <button class="primary" type="button" (click)="apply()">{{ 'Apply' | ffkText }}</button
            ><button
              type="button"
              (click)="save()"
              [disabled]="mode() === 'saved' || !state.preference() || state.preferenceStale()"
            >
              {{ 'Save as my default' | ffkText }}
            </button>
          </div>
        </fieldset>
        @if (state.loading()) {
          <p role="status">{{ 'Loading accounts…' | ffkText }}</p>
        }
        @if (validation() || state.error()) {
          <p role="alert">{{ validation() || state.error() | ffkText }}</p>
          <button type="button" (click)="reload()">
            {{ (state.preferenceStale() ? 'Reload preference' : 'Try again') | ffkText }}
          </button>
        }
        @if (state.notice()) {
          <p role="status">{{ state.notice() | ffkText }}</p>
        }
      </div>
    }
  </details>`,
})
export class KoinonReaderSourceSelector {
  readonly state = inject(KoinonSourceAccounts);
  readonly f = inject(KoinonFacade);
  private readonly i18n = inject(KoinonI18n);
  readonly appliedCount = signal(0);
  private readonly tasks = inject(PendingTasks);
  private static nextId = 0;
  readonly group = 'reader-sources-' + ++KoinonReaderSourceSelector.nextId;
  readonly providerName = providerName;
  readonly connectionStatus = connectionStatus;
  readonly expanded = signal(false);
  readonly mode = signal<ReaderMode>('saved');
  readonly chosen = signal<string[]>([]);
  readonly validation = signal('');
  readonly applied = signal<ReaderMode>('saved');
  @Input() label = 'Sources for answers';
  @Input() openInitially = false;
  @Input() disabled = false;
  readonly selection = input<ReaderSourceSelection[] | null>(null);
  @Output() selectionChange = new EventEmitter<ReaderSourceSelection[] | null>();
  readonly modes: { value: ReaderMode; label: string }[] = [
    { value: 'saved', label: 'Use my saved source accounts' },
    { value: 'explicit', label: 'Choose accounts for this request' },
    { value: 'local', label: 'Use local knowledge only' },
  ];
  constructor() {
    effect(() => {
      this.state.identity();
      this.f.context();
      const selection=this.selection();
      const mode=selection===null?'saved':selection.length?'explicit':'local';
      this.mode.set(mode);
      this.applied.set(mode);
      this.chosen.set(selection?.map(row=>row.connection_id)??[]);
      this.appliedCount.set(selection?.length??0);
      this.validation.set('');
    });
  }
  summary() {
    return this.applied() === 'saved'
      ? this.i18n.text('Saved source accounts')
      : this.applied() === 'local'
        ? this.i18n.text('Local knowledge only')
        : this.i18n
            .text('{n} source accounts selected')
            .replace('{n}', String(this.appliedCount()));
  }
  opened(event: Event) {
    const open = (event.target as HTMLDetailsElement).open;
    this.expanded.set(open);
    if (open) this.reload();
  }
  reload() {
    this.tasks.run(() => Promise.all([this.state.load(), this.state.loadPreference()]));
  }
  more() {
    this.tasks.run(() => this.state.load(true));
  }
  toggle(id: string, checked: boolean) {
    this.chosen.update((ids) =>
      checked ? [...ids.filter((value) => value !== id), id] : ids.filter((value) => value !== id),
    );
    this.validation.set('');
  }
  private choices() {
    try {
      return this.state.apply(this.mode(), this.chosen());
    } catch (error) {
      this.validation.set(
        error instanceof Error ? error.message : 'Selection needs to be checked again',
      );
      return undefined;
    }
  }
  apply() {
    const choice = this.choices();
    if (choice === undefined || this.disabled) return;
    this.applied.set(this.mode());
    this.appliedCount.set(choice?.length ?? 0);
    this.selectionChange.emit(choice);
  }
  save() {
    const choice = this.choices();
    if (choice === undefined || choice === null || this.disabled) return;
    this.tasks.run(() => this.state.save(choice));
  }
}
