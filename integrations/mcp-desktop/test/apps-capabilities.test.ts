// Copyright 2026 Firefly Software Foundation
// SPDX-License-Identifier: Apache-2.0

import assert from 'node:assert/strict';
import { randomUUID } from 'node:crypto';
import { createServer } from 'node:http';
import { test } from 'node:test';
import { Client } from '@modelcontextprotocol/sdk/client/index.js';
import { InMemoryTransport } from '@modelcontextprotocol/sdk/inMemory.js';
import { Server } from '@modelcontextprotocol/sdk/server/index.js';
import { StreamableHTTPServerTransport } from '@modelcontextprotocol/sdk/server/streamableHttp.js';
import {
  CallToolRequestSchema, ErrorCode, ListResourcesRequestSchema, ListToolsRequestSchema,
  McpError, ReadResourceRequestSchema, type ClientCapabilities,
} from '@modelcontextprotocol/sdk/types.js';
import { createBridge } from '../src/bridge.js';

const UI = 'io.modelcontextprotocol/ui';
const MIME = 'text/html;profile=mcp-app';
const URI = 'ui://koinon/knowledge-review';

async function withBridge(capabilities: ClientCapabilities, run: (host: Client, upstream: Server) => Promise<void>) {
  const upstream = new Server({ name: 'owned-apps-upstream', version: '1.0.0' }, {
    capabilities: { tools: {}, resources: {}, extensions: { [UI]: {} } },
  });
  const supported = () => {
    const ui = upstream.getClientCapabilities()?.extensions?.[UI] as { mimeTypes?: string[] } | undefined;
    return ui?.mimeTypes?.includes(MIME) === true;
  };
  const toolMeta = { ui: { resourceUri: URI, visibility: ['app'] }, 'koinon/contract': 'exact' };
  upstream.setRequestHandler(ListToolsRequestSchema, () => ({ tools: supported() ? [{
    name: 'koinon_approve_knowledge', inputSchema: { type: 'object', additionalProperties: false }, _meta: toolMeta,
  }] : [{ name: 'koinon_context', inputSchema: { type: 'object' } }] }));
  upstream.setRequestHandler(CallToolRequestSchema, () => {
    if (!supported()) throw new McpError(ErrorCode.InvalidRequest, 'MCP Apps is required; secret upstream details');
    return { content: [{ type: 'text', text: 'Review the proposed change.' }],
      structuredContent: { review_id: 'owned-review' },
      _meta: { 'koinon/knowledgeReview': { nonce: 'private-owned-review-nonce', review: { id: 'owned-review' } } } };
  });
  upstream.setRequestHandler(ListResourcesRequestSchema, () => ({ resources: supported() ? [{
    uri: URI, name: 'koinon review', mimeType: MIME, _meta: { ui: { prefersBorder: true } },
  }] : [] }));
  upstream.setRequestHandler(ReadResourceRequestSchema, () => ({ contents: [{
    uri: URI, mimeType: MIME, text: '<!doctype html><title>koinon</title>',
    _meta: { ui: { csp: { connectDomains: [], resourceDomains: [] }, prefersBorder: true } },
  }] }));
  const transport = new StreamableHTTPServerTransport({ sessionIdGenerator: randomUUID, enableJsonResponse: true });
  await upstream.connect(transport);
  const http = createServer(async (req, res) => {
    assert.equal(req.url, '/mcp');
    assert.equal(req.headers.authorization, 'Bearer owned-bridge-token');
    await transport.handleRequest(req, res);
  });
  await new Promise<void>((done) => http.listen(0, '127.0.0.1', done));
  const address = http.address();
  assert.ok(address && typeof address !== 'string');
  const bridge = createBridge({ url: new URL(`http://127.0.0.1:${address.port}/mcp`), token: 'owned-bridge-token' },
    'data:image/png;base64,', 'data:image/png;base64,');
  const host = new Client({ name: 'owned-downstream-host', version: '1.0.0' }, { capabilities });
  const [local, client] = InMemoryTransport.createLinkedPair();
  try {
    await bridge.connect(local);
    await host.connect(client);
    await run(host, upstream);
  } finally {
    await host.close();
    await bridge.close();
    await upstream.close();
    await new Promise<void>((done) => http.close(() => done()));
  }
}

test('actual downstream Apps MIME capability reaches upstream initialization and preserves private review data', async () => {
  await withBridge({ extensions: { [UI]: { mimeTypes: [MIME] }, 'example/unrelated': {} }, sampling: {} }, async (host, upstream) => {
    const tools = await host.listTools();
    assert.deepEqual(upstream.getClientCapabilities()?.extensions, { [UI]: { mimeTypes: [MIME] } });
    assert.deepEqual(host.getServerCapabilities()?.extensions?.[UI], {});
    assert.equal(upstream.getClientCapabilities()?.sampling, undefined);
    assert.deepEqual(tools.tools[0]._meta, { ui: { resourceUri: URI, visibility: ['app'] }, 'koinon/contract': 'exact' });
    const result = await host.callTool({ name: 'koinon_approve_knowledge', arguments: {} });
    assert.deepEqual(result._meta, { 'koinon/knowledgeReview': { nonce: 'private-owned-review-nonce', review: { id: 'owned-review' } } });
    assert.equal(JSON.stringify(result.content).includes('private-owned-review-nonce'), false);
    assert.equal(JSON.stringify(result.structuredContent).includes('private-owned-review-nonce'), false);
    assert.equal((await host.listResources()).resources[0].mimeType, MIME);
    const resource = (await host.readResource({ uri: URI })).contents[0];
    assert.equal(resource.mimeType, MIME);
    assert.deepEqual(resource._meta, { ui: { csp: { connectDomains: [], resourceDomains: [] }, prefersBorder: true } });
    assert.ok('text' in resource && resource.text.includes('<title>koinon</title>'));
  });
});

for (const extension of [undefined, {}, { mimeTypes: [] }, { mimeTypes: ['text/html'] }, { mimeTypes: MIME }]) {
  test(`unsupported host does not gain Apps capabilities: ${JSON.stringify(extension)}`, async () => {
    await withBridge(extension ? { extensions: { [UI]: extension } } : {}, async (host, upstream) => {
      assert.equal((await host.listTools()).tools[0].name, 'koinon_context');
      assert.equal(upstream.getClientCapabilities()?.extensions?.[UI], undefined);
      await assert.rejects(host.callTool({ name: 'koinon_approve_knowledge', arguments: {},
        _meta: { extensions: { [UI]: { mimeTypes: [MIME] } } } }), (error: Error) =>
        /request failed/.test(error.message) && !/secret upstream|owned-bridge-token/.test(error.message));
      assert.equal(upstream.getClientCapabilities()?.extensions?.[UI], undefined);
    });
  });
}
