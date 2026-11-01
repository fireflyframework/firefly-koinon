// Copyright 2026 Firefly Software Foundation SPDX-License-Identifier: Apache-2.0
import { registerKoinonSpanish } from '@fireflyframework/koinon-angular/workbench';
import { SCHEDULE_SPANISH } from './spanish';
registerKoinonSpanish(SCHEDULE_SPANISH);
import { ChangeDetectionStrategy, Component, EventEmitter, Input, Output } from '@angular/core';
import { FormsModule } from '@angular/forms';
import { KoinonTextPipe } from '@fireflyframework/koinon-angular';
import type {
  DigestFrequency,
  DigestSchedule,
} from '@fireflyframework/koinon-angular/communications';
@Component({
  selector: 'ffk-digest-schedule',
  imports: [FormsModule, KoinonTextPipe],
  template: ` <div class="schedule-fields">
    <label
      >{{ 'Local send time' | ffkText
      }}<input
        type="time"
        [ngModel]="value.local_time"
        (ngModelChange)="change('local_time', $event)"
        [ngModelOptions]="{ standalone: true }"
        [disabled]="disabled"
        required
    /></label>
    @if (frequency === 'weekly') {
      <label
        >{{ 'Day of the week' | ffkText
        }}<select
          [ngModel]="value.weekday"
          (ngModelChange)="change('weekday', $event)"
          [ngModelOptions]="{ standalone: true }"
          [disabled]="disabled"
        >
          @for (day of weekdays; track $index) {
            <option [ngValue]="$index">{{ day | ffkText }}</option>
          }
        </select></label
      >
    }
    @if (frequency === 'monthly') {
      <label
        >{{ 'Day of the month' | ffkText
        }}<input
          type="number"
          min="1"
          max="31"
          step="1"
          [ngModel]="value.day_of_month"
          (ngModelChange)="change('day_of_month', $event)"
          [ngModelOptions]="{ standalone: true }"
          [disabled]="disabled"
          required
        /><small>{{
          'In shorter months, the summary is sent on the last day.' | ffkText
        }}</small></label
      >
    }
  </div>`,
  styles: `
    :host {
      display: block;
    }
    .schedule-fields {
      display: grid;
      grid-template-columns: repeat(2, minmax(0, 1fr));
      gap: 20px;
      max-width: 620px;
    }
    label {
      display: grid;
      gap: 8px;
      font-size: 12px;
      align-content: start;
    }
    input,
    select {
      min-height: 44px;
      min-width: 0;
      box-sizing: border-box;
      width: 100%;
      border: 1px solid var(--ui-line);
      border-radius: 8px;
      padding: 10px 12px;
      background: var(--ui-surface);
      color: var(--ui-text);
      font: 400 13px/1.7 var(--ffk-font);
    }
    small {
      color: var(--ui-muted);
      line-height: 1.7;
    }
    input:focus-visible,
    select:focus-visible {
      outline: 2px solid var(--ui-accent);
      outline-offset: 3px;
    }
    @media (max-width: 600px) {
      .schedule-fields {
        grid-template-columns: 1fr;
      }
    }
  `,
  changeDetection: ChangeDetectionStrategy.OnPush,
})
export class KoinonDigestSchedule {
  @Input() frequency: DigestFrequency = 'off';
  @Input() value: DigestSchedule = { local_time: '09:00', weekday: 0, day_of_month: 1 };
  @Input() disabled = false;
  @Output() valueChange = new EventEmitter<DigestSchedule>();
  readonly weekdays = [
    'Monday',
    'Tuesday',
    'Wednesday',
    'Thursday',
    'Friday',
    'Saturday',
    'Sunday',
  ];
  change(key: keyof DigestSchedule, value: string | number) {
    if (!this.disabled) this.valueChange.emit({ ...this.value, [key]: value });
  }
}
