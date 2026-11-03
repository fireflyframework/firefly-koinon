// Copyright 2026 Firefly Software Foundation
// SPDX-License-Identifier: Apache-2.0
import type { AssetAvailability } from '@fireflyframework/koinon-sdk/availability';
import type { StatusTone } from '@fireflyframework/koinon-angular/workbench/core';
export function availabilityStatus(value?: AssetAvailability, kind?: string): { label: string; tone: StatusTone } {
  if (!value) return { label: 'Availability not checked', tone: 'attention' };
  if (value.phase === 'failed') return { label: 'Processing failed', tone: 'error' };
  if (value.phase === 'reconciliation_required') return { label: 'Review required', tone: 'attention' };
  if (value.phase === 'cancelled') return { label: 'Stopped', tone: 'attention' };
  if (value.phase === 'queued') return { label: 'Queued', tone: 'processing' };
  if (value.phase === 'processing') return { label: 'Processing', tone: 'processing' };
  if (value.phase === 'indexing') return { label: 'Indexing', tone: 'processing' };
  if (value.search?.state === 'ready') return { label: 'Searchable', tone: 'ready' };
  if (value.query?.state === 'ready') return { label: 'Available to query', tone: 'ready' };
  if (['dataset', 'table'].includes(kind ?? '') && value.query?.state === 'pending')
    return { label: 'Query preparation pending', tone: 'processing' };
  if (value.read?.state === 'ready') return {
    label: value.search?.state === 'pending' ? 'Text available; search pending' : 'Text available; search not checked',
    tone: value.search?.state === 'pending' ? 'processing' : 'attention',
  };
  return { label: 'Availability not checked', tone: 'attention' };
}
