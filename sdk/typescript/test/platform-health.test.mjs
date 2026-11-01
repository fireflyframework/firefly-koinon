// Copyright 2026 Firefly Software Foundation
// SPDX-License-Identifier: Apache-2.0
import assert from 'node:assert/strict';
import test from 'node:test';
import { createPlatformHealthApi } from '../dist/platform-health.js';

test('platform reads preserve tenant path encoding and caller cancellation without request bodies', async () => {
  const calls = [];
  const signal = new AbortController().signal;
  const transport = { request: async (...args) => { calls.push(args); return { tenant_id: 'north' }; } };
  const api = createPlatformHealthApi(transport);
  await api.health('tenant/with space', { signal });
  await api.systemInformation('north', { signal });
  assert.deepEqual(calls.map(([method, path]) => [method, path]), [
    ['GET', '/tenants/tenant%2Fwith%20space/platform/health'],
    ['GET', '/tenants/north/platform/system-information'],
  ]);
  for (const [, , options] of calls) { assert.equal(options.signal, signal); assert.equal(options.body, undefined); }
});
