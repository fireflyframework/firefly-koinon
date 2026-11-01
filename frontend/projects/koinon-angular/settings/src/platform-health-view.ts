// Copyright 2026 Firefly Software Foundation
// SPDX-License-Identifier: Apache-2.0
import type { HealthComponent, HealthStatus } from '@fireflyframework/koinon-sdk/platform-health';
export function healthStatus(component: HealthComponent, now: number): HealthStatus {
  if (component.status === 'disabled') return 'disabled';
  if (
    component.status === 'failed' &&
    component.basis === 'configuration' &&
    component.freshness !== 'stale'
  )
    return 'failed';
  const observed = Date.parse(component.observed_at ?? '');
  const expires = Date.parse(component.expires_at ?? '');
  if (
    component.basis !== 'observed' ||
    component.freshness !== 'current' ||
    !Number.isFinite(observed) ||
    !Number.isFinite(expires) ||
    observed > now ||
    expires <= now ||
    expires <= observed
  )
    return 'unknown';
  return component.status === 'passed' || component.status === 'failed'
    ? component.status
    : 'unknown';
}
export function healthSummary(
  components: readonly HealthComponent[],
  now: number,
): Record<HealthStatus, number> {
  const summary = { passed: 0, failed: 0, unknown: 0, disabled: 0 };
  for (const component of components) ++summary[healthStatus(component, now)];
  return summary;
}
