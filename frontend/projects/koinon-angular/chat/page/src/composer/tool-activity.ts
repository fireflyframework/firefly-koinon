// Copyright 2026 Firefly Software Foundation
// SPDX-License-Identifier: Apache-2.0
import { ChangeDetectionStrategy, Component, EventEmitter, Input, Output } from '@angular/core';
import type { ToolActivity } from '@fireflyframework/koinon-sdk';
import { KoinonIcon, KoinonTextPipe } from '@fireflyframework/koinon-angular';
@Component({
  selector: 'ffk-tool-activity',
  imports: [KoinonIcon, KoinonTextPipe],
  changeDetection: ChangeDetectionStrategy.OnPush,
  template: `@if (activities.length || count) {
    <details>
      <summary>
        <ffk-icon name="code" /><span>{{ heading | ffkText }}</span
        ><span class="count">{{ count || activities.length }}</span
        ><ffk-icon class="chevron" name="chevron" />
      </summary>
      <ol>
        @for (activity of activities; track activity.call_id) {
          <li [attr.data-status]="activity.status">
            <ffk-icon [name]="icon(activity.status)" />
            <div>
              <span class="tool-name">{{ label(activity.tool_name) | ffkText }}</span
              ><span class="state"
                >{{ state(activity.status) | ffkText }}
                @if (activity.duration_ms !== undefined) {
                 , {{ duration(activity.duration_ms) }}
                }
              </span>
              @if (activity.summary) {
                <p>{{ activity.summary }}</p>
              }
            </div>
          </li>
        }
      </ol>
      @if (error) {
        <p class="error" role="alert">{{ error }}</p>
      }
      @if (hasMore || error) {
        <button type="button" [disabled]="loading" (click)="loadMore.emit()">
          {{
            (loading ? 'Loading tool activity…' : error ? 'Try again' : 'Show more tools') | ffkText
          }}
        </button>
      }
    </details>
  }`,
  styles: `
    :host {
      display: block;
      min-width: 0;
      margin: 0 0 12px;
      font: 400 12px/1.6 var(--ffk-font, 'Manrope Variable', sans-serif);
      color: var(--ui-muted);
    }
    * {
      box-sizing: border-box;
    }
    details {
      min-width: 0;
    }
    summary {
      display: flex;
      align-items: center;
      gap: 8px;
      min-height: 32px;
      width: fit-content;
      max-width: 100%;
      cursor: pointer;
      list-style: none;
      border-radius: 6px;
    }
    summary::-webkit-details-marker {
      display: none;
    }
    summary > span:first-of-type {
      overflow-wrap: anywhere;
    }
    .count {
      font-variant-numeric: tabular-nums;
      font-size: 10px;
    }
    .chevron {
      font-size: 11px;
      transition: transform 0.15s;
    }
    details[open] .chevron {
      transform: rotate(90deg);
    }
    ol {
      list-style: none;
      display: grid;
      gap: 12px;
      padding: 8px 0 4px 4px;
      margin: 0;
    }
    li {
      display: flex;
      align-items: flex-start;
      gap: 10px;
    }
    li > ffk-icon {
      margin-top: 3px;
      color: var(--ui-accent);
      flex-shrink: 0;
    }
    li > div {
      min-width: 0;
    }
    .tool-name {
      color: var(--ui-text);
    }
    .state {
      margin-left: 8px;
      font-size: 11px;
    }
    p {
      margin: 3px 0 0;
      overflow-wrap: anywhere;
    }
    button {
      margin-top: 8px;
      border: 1px solid var(--ui-line);
      border-radius: 6px;
      padding: 6px 10px;
      background: transparent;
      color: var(--ui-text);
      font: inherit;
      cursor: pointer;
    }
    button:disabled {
      color: var(--ui-muted);
      cursor: default;
    }
    summary:focus-visible,
    button:focus-visible {
      outline: 2px solid var(--ui-focus, var(--ui-accent));
      outline-offset: 3px;
    }
    .error {
      color: var(--ui-text);
    }
    @media (pointer: coarse) {
      summary,
      button {
        min-height: 44px;
      }
    }
    @media (prefers-reduced-motion: reduce) {
      .chevron {
        transition: none;
      }
    }
  `,
})
export class KoinonToolActivity {
  @Input() activities: readonly ToolActivity[] = [];
  @Input() count = 0;
  @Input() hasMore = false;
  @Input() loading = false;
  @Input() error = '';
  @Output() loadMore = new EventEmitter<void>();
  get heading() {
    const running = [...this.activities]
      .reverse()
      .find((item) => item.status === 'running' || item.status === 'queued');
    return running ? this.label(running.tool_name) : 'Tools used';
  }
  label(name: ToolActivity['tool_name']) {
    return {
      search_knowledge: 'Search knowledge',
      inspect_schema: 'Inspect data structure',
      query_dataset: 'Query data',
      search_private_attachments: 'Read attached files',
      propose_catalog_update: 'Propose a catalog edit',
    }[name];
  }
  state(status: ToolActivity['status']) {
    return {
      queued: 'Queued',
      running: 'Running',
      completed: 'Completed',
      failed: 'Failed',
      cancelled: 'Stopped',
    }[status];
  }
  icon(status: ToolActivity['status']) {
    return {
      queued: 'history',
      running: 'code',
      completed: 'check',
      failed: 'alert',
      cancelled: 'stop',
    }[status];
  }
  duration(milliseconds: number) {
    if (milliseconds < 100) return '<0.1 s';
    return (
      new Intl.NumberFormat(undefined, { maximumFractionDigits: 1 }).format(milliseconds / 1000) +
      ' s'
    );
  }
}
