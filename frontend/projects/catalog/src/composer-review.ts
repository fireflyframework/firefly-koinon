// Copyright 2026 Firefly Software Foundation
// SPDX-License-Identifier: Apache-2.0
import { Component, OnDestroy, signal } from '@angular/core';
import { KoinonChatComposer, type ComposerAttachment } from '@fireflyframework/koinon-angular/chat/page';
@Component({
  selector: 'ffk-composer-review',
  imports: [KoinonChatComposer],
  template: `<header>
      <h1>Chat composer</h1>
      <p>
        Interactive design fixture. Files stay in this browser; no upload or model call is made.
      </p>
    </header>
    <div class="stage">
      <ffk-chat-composer
        [value]="draft()"
        (valueChange)="draft.set($event)"
        [canSend]="!!draft().trim()"
        [attachmentsEnabled]="true"
        [attachments]="attachments()"
        (filesSelected)="select($event)"
        (attachmentRemoved)="remove($event)"
        (sendRequested)="feedback.set('Design preview: no message was sent.')"
      />
    </div>
    <div class="fixture-controls">
      <label
        >Preview state
        <select [value]="state()" (change)="setState($event)">
          <option value="selected">Selected</option>
          <option value="uploading">Uploading</option>
          <option value="processing">Processing</option>
          <option value="ready">Ready</option>
          <option value="failed">Failed</option>
        </select></label
      ><span role="status">{{ feedback() }}</span>
    </div>`,
  styles: `
    :host {
      display: block;
      width: min(100%, 900px);
      margin: 32px auto;
      color: var(--ui-text);
    }
    header {
      margin: 0 0 36px;
    }
    h1 {
      font-size: 26px;
      font-weight: 500;
      letter-spacing: -0.03em;
    }
    p {
      font-size: 12px;
      color: var(--ui-muted);
      line-height: 1.8;
      margin-top: 12px;
    }
    .stage {
      padding: 90px 0 36px;
    }
    .fixture-controls {
      display: flex;
      align-items: center;
      gap: 20px;
      flex-wrap: wrap;
      font-size: 11px;
      color: var(--ui-muted);
    }
    label {
      display: flex;
      gap: 10px;
      align-items: center;
    }
    select {
      font: inherit;
      padding: 6px;
      border: 1px solid var(--ui-line);
      border-radius: 6px;
      color: var(--ui-text);
      background: var(--ui-surface);
    }
    @media (max-width: 600px) {
      :host {
        margin: 16px 0;
      }
      .stage {
        padding: 28px 0;
      }
      header {
        margin-bottom: 16px;
      }
      h1 {
        font-size: 24px;
      }
    }
  `,
})
export class ComposerReview implements OnDestroy {
  readonly draft = signal(
    'Compare these files and explain what changed in the service review process.',
  );
  readonly feedback = signal('');
  readonly state = signal<ComposerAttachment['state']>('selected');
  readonly attachments = signal<ComposerAttachment[]>([]);
  private readonly previews = new Map<string, string>();
  select(files: File[]) {
    const next = files.map((file) => {
      const id = crypto.randomUUID();
      const previewUrl = ['image/png', 'image/jpeg', 'image/webp'].includes(file.type)
        ? URL.createObjectURL(file)
        : undefined;
      if (previewUrl) this.previews.set(id, previewUrl);
      return {
        id,
        name: file.name,
        size: file.size,
        mediaType: file.type,
        state: this.state(),
        ...(previewUrl ? { previewUrl } : {}),
      };
    });
    this.attachments.update((items) => [...items, ...next]);
  }
  setState(event: Event) {
    const state = (event.target as HTMLSelectElement).value as ComposerAttachment['state'];
    this.state.set(state);
    this.attachments.update((items) => items.map((item) => ({ ...item, state })));
  }
  remove(id: string) {
    const url = this.previews.get(id);
    if (url) URL.revokeObjectURL(url);
    this.previews.delete(id);
    this.attachments.update((items) => items.filter((item) => item.id !== id));
  }
  ngOnDestroy() {
    for (const url of this.previews.values()) URL.revokeObjectURL(url);
  }
}
