// Copyright 2026 Firefly Software Foundation
// SPDX-License-Identifier: Apache-2.0

import assert from 'node:assert/strict';
import { test } from 'node:test';
import { createServer } from 'node:http';
import { mkdtemp, cp, rm, readFile } from 'node:fs/promises';
import { tmpdir } from 'node:os';
import { join, resolve } from 'node:path';
import { Client } from '@modelcontextprotocol/sdk/client/index.js';
import { StdioClientTransport } from '@modelcontextprotocol/sdk/client/stdio.js';
import { Server } from '@modelcontextprotocol/sdk/server/index.js';
import { StreamableHTTPServerTransport } from '@modelcontextprotocol/sdk/server/streamableHttp.js';
import { CallToolRequestSchema, ListToolsRequestSchema, ListResourcesRequestSchema, ReadResourceRequestSchema, ListResourceTemplatesRequestSchema, ListPromptsRequestSchema, GetPromptRequestSchema } from '@modelcontextprotocol/sdk/types.js';

test('relocated bundle forwards authenticated discovery, tools, resources, and prompts without local dependencies', async () => {
  let requests = 0;
  const http = createServer(async (req, res) => {
    requests++;
    assert.equal(req.url, '/mcp');
    assert.equal(req.headers.authorization, 'Bearer relocation-test-token');
    if (req.method === 'GET') { res.writeHead(405).end(); return; }
    const server = new Server({ name: 'test-upstream', version: '1.0.0' }, { capabilities: { tools: {}, resources: {}, prompts: {} } });
    server.setRequestHandler(ListToolsRequestSchema, () => ({ tools: [{ name: 'koinon_context', description: 'Remote contract', inputSchema: { type: 'object', additionalProperties: false } }] }));
    server.setRequestHandler(CallToolRequestSchema, (request) => ({ content: [{ type: 'text', text: JSON.stringify(request.params) }] }));
    server.setRequestHandler(ListResourcesRequestSchema, () => ({ resources: [{ name: 'guide', uri: 'koinon://guide' }] }));
    server.setRequestHandler(ListResourceTemplatesRequestSchema, () => ({ resourceTemplates: [] }));
    server.setRequestHandler(ReadResourceRequestSchema, () => ({ contents: [{ uri: 'koinon://guide', text: 'Evidence' }] }));
    server.setRequestHandler(ListPromptsRequestSchema, () => ({ prompts: [{ name: 'investigate' }] }));
    server.setRequestHandler(GetPromptRequestSchema, () => ({ messages: [{ role: 'user', content: { type: 'text', text: 'Find evidence.' } }] }));
    const transport = new StreamableHTTPServerTransport({ sessionIdGenerator: undefined, enableJsonResponse: true });
    await server.connect(transport);
    res.on('close', () => { void server.close(); });
    await transport.handleRequest(req, res);
  });
  await new Promise<void>((done) => http.listen(0, '127.0.0.1', done));
  const address = http.address();
  assert.ok(address && typeof address !== 'string');
  const temp = await mkdtemp(join(tmpdir(), 'koinon relocated '));
  let client: Client | undefined;
  try {
    await cp(resolve('build/server'), join(temp, 'server'), { recursive: true });
    const manifest = JSON.parse(await readFile('manifest.json', 'utf8'));
    assert.equal(manifest.server.mcp_config.args[0], '${__dirname}/server/index.cjs');
    const transport = new StdioClientTransport({ command: process.execPath, args: [join(temp, 'server/index.cjs')], cwd: temp, env: {
      KOINON_MCP_URL: `http://127.0.0.1:${address.port}/mcp`, KOINON_TOKEN: 'relocation-test-token', KOINON_ALLOW_LOOPBACK_HTTP: '1',
    }, stderr: 'pipe' });
    let stderr = '';
    transport.stderr?.on('data', (chunk) => { stderr += String(chunk); });
    client = new Client({ name: 'installation-smoke', version: '1.0.0' });
    await client.connect(transport);
    assert.equal(requests, 0, 'starting and initializing locally must not connect upstream');
    assert.equal(client.getServerVersion()?.title, 'koinon');
    assert.equal((await client.listTools()).tools[0].name, 'koinon_context');
    const result = await client.callTool({ name: 'koinon_context', arguments: {} });
    assert.match(JSON.stringify(result), /koinon_context/);
    assert.equal((await client.listResources()).resources[0].uri, 'koinon://guide');
    assert.equal((await client.listResourceTemplates()).resourceTemplates.length, 0);
    const content = (await client.readResource({ uri: 'koinon://guide' })).contents[0];
    assert.ok('text' in content);
    assert.equal(content.text, 'Evidence');
    assert.equal((await client.listPrompts()).prompts[0].name, 'investigate');
    assert.equal((await client.getPrompt({ name: 'investigate' })).messages.length, 1);
    assert.ok(requests > 1);
    assert.equal(stderr.includes('relocation-test-token'), false);
  } finally {
    await client?.close();
    await new Promise<void>((done) => http.close(() => done()));
    await rm(temp, { recursive: true, force: true });
  }
});
