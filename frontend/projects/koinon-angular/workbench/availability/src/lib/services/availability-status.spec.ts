// Copyright 2026 Firefly Software Foundation
// SPDX-License-Identifier: Apache-2.0
import { expect, it } from 'vitest';
import type { AssetAvailability } from '@fireflyframework/koinon-sdk/availability';
import { availabilityStatus } from './availability-status';
function availability(values: Partial<AssetAvailability>): AssetAvailability { return {
  phase: 'complete', read: { state: 'ready', reason: 'RECORDED' }, search: { state: 'pending', reason: 'INDEX_PENDING' },
  query: { state: 'not_applicable', reason: 'DOCUMENT' }, revision: {}, ...values,
}; }
it('keeps extracted text distinct from searchable completion', () => {
  expect(availabilityStatus(availability({}))).toEqual({ label: 'Text available; search pending', tone: 'processing' });
  expect(availabilityStatus(availability({ search: { state: 'ready', reason: 'INDEX_ACTIVE' } })))
    .toEqual({ label: 'Searchable', tone: 'ready' });
});
it('distinguishes processing, failure, unresolved state, and query readiness', () => {
  expect(availabilityStatus(availability({ phase: 'processing' })).tone).toBe('processing');
  expect(availabilityStatus(availability({ phase: 'failed' })).tone).toBe('error');
  expect(availabilityStatus(undefined).tone).toBe('attention');
  expect(availabilityStatus(availability({ query: { state: 'ready', reason: 'QUERY_READY' } }), 'dataset'))
    .toEqual({ label: 'Available to query', tone: 'ready' });
});
