// Copyright 2026 Firefly Software Foundation SPDX-License-Identifier: Apache-2.0
import { ChangeDetectionStrategy, Component, Input, inject } from '@angular/core';
import {
  KoinonBadge,
  KoinonDatePipe,
  KoinonI18n,
  KoinonTextPipe,
} from '@fireflyframework/koinon-angular';
import type {
  ActivitySummary,
  ObservedCount,
  ObservedCost,
  KnowledgeActivityCounts,
} from '@fireflyframework/koinon-sdk';
import { registerKoinonSpanish } from '@fireflyframework/koinon-angular/workbench';
import { ACTIVITY_SPANISH } from './spanish';
registerKoinonSpanish(ACTIVITY_SPANISH);
@Component({
  selector: 'ffk-activity-summary',
  imports: [KoinonBadge, KoinonDatePipe, KoinonTextPipe],
  templateUrl: './activity-summary.html',
  styleUrl: './activity.scss',
  changeDetection: ChangeDetectionStrategy.OnPush,
})
export class KoinonActivitySummary {
  @Input({ required: true }) value!: ActivitySummary;
  readonly i18n = inject(KoinonI18n);
  readonly knowledgeKeys: (keyof KnowledgeActivityCounts)[] = ['created', 'updated', 'consulted'];
  readonly labels = { created: 'Created', updated: 'Updated', consulted: 'Consulted' };
  readonly mcpKeys = [
    'requests',
    'tool_calls',
    'succeeded',
    'failed',
    'rejected',
    'tool_cancelled',
    'request_succeeded',
    'request_failed',
    'request_rejected',
    'request_cancelled',
    'average_duration_ms',
    'p95_duration_ms',
  ] as const;
  readonly mcpLabels = {
    requests: 'Requests',
    tool_calls: 'Tool calls',
    succeeded: 'Successful tools',
    failed: 'Failed tools',
    rejected: 'Rejected tools',
    tool_cancelled: 'Cancelled tools',
    request_succeeded: 'Successful requests',
    request_failed: 'Failed requests',
    request_rejected: 'Rejected requests',
    request_cancelled: 'Cancelled requests',
    average_duration_ms: 'Average tool duration (ms)',
    p95_duration_ms: '95th percentile tool duration (ms)',
  };
  count(value: ObservedCount | undefined) {
    return value?.status !== 'unavailable' && value?.value != null
      ? new Intl.NumberFormat(this.i18n.preferences().locale).format(value.value)
      : this.i18n.text('Unavailable');
  }
  cost(value: ObservedCost) {
    return value.status !== 'unavailable' && value.amount != null
      ? String(value.amount) + (value.currency ? ' ' + value.currency : '')
      : this.i18n.text('Unavailable');
  }
  local() {
    return { ...this.i18n.preferences(), time_zone: this.value.window.time_zone };
  }
  bar(value: ObservedCount) {
    const max = Math.max(
      1,
      ...(this.value.top_projects ?? []).map((row) => row.knowledge.consulted.value ?? 0),
    );
    return value.status === 'unavailable' || value.value == null
      ? null
      : Math.min(100, Math.max(0, (value.value / max) * 100));
  }
}
