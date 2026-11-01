// Copyright 2026 Firefly Software Foundation SPDX-License-Identifier: Apache-2.0
import { ChangeDetectionStrategy, Component, EventEmitter, Input, Output } from '@angular/core';
import { FormsModule } from '@angular/forms';
import { KoinonTextPipe } from '@fireflyframework/koinon-angular';
import type { ActivityWindow } from '@fireflyframework/koinon-sdk';
export function defaultActivityDates(now = new Date()) {
  const end = now.toISOString().slice(0, 10);
  return {
    start: new Date(Date.parse(end + 'T00:00:00Z') - 7 * 86400000).toISOString().slice(0, 10),
    end,
  };
}
export function activityWindow(
  start: string,
  end: string,
  time_zone: string,
  now = new Date(),
): ActivityWindow | null {
  const date = (value: string) =>
    /^\d{4}-\d{2}-\d{2}$/.test(value) &&
    Number.isFinite(Date.parse(value + 'T00:00:00Z')) &&
    new Date(value + 'T00:00:00Z').toISOString().slice(0, 10) === value;
  if (
    !date(start) ||
    !date(end) ||
    start >= end ||
    Date.parse(end + 'T00:00:00Z') > now.getTime() ||
    Date.parse(end + 'T00:00:00Z') - Date.parse(start + 'T00:00:00Z') > 366 * 86400000
  )
    return null;
  return {
    start_at: new Date(start + 'T00:00:00Z').toISOString(),
    end_at: new Date(end + 'T00:00:00Z').toISOString(),
    time_zone,
  };
}
@Component({
  selector: 'ffk-activity-window',
  imports: [FormsModule, KoinonTextPipe],
  template: `<fieldset>
    <legend>{{ 'Reporting window' | ffkText }}</legend>
    <div>
      <label
        ><span>{{ 'From date (UTC)' | ffkText }}</span
        ><input
          type="date"
          name="activity-start"
          [ngModel]="start"
          (ngModelChange)="start = $event; changed()"
          [max]="today"
          [disabled]="disabled" /></label
      ><label
        ><span>{{ 'Until date, excluded (UTC)' | ffkText }}</span
        ><input
          type="date"
          name="activity-end"
          [ngModel]="end"
          (ngModelChange)="end = $event; changed()"
          [max]="today"
          [disabled]="disabled"
      /></label>
    </div>
    <small
      >{{
        'Only completed UTC days are included. Daily activity is grouped in your profile time zone.'
          | ffkText
      }}
      {{ timeZone }}</small
    >
  </fieldset>`,
  styles: [
    `
      :host {
        display: block;
      }
      fieldset {
        margin: 0;
        padding: 0;
        border: 0;
        min-width: 0;
      }
      legend {
        font-size: 0.875rem;
        font-weight: 650;
        margin-bottom: 12px;
      }
      fieldset > div {
        display: flex;
        gap: 16px;
        flex-wrap: wrap;
      }
      label {
        display: grid;
        gap: 8px;
        font-size: 0.875rem;
        flex: 1;
        min-width: 160px;
        align-content: start;
      }
      @media (max-width: 600px) {
        label > span {
          min-height: 2.8em;
        }
      }
      input:focus-visible {
        outline: 2px solid var(--ui-accent);
        outline-offset: 3px;
      }
      input {
        box-sizing: border-box;
        width: 100%;
        min-height: 44px;
        border: 1px solid var(--ui-line);
        border-radius: var(--ffk-radius-md, 8px);
        background: var(--ui-surface);
        color: var(--ui-text);
        padding: 10px 12px;
        font: inherit;
      }
      small {
        display: block;
        color: var(--ui-muted);
        font-size: 0.8125rem;
        line-height: 1.6;
        margin-top: 10px;
      }
    `,
  ],
  changeDetection: ChangeDetectionStrategy.OnPush,
})
export class KoinonActivityWindow {
  @Input() timeZone = 'UTC';
  @Input() disabled = false;
  @Output() windowChanged = new EventEmitter<ActivityWindow | null>();
  private readonly defaults = defaultActivityDates();
  readonly today = this.defaults.end;
  start = this.defaults.start;
  end = this.defaults.end;
  changed() {
    this.windowChanged.emit(activityWindow(this.start, this.end, this.timeZone));
  }
}
