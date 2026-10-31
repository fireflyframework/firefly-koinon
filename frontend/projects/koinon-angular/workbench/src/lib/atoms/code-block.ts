// Copyright 2026 Firefly Software Foundation
// SPDX-License-Identifier: Apache-2.0
import { DOCUMENT } from '@angular/common';
import {
  ChangeDetectionStrategy,
  Component,
  Input,
  OnDestroy,
  PendingTasks,
  computed,
  inject,
  signal,
} from '@angular/core';
import { KoinonIcon } from './icon';
import { KoinonTextPipe } from '../foundations/i18n';
import type { CodeToken } from '../foundations/code-tokens';
@Component({
  selector: 'ffk-code-block',
  imports: [KoinonIcon, KoinonTextPipe],
  template: `<figure>
    <figcaption>
      <span class="language">{{ languageLabel() }}</span
      ><button
        type="button"
        [attr.aria-label]="copyLabel() | ffkText"
        [attr.title]="copyLabel() | ffkText"
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
        {{ 'Copy unavailable. Select the code and copy it manually.' | ffkText }}
      </p>
    }
  </figure>`,
  styleUrl: './code-block.scss',
  changeDetection: ChangeDetectionStrategy.OnPush,
})
export class KoinonCodeBlock implements OnDestroy {
  @Input() label = 'Recorded SQL';
  @Input() set code(value: string) {
    this.raw.set(value ?? '');
    this.copied.set(false);
    this.error.set(false);
    this.highlight();
  }
  @Input() set language(value: string) {
    this.syntax.set((value ?? 'sql').trim().toLowerCase());
    this.copied.set(false);
    this.error.set(false);
    this.highlight();
  }
  readonly raw = signal('');
  private readonly syntax = signal('sql');
  readonly tokens = signal<readonly CodeToken[]>([]);
  readonly languageLabel = computed(() =>
    ['text', 'plaintext', 'txt', ''].includes(this.syntax()) ? 'Text' : this.syntax().toUpperCase(),
  );
  readonly copyLabel = computed(() => (this.syntax() === 'sql' ? 'Copy SQL' : 'Copy code'));
  readonly copied = signal(false);
  readonly error = signal(false);
  private readonly document = inject(DOCUMENT);
  private readonly tasks = inject(PendingTasks);
  private generation = 0;
  ngOnDestroy() {
    ++this.generation;
  }
  private highlight() {
    const generation = ++this.generation,
      code = this.raw(),
      language = this.syntax();
    this.tokens.set([{ kind: 'plain', text: code }]);
    this.tasks.run(async () => {
      const highlighted =
        language === 'sql'
          ? import('../foundations/sql-tokens').then(({ sqlTokens }) => sqlTokens(code))
          : import('../foundations/code-tokens').then(({ codeTokens }) =>
              codeTokens(code, language),
            );
      const tokens = await highlighted.catch(() => [{ kind: 'plain', text: code }]);
      if (generation === this.generation) this.tokens.set(tokens);
    });
  }
  copy() {
    const sql = this.raw(),
      generation = this.generation;
    this.tasks.run(async () => {
      try {
        const clipboard = this.document.defaultView?.navigator.clipboard;
        if (!clipboard) throw Error('Clipboard unavailable');
        await clipboard.writeText(sql);
        if (generation === this.generation) {
          this.copied.set(true);
          this.error.set(false);
        }
      } catch {
        if (generation === this.generation) this.error.set(true);
      }
    });
  }
}
