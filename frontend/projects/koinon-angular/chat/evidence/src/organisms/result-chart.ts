// Copyright 2026 Firefly Software Foundation SPDX-License-Identifier: Apache-2.0
import { KoinonTextPipe, KoinonValuePipe } from '@fireflyframework/koinon-angular';
import type { Presentation } from '@fireflyframework/koinon-sdk';
import { Component, Input, ChangeDetectionStrategy } from '@angular/core';
interface ChartRow {
  label: string;
  value: number;
  color: string;
  share: number;
  offset: number;
}
@Component({
  imports: [KoinonTextPipe, KoinonValuePipe],
  selector: 'ffk-result-chart',
  template: `@if (chart(); as data) {
      @if (data.rows.length && data.rows.length <= 100) {
        <figure [class.unframed]="!framed">
          <figcaption>{{ data.valueColumn }} by {{ data.labelColumn }}</figcaption>
          @if (kind === 'line') {
            <svg
              class="line-chart"
              viewBox="0 0 600 200"
              role="img"
              [attr.aria-label]="data.valueColumn + ' by ' + data.labelColumn"
            >
              <path d="M25 15V175H585" />
              <polyline [attr.points]="linePoints(data.rows)" />
              @for (row of data.rows; track $index) {
                <circle
                  [attr.cx]="lineX($index, data.rows.length)"
                  [attr.cy]="lineY(row.value, data.rows)"
                  r="3"
                >
                  <title>
                    {{ row.label }}: {{ row.value | ffkValue: undefined : presentation }}
                  </title>
                </circle>
              }
            </svg>
            <ol class="line-values">
              @for (row of data.rows; track $index) {
                <li>
                  <span>{{ row.label }}</span
                  ><strong>{{ row.value | ffkValue: undefined : presentation }}</strong>
                </li>
              }
            </ol>
          } @else if (kind === 'pie') {
            @if (canPie(data.rows)) {
              <div class="pie-layout">
                <svg
                  class="pie-chart"
                  viewBox="0 0 180 180"
                  role="img"
                  [attr.aria-label]="data.valueColumn + ' by ' + data.labelColumn"
                >
                  @for (row of data.rows; track $index) {
                    <circle
                      cx="90"
                      cy="90"
                      r="60"
                      pathLength="100"
                      [attr.stroke]="row.color"
                      [attr.stroke-dasharray]="row.share + ' ' + (100 - row.share)"
                      [attr.stroke-dashoffset]="-row.offset"
                    >
                      <title>
                        {{ row.label }}: {{ row.value | ffkValue: undefined : presentation }}
                      </title>
                    </circle>
                  }
                </svg>
                <ul>
                  @for (row of data.rows; track $index) {
                    <li>
                      <i [style.background]="row.color"></i><span>{{ row.label }}</span
                      ><strong>{{ row.value | ffkValue: undefined : presentation }}</strong>
                    </li>
                  }
                </ul>
              </div>
            } @else {
              <p class="unavailable">
                {{
                  'A pie chart requires nonnegative values and a positive total. Use the table for this result.'
                    | ffkText
                }}
              </p>
            }
          } @else {
            <div
              class="bars"
              role="img"
              [attr.aria-label]="data.valueColumn + ' by ' + data.labelColumn"
            >
              @for (row of data.rows; track $index) {
                <div class="bar-row">
                  <span [title]="row.label">{{ row.label }}</span>
                  <div class="track">
                    <i [style.left.%]="baseline(data.rows)"></i
                    ><b
                      [style.left.%]="barLeft(row.value, data.rows)"
                      [style.width.%]="barWidth(row.value, data.rows)"
                    ></b>
                  </div>
                  <strong>{{ row.value | ffkValue: undefined : presentation }}</strong>
                </div>
              }
            </div>
          }
        </figure>
      } @else {
        <p class="unavailable">
          {{
            'A chart needs between 1 and 100 returned groups. Use the table to inspect this result.'
              | ffkText
          }}
        </p>
      }
    } @else {
      <p class="unavailable">
        {{
          'This result has no numeric column to chart. Use the table to inspect its values.'
            | ffkText
        }}
      </p>
    }`,
  styleUrl: './result-chart.scss',
  changeDetection: ChangeDetectionStrategy.OnPush,
})
export class KoinonResultChart {
  @Input() presentation?: Presentation;
  @Input() framed = true;
  @Input() rows: Record<string, unknown>[] = [];
  @Input() kind: 'line' | 'bar' | 'pie' = 'bar';
  readonly colors = ['#FFB34A', '#6B8795', '#7A8460', '#BFB8AB', '#855414', '#474A42'];
  chart() {
    const first = this.rows[0];
    if (!first) return null;
    const columns = Object.keys(first),
      numeric = columns.find((k) =>
        this.rows.every((row) => typeof row[k] === 'number' && Number.isFinite(row[k])),
      );
    if (!numeric) return null;
    const label =
      columns.find((k) => k !== numeric && typeof first[k] !== 'number') ??
      columns.find((k) => k !== numeric) ??
      numeric;
    let offset = 0;
    const total = this.rows.reduce((sum, row) => sum + Math.max(0, Number(row[numeric])), 0);
    return {
      valueColumn: numeric,
      labelColumn: label,
      rows: this.rows.map((row, i) => {
        const value = Number(row[numeric]),
          share = total > 0 ? (Math.max(0, value) / total) * 100 : 0;
        const result = {
          label: String(row[label] ?? ''),
          value,
          color: this.colors[i % this.colors.length],
          share,
          offset,
        };
        offset += share;
        return result;
      }),
    };
  }
  baseline(rows: ChartRow[]) {
    return rows.every((r) => r.value >= 0) ? 0 : rows.every((r) => r.value <= 0) ? 100 : 50;
  }
  barWidth(value: number, rows: ChartRow[]) {
    const max = Math.max(...rows.map((r) => Math.abs(r.value)), 1),
      range = this.baseline(rows) === 50 ? 50 : 100;
    return (Math.abs(value) / max) * range;
  }
  barLeft(value: number, rows: ChartRow[]) {
    const base = this.baseline(rows);
    return value < 0 ? base - this.barWidth(value, rows) : base;
  }
  lineX(index: number, count: number) {
    return 25 + (index / Math.max(count - 1, 1)) * 560;
  }
  lineY(value: number, rows: ChartRow[]) {
    const min = Math.min(0, ...rows.map((r) => r.value)),
      max = Math.max(...rows.map((r) => r.value), 1);
    return 175 - ((value - min) / Math.max(max - min, 1)) * 150;
  }
  linePoints(rows: ChartRow[]) {
    return rows
      .map((row, i) => this.lineX(i, rows.length) + ',' + this.lineY(row.value, rows))
      .join(' ');
  }
  canPie(rows: ChartRow[]) {
    return rows.every((r) => r.value >= 0) && rows.some((r) => r.value > 0);
  }
}
