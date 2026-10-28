// Copyright 2026 Firefly Software Foundation
// SPDX-License-Identifier: Apache-2.0

import assert from 'node:assert/strict';
import { test } from 'node:test';
import { parseConfig, restrictedFetch } from '../src/config.js';

test('requires explicit HTTPS endpoint and a token without URL credentials', () => {
  const good = { KOINON_MCP_URL: 'https://knowledge.example.com/mcp', KOINON_TOKEN: 'test-pat' };
  assert.equal(parseConfig(good).url.href, good.KOINON_MCP_URL);
  for (const url of ['http://knowledge.example.com/mcp', 'https://user:secret@example.com/mcp', 'https://example.com/mcp?token=secret', 'https://example.com/mcp#secret', 'file:///mcp']) {
    assert.throws(() => parseConfig({ ...good, KOINON_MCP_URL: url }));
  }
  assert.throws(() => parseConfig({ KOINON_MCP_URL: good.KOINON_MCP_URL }));
  assert.throws(() => parseConfig({ ...good, KOINON_TOKEN: 'bad\r\nheader' }));
  assert.throws(() => parseConfig({ ...good, KOINON_MCP_URL: 'http://localhost:3000/mcp' }));
  assert.equal(parseConfig({ ...good, KOINON_MCP_URL: 'http://127.0.0.1:3000/mcp', KOINON_ALLOW_LOOPBACK_HTTP: '1' }).url.protocol, 'http:');
  assert.throws(() => parseConfig({ ...good, KOINON_MCP_URL: 'http://127.0.0.2:3000/mcp', KOINON_ALLOW_LOOPBACK_HTTP: '1' }));
});

test('restricted fetch binds credentials to exact endpoint and forbids redirects', async () => {
  const config = parseConfig({ KOINON_MCP_URL: 'https://knowledge.example.com/mcp', KOINON_TOKEN: 'test-pat' });
  let calls = 0;
  const fetcher = restrictedFetch(config, async (_url, init) => {
    calls++;
    assert.equal(init?.redirect, 'error');
    assert.equal(new Headers(init?.headers).get('authorization'), 'Bearer test-pat');
    assert.ok(init?.signal);
    return new Response('{}', { status: 200 });
  });
  await fetcher(config.url, { method: 'POST' });
  assert.equal(calls, 1);
  await assert.rejects(fetcher('https://other.example.com/mcp'));
  await assert.rejects(fetcher('https://knowledge.example.com/other'));
  assert.equal(calls, 1);
});

test('restricted fetch rejects redirect responses even with a custom transport', async () => {
  const config = parseConfig({ KOINON_MCP_URL: 'https://knowledge.example.com/mcp', KOINON_TOKEN: 'test-pat' });
  const fetcher = restrictedFetch(config, async () => new Response(null, { status: 302, headers: { location: 'https://other.example.com' } }));
  await assert.rejects(fetcher(config.url), /redirect/i);
});
