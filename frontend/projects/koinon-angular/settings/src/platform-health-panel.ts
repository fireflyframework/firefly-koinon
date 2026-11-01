// Copyright 2026 Firefly Software Foundation
// SPDX-License-Identifier: Apache-2.0
import {
  ChangeDetectionStrategy,
  Component,
  EventEmitter,
  Output,
  PendingTasks,
  computed,
  effect,
  inject,
  signal,
  untracked,
} from '@angular/core';
import { FormsModule } from '@angular/forms';
import {
  KoinonBadge,
  KoinonButton,
  KoinonDatePipe,
  KoinonFacade,
  KoinonI18n,
  KoinonIcon,
  KoinonSkeleton,
  KoinonTextPipe,
  KoinonValuePipe,
} from '@fireflyframework/koinon-angular';
import { registerKoinonSpanish } from '@fireflyframework/koinon-angular/workbench';
import type {
  HealthComponent,
  HealthStatus,
  SystemArtifact,
  SystemLimit,
} from '@fireflyframework/koinon-sdk/platform-health';
import { KoinonPlatformHealthState } from './platform-health-state';
import { healthStatus, healthSummary } from './platform-health-view';
import {
  HEALTH_COMPONENTS,
  HEALTH_REASONS,
  HEALTH_REMEDIATIONS,
  SYSTEM_COMPONENTS,
  SYSTEM_LIMITS,
} from './platform-health-labels';
import { PLATFORM_HEALTH_SPANISH } from './platform-health-spanish';
registerKoinonSpanish(PLATFORM_HEALTH_SPANISH);

@Component({
  selector: 'ffk-platform-health-panel',
  imports: [
    FormsModule,
    KoinonBadge,
    KoinonButton,
    KoinonDatePipe,
    KoinonIcon,
    KoinonSkeleton,
    KoinonTextPipe,
    KoinonValuePipe,
  ],
  providers: [KoinonPlatformHealthState],
  templateUrl: './platform-health-panel.html',
  styleUrl: './platform-health-panel.scss',
  changeDetection: ChangeDetectionStrategy.OnPush,
})
export class KoinonPlatformHealthPanel {
  @Output() sectionRequested = new EventEmitter<string>();
  readonly state = inject(KoinonPlatformHealthState);
  private readonly f = inject(KoinonFacade);
  private readonly i18n = inject(KoinonI18n);
  private readonly tasks = inject(PendingTasks);
  readonly view = signal<'health' | 'information'>('health');
  readonly filter = signal<HealthStatus | 'all'>('all');
  readonly selectedId = signal<HealthComponent['id'] | null>(null);
  readonly summary = computed(() =>
    healthSummary(this.state.health()?.components ?? [], this.state.now()),
  );
  readonly rows = computed(() => {
    const order = { failed: 0, unknown: 1, passed: 2, disabled: 3 };
    return (this.state.health()?.components ?? [])
      .filter((row) => this.filter() === 'all' || this.status(row) === this.filter())
      .sort((a, b) => order[this.status(a)] - order[this.status(b)]);
  });
  readonly selected = computed(
    () => this.rows().find((row) => row.id === this.selectedId()) ?? this.rows()[0] ?? null,
  );
  readonly components = HEALTH_COMPONENTS;
  readonly reasons = HEALTH_REASONS;
  readonly remediations = HEALTH_REMEDIATIONS;
  readonly systemComponents = SYSTEM_COMPONENTS;
  readonly limitLabels = SYSTEM_LIMITS;
  readonly statuses: HealthStatus[] = ['failed', 'unknown', 'passed', 'disabled'];
  readonly statusLabels: Record<HealthStatus, string> = {
    failed: 'Needs attention',
    unknown: 'Not checked or expired',
    passed: 'Checks passed',
    disabled: 'Not enabled',
  };
  readonly capabilityLabels = [
    { key: 'knowledge_enabled', label: 'Knowledge services' },
    { key: 'mcp_enabled', label: 'MCP connections' },
    { key: 'communications_enabled', label: 'Email communications' },
    { key: 'scheduled_consumers_enabled', label: 'Scheduled processing' },
  ] as const;
  constructor() {
    effect(() => {
      this.state.key();
      const view = this.view(),
        allowed = this.state.allowed();
      if (allowed)
        untracked(() => {
          void this.tasks.run(() =>
            view === 'health' ? this.state.loadHealth() : this.state.loadInformation(),
          );
        });
    });
  }
  status(component: HealthComponent) {
    return healthStatus(component, this.state.now());
  }
  statusLabel(component: HealthComponent) {
    const status = this.status(component);
    if (status === 'unknown')
      return component.freshness === 'stale' ||
        (component.expires_at && Date.parse(component.expires_at) <= this.state.now())
        ? 'Observation expired'
        : 'Not checked';
    return status === 'passed' && component.coverage === 'partial'
      ? 'Checked sample passed'
      : this.statusLabels[status];
  }
  refresh() {
    void this.tasks.run(() =>
      this.view() === 'health' ? this.state.loadHealth() : this.state.loadInformation(),
    );
  }
  tabKey(event: KeyboardEvent) {
    if (!['ArrowLeft', 'ArrowRight', 'Home', 'End'].includes(event.key)) return;
    event.preventDefault();
    const view =
      event.key === 'Home'
        ? 'health'
        : event.key === 'End'
          ? 'information'
          : this.view() === 'health'
            ? 'information'
            : 'health';
    this.view.set(view);
    (event.currentTarget as HTMLElement).parentElement
      ?.querySelector<HTMLButtonElement>(`[data-view="${view}"]`)
      ?.focus();
  }
  reviewSection(component: HealthComponent): string | null {
    const permissions = this.f.tenantPermissions();
    if (component.remediation === 'review_indexes' && permissions.has('indexes:manage'))
      return 'storage';
    if (component.remediation === 'review_ingestion' && permissions.has('jobs:manage'))
      return 'operations';
    if (component.remediation === 'review_communications' && permissions.has('members:write'))
      return 'communications';
    if (
      component.id === 'model-configuration' &&
      component.remediation === 'review_configuration' &&
      (permissions.has('providers:write') || permissions.has('settings:write'))
    )
      return 'models';
    return null;
  }
  limitValue(limit: SystemLimit) {
    if (limit.unit !== 'bytes') return this.i18n.value(limit.value);
    const divisor = limit.value >= 1048576 ? 1048576 : limit.value >= 1024 ? 1024 : 1;
    return `${new Intl.NumberFormat(this.i18n.preferences().locale, { maximumFractionDigits: 1 }).format(limit.value / divisor)} ${divisor === 1048576 ? 'MiB' : divisor === 1024 ? 'KiB' : 'bytes'}`;
  }
  artifactStatus(artifact: SystemArtifact) {
    return artifact.present === false
      ? 'Not provided'
      : artifact.present === true && /^[a-f0-9]{64}$/.test(artifact.sha256 ?? '')
        ? 'Included'
        : 'Unknown';
  }
  safeLabel(labels: Readonly<Record<string, string>>, key: string, fallback: string) {
    return Object.hasOwn(labels, key) ? labels[key] : fallback;
  }
  version(value: string | null | undefined, available: boolean) {
    return available && value && /^[A-Za-z0-9.!+_-]{1,64}$/.test(value) ? value : null;
  }
  validRevision(value: string | null | undefined) {
    return value && /^[a-f0-9]{40}$/.test(value) ? value : null;
  }
}
