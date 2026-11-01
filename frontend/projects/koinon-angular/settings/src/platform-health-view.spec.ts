// Copyright 2026 Firefly Software Foundation
// SPDX-License-Identifier: Apache-2.0
import type { HealthComponent } from '@fireflyframework/koinon-sdk/platform-health';
import { healthStatus, healthSummary } from './platform-health-view';
const now = Date.parse('2026-11-01T10:00:00Z');
const observed: HealthComponent = {
  id: 'database-primary',
  configured: true,
  status: 'passed',
  basis: 'observed',
  freshness: 'current',
  observed_at: '2026-11-01T09:59:00Z',
  expires_at: '2026-11-01T10:01:00Z',
  reason: 'DATABASE_OK',
  remediation: 'none',
  coverage: 'complete',
};
it('marks only a bounded current successful observation as passed', () => {
  expect(healthStatus(observed, now)).toBe('passed');
});
for (const [name, change] of [
  ['configuration alone', { basis: 'configuration' }],
  ['stale evidence', { freshness: 'stale' }],
  ['expired evidence', { expires_at: '2026-11-01T10:00:00Z' }],
  ['missing expiry', { expires_at: null }],
  ['invalid observation time', { observed_at: 'not-a-time' }],
  ['future observation', { observed_at: '2026-11-01T10:02:00Z' }],
] as [string, Partial<HealthComponent>][])
  it(`does not mark ${name} as passed`, () => {
    expect(healthStatus({ ...observed, ...change }, now)).toBe('unknown');
  });
it('keeps disabled configuration separate from unknown checks', () => {
  expect(healthStatus({ ...observed, status: 'disabled', basis: 'configuration' }, now)).toBe(
    'disabled',
  );
});
it('shows a current configuration problem as needing attention', () => {
  expect(
    healthStatus(
      {
        ...observed,
        status: 'failed',
        basis: 'configuration',
        observed_at: null,
        expires_at: null,
        reason: 'MODEL_CONFIGURATION_INCOMPLETE',
      },
      now,
    ),
  ).toBe('failed');
});
it('reclassifies an expired failed observation without hiding its last known detail', () => {
  expect(
    healthStatus({ ...observed, status: 'failed', expires_at: '2026-11-01T09:59:59Z' }, now),
  ).toBe('unknown');
});
it('counts returned observations and reclassifies expired entries independently of server summary', () => {
  const components = [
    observed,
    { ...observed, id: 'workers', status: 'unknown' },
    { ...observed, id: 'communications', status: 'disabled' },
    { ...observed, id: 'indexes-documents', status: 'failed' },
  ] as HealthComponent[];
  expect(healthSummary(components, now)).toEqual({ passed: 1, failed: 1, unknown: 1, disabled: 1 });
  expect(healthSummary(components, now + 60000)).toEqual({
    passed: 0,
    failed: 0,
    unknown: 3,
    disabled: 1,
  });
});
