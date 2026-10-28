// Copyright 2026 Firefly Software Foundation
// SPDX-License-Identifier: Apache-2.0
import {registerKoinonSpanish} from '../foundations/i18n';
import {PANEL_SPANISH} from '../foundations/panel-spanish.generated';
import {
  ChangeDetectionStrategy,
  Component,
  computed,
  effect,
  inject,
  signal,
  untracked,
} from '@angular/core';
import type { ProvenanceTransformStep } from '@fireflyframework/koinon-sdk';
import { KoinonTableLineage } from '../services/table-lineage';
import { KoinonI18n, KoinonTextPipe, KoinonDatePipe, KoinonValuePipe } from '../foundations/i18n';
import { KoinonSidePanel } from '../molecules/side-panel';
import { KoinonPagination } from '../molecules/pagination';
import { KoinonButton } from '../atoms/button';
import { KoinonBadge } from '../atoms/badge';
import { KoinonIcon } from '../atoms/icon';
import { KoinonSkeleton } from '../atoms/skeleton';
import { KoinonTableCoordinatesView } from './table-coordinates';
import type { CoordinateTarget } from '../services/table-coordinates';
registerKoinonSpanish(PANEL_SPANISH);
@Component({
  selector: 'ffk-table-lineage-panel',
  imports: [
    KoinonSidePanel,
    KoinonPagination,
    KoinonButton,
    KoinonBadge,
    KoinonIcon,
    KoinonSkeleton,
    KoinonTextPipe,
    KoinonDatePipe,
    KoinonValuePipe,
    KoinonTableCoordinatesView,
  ],
  templateUrl: './table-lineage-panel.html',
  styleUrl: './table-lineage-panel.scss',
  changeDetection: ChangeDetectionStrategy.OnPush,
})
export class KoinonTableLineagePanel {
  readonly state = inject(KoinonTableLineage);
  private readonly i18n = inject(KoinonI18n);
  readonly coordinatesOpen = signal(false);
  readonly coordinateTarget = computed<CoordinateTarget | null>(() => {
    const target = this.state.target(),
      detail = this.state.detail();
    return target && detail
      ? { datasetId: target.datasetId, tableId: target.tableId, snapshotId: detail.snapshot_id }
      : null;
  });
  constructor() {
    effect(() => {
      this.coordinateTarget();
      untracked(() => this.coordinatesOpen.set(false));
    });
  }
  operation(value: string | null | undefined) {
    return (
      (
        { upload: 'Uploaded', replace: 'Replaced', reingest: 'Reprocessed' } as Record<
          string,
          string
        >
      )[value ?? ''] ?? 'Change not recorded'
    );
  }
  status(value: string) {
    return (
      (
        { READY: 'Ready', PARTIAL: 'Processing', FAILED: 'Needs attention' } as Record<
          string,
          string
        >
      )[value] ?? 'Status unavailable'
    );
  }
  stepTitle(step: ProvenanceTransformStep) {
    const titles: Record<string, string> = {
      materialize: 'Read source data',
      decompress: 'Decompress source',
      finalize_parquet: 'Save processed data',
      model_input: 'Send model input',
      model_output: 'Record model output',
      stage_input: 'Start processing stage',
      stage_completed: 'Complete processing stage',
      stage_failed: 'Processing stage failed',
    };
    return titles[step.kind] ?? 'Recorded transformation';
  }
  stage(step: ProvenanceTransformStep) {
    const value = step.parameters?.['stage'] ?? step.parameters?.['role'];
    if (typeof value !== 'string') return '';
    const names: Record<string, string> = {
      parse: 'Read and prepare data',
      describe: 'Describe columns',
      'structured.describe': 'Describe columns',
      discover: 'Discover schema',
      embed: 'Index for search',
    };
    return this.i18n.text(names[value] ?? 'Processing');
  }
  parameters(step: ProvenanceTransformStep) {
    const labels: Record<string, string> = {
      binding_mode: 'Connection mode',
      assignment_id: 'Connection assignment',
      assignment_revision: 'Assignment revision',
      provider_id: 'Provider',
      provider_revision: 'Provider revision',
      selected_model_id: 'Selected model',
      agent_id: 'Agent',
      agent_revision: 'Agent revision',
      api: 'Model API',
      output_mode: 'Output mode',
      model_options_sha256: 'Model options SHA256',
      instructions_sha256: 'Instructions SHA256',
      applied_model_settings_sha256: 'Applied settings SHA256',
    };
    return Object.entries(labels).flatMap(([key, label]) => {
      const value = step.parameters?.[key];
      return typeof value === 'string' || typeof value === 'number'
        ? [{ label, value: String(value) }]
        : [];
    });
  }
}
