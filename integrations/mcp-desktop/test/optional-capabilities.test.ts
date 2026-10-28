// Copyright 2026 Firefly Software Foundation
// SPDX-License-Identifier: Apache-2.0

import assert from 'node:assert/strict';
import { test } from 'node:test';
import { createServer } from 'node:http';
import { Client } from '@modelcontextprotocol/sdk/client/index.js';
import { InMemoryTransport } from '@modelcontextprotocol/sdk/inMemory.js';
import { Server } from '@modelcontextprotocol/sdk/server/index.js';
import { StreamableHTTPServerTransport } from '@modelcontextprotocol/sdk/server/streamableHttp.js';
import { createBridge } from '../src/bridge.js';

for (const unauthorized of [false, true]) {
  test(unauthorized ? 'authorization failures stay errors without response body or token disclosure' : 'missing optional remote capabilities return empty discovery lists', async () => {
    const http = createServer(async (req, res) => {
      if (unauthorized) { res.writeHead(401).end('secret-token must not reach local errors'); return; }
      if (req.method === 'GET') { res.writeHead(405).end(); return; }
      const remote = new Server({ name: 'tools-only', version: '1.0.0' }, { capabilities: { tools: {} } });
      const transport = new StreamableHTTPServerTransport({ sessionIdGenerator: undefined, enableJsonResponse: true });
      await remote.connect(transport);
      res.on('close', () => { void remote.close(); });
      await transport.handleRequest(req, res);
    });
    await new Promise<void>((done) => http.listen(0, '127.0.0.1', done));
    const address = http.address();
    assert.ok(address && typeof address !== 'string');
    const bridge = createBridge({ url: new URL(`http://127.0.0.1:${address.port}/mcp`), token: 'secret-token' }, 'data:image/png;base64,', 'data:image/png;base64,');
    const [local, host] = InMemoryTransport.createLinkedPair();
    const client = new Client({ name: 'test-host', version: '1.0.0' });
    try {
      await bridge.connect(local);
      await client.connect(host);
      if (unauthorized) {
        await assert.rejects(client.listResources(), (error: Error) => /request failed/.test(error.message) && !/secret-token/.test(error.message));
        await assert.rejects(client.listPrompts());
      } else {
        assert.deepEqual(await client.listResources(), { resources: [] });
        assert.deepEqual(await client.listResourceTemplates(), { resourceTemplates: [] });
        assert.deepEqual(await client.listPrompts(), { prompts: [] });
      }
    } finally {
      await client.close();
      await bridge.close();
      await new Promise<void>((done) => http.close(() => done()));
    }
  });
}
