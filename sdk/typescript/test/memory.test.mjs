// Copyright 2026 Firefly Software Foundation
// SPDX-License-Identifier: Apache-2.0
import assert from 'node:assert/strict';
import { test } from 'node:test';
import { FetchTransport, KoinonClient } from '../dist/index.js';

test('memory and conversation removal preserve explicit choices and current revisions', async () => {
  const calls = [];
  const client = new KoinonClient({ transport: new FetchTransport({
    baseUrl: 'https://example.test/api/v1', accessToken: () => 'fixture',
    fetch: async (url, init) => {
      calls.push({ url: new URL(url), init });
      return init.method === 'DELETE' ? new Response(null, { status: 204 })
        : new Response('{}', { headers: { 'Content-Type': 'application/json' } });
    },
  }) });
  await client.chat.folders.update('tenant/one', 'folder/one', { expected_revision: 2, memory_enabled: false });
  await client.organizationChat.update('tenant/one', {
    expected_revision: 3, default_agent_id: 'agent', memory: { allow_project_memory: false },
  });
  await client.chat.delete('tenant/one', 'thread/one', 5);
  assert.deepEqual(JSON.parse(calls[0].init.body), { expected_revision: 2, memory_enabled: false });
  assert.deepEqual(JSON.parse(calls[1].init.body).memory, { allow_project_memory: false });
  assert.equal(calls[2].init.method, 'DELETE');
  assert.equal(calls[2].url.pathname, '/api/v1/tenants/tenant%2Fone/chat/threads/thread%2Fone');
  assert.equal(calls[2].url.searchParams.get('expected_revision'), '5');
});
