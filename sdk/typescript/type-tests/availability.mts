// Copyright 2026 Firefly Software Foundation
// SPDX-License-Identifier: Apache-2.0
import type { KoinonTransport, AvailabilityRequest, ProcessingRequest } from '../src/index.js';
import { createAvailabilityApi } from '../src/availability.js';
declare const transport: KoinonTransport;
const api = createAvailabilityApi(transport);
const selection: AvailabilityRequest = { asset_ids: ['asset'], workspace_id: 'workspace' };
const page: ProcessingRequest = { page: 1, page_size: 25 };
const observation = await api.observe('tenant', selection, { signal: new AbortController().signal });
void observation.items['asset']?.latest_attempt?.state;
void observation.items['asset']?.revision?.snapshot_id;
void api.processing('tenant', page);
// @ts-expect-error Observation selects explicit assets, never an arbitrary subject.
void api.observe('tenant', { subject: 'another-user', asset_ids: ['asset'] });
// @ts-expect-error Processing filters use the typed native paging contract.
void api.processing('tenant', { status: 'processing' });
