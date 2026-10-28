// Copyright 2026 Firefly Software Foundation
// SPDX-License-Identifier: Apache-2.0
import { DOCUMENT } from '@angular/common';
import {
  ChangeDetectionStrategy,
  Component,
  Input,
  PendingTasks,
  computed,
  inject,
  signal,
} from '@angular/core';
import { KoinonIcon } from './icon';
import { KoinonTextPipe } from '../foundations/i18n';
import { sqlTokens } from '../foundations/sql-tokens';
@Component({
  selector: 'ffk-code-block',
  imports: [KoinonIcon, KoinonTextPipe],
  template: `<figure>
    <figcaption>
      <span>SQL</span
      ><button
        type="button"
        [attr.aria-label]="'Copy SQL' | ffkText"
        [attr.title]="'Copy SQL' | ffkText"
        (click)="copy()"
      >
        <ffk-icon [name]="copied() ? 'check' : 'copy'" />
      </button>
    </figcaption>
    <pre
      tabindex="0"
      role="region"
      [attr.aria-label]="label | ffkText"
    ><code>@for (token of tokens(); track $index) {<span [class]="'token ' + token.kind" [textContent]="token.text"></span>}</code></pre>
    <span class="sr-only" role="status">{{ (copied() ? 'Copied' : '') | ffkText }}</span>
    @if (error()) {
      <p class="copy-error" role="alert">
        {{ 'Copy unavailable. Select the SQL and copy it manually.' | ffkText }}
      </p>
    }
  </figure>`,
  styleUrl: './code-block.scss',
  changeDetection: ChangeDetectionStrategy.OnPush,
})
export class KoinonCodeBlock {
  @Input() label = 'Recorded SQL';
  @Input() set code(value: string) {
    this.raw.set(value ?? '');
    this.copied.set(false);
    this.error.set(false);
  }
  readonly raw = signal('');
  readonly tokens = computed(() => sqlTokens(this.raw()));
  readonly copied = signal(false);
  readonly error = signal(false);
  private readonly document = inject(DOCUMENT);
  private readonly tasks = inject(PendingTasks);
  copy() {
    const sql = this.raw();
    this.tasks.run(async () => {
      try {
        const clipboard = this.document.defaultView?.navigator.clipboard;
        if (!clipboard) throw Error('Clipboard unavailable');
        await clipboard.writeText(sql);
        if (sql === this.raw()) {
          this.copied.set(true);
          this.error.set(false);
        }
      } catch {
        if (sql === this.raw()) this.error.set(true);
      }
    });
  }
}
