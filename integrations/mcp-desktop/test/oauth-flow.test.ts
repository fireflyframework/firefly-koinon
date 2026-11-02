// Copyright 2026 Firefly Software Foundation
// SPDX-License-Identifier: Apache-2.0
import assert from 'node:assert/strict';
import { createHash } from 'node:crypto';
import { createServer, request } from 'node:http';
import { cp, mkdtemp, readdir, rm } from 'node:fs/promises';
import { tmpdir } from 'node:os';
import { join, resolve } from 'node:path';
import { spawn } from 'node:child_process';
import { test, type TestContext } from 'node:test';
import { Client } from '@modelcontextprotocol/sdk/client/index.js';
import { InMemoryTransport } from '@modelcontextprotocol/sdk/inMemory.js';
import { StdioClientTransport } from '@modelcontextprotocol/sdk/client/stdio.js';
import { Server } from '@modelcontextprotocol/sdk/server/index.js';
import { StreamableHTTPServerTransport } from '@modelcontextprotocol/sdk/server/streamableHttp.js';
import { CallToolRequestSchema, ListToolsRequestSchema, ToolListChangedNotificationSchema } from '@modelcontextprotocol/sdk/types.js';
import { createBridge } from '../src/bridge.js';
import type { OAuthConfig } from '../src/config.js';

async function oauthFixture(t: TestContext, relocated = false) {
  let authUrl: URL | undefined;
  let metadataPatch: Record<string, unknown> = {};
  let resourcePatch: Record<string, unknown> = {};
  let tokenPatch: Record<string, unknown> = {};
  let challenge = false;
  let forbiddenChallenge = false;
  let revoked = false;
  let calls = 0;
  let exchanges = 0;
  let discovery = 0;
  let notifications = 0;
  let token = '';
  let metadataStatus = 200;
  let exchangeGate: Promise<void> | undefined;
  let exchangeStarted: (() => void) | undefined;
  let requestedScope = 'catalog:read knowledge:search';
  const http = createServer(async (req, res) => {
    if (req.url === '/.well-known/oauth-protected-resource/mcp') {
      discovery++;
      assert.equal(req.headers.authorization, undefined);
      if (metadataStatus !== 200) { res.writeHead(metadataStatus, { location: 'https://evil.example/metadata' }).end(); return; }
      res.setHeader('Content-Type', 'application/json');
      res.end(JSON.stringify({ resource: config.url.href, authorization_servers: [issuer], scopes_supported: ['catalog:read', 'knowledge:search', 'catalog:write'], ...resourcePatch })); return;
    }
    if (req.url === '/.well-known/oauth-authorization-server/oauth2/mcp') {
      assert.equal(req.headers.authorization, undefined);
      res.setHeader('Content-Type', 'application/json');
      res.end(JSON.stringify({ issuer, authorization_endpoint: issuer + '/authorize', token_endpoint: issuer + '/token', response_types_supported: ['code'], grant_types_supported: ['authorization_code'], code_challenge_methods_supported: ['S256'], token_endpoint_auth_methods_supported: ['none'], ...metadataPatch })); return;
    }
    if (req.url === '/oauth2/mcp/token') {
      exchanges++;
      exchangeStarted?.();
      await exchangeGate;
      assert.equal(req.headers.authorization, undefined);
      const parts = [];
      for await (const chunk of req) parts.push(Buffer.from(chunk));
      const body = new URLSearchParams(Buffer.concat(parts).toString());
      assert.equal(body.get('client_id'), 'desktop-test');
      assert.equal(body.get('grant_type'), 'authorization_code');
      assert.equal(body.get('resource'), config.url.href);
      assert.equal(body.get('redirect_uri'), config.redirectUrl.href);
      assert.equal(body.get('code'), 'owned-one-use-code');
      assert.equal(createHash('sha256').update(body.get('code_verifier') || '').digest('base64url'), authUrl?.searchParams.get('code_challenge'));
      token = `owned-access-${exchanges}`;
      res.setHeader('Content-Type', 'application/json');
      res.end(JSON.stringify({ access_token: token, token_type: 'Bearer', expires_in: 3600, scope: authUrl?.searchParams.get('scope'), ...tokenPatch })); return;
    }
    assert.equal(req.url, '/mcp');
    if (revoked || !token || req.headers.authorization !== `Bearer ${token}`) { res.writeHead(401).end('private upstream detail'); return; }
    if (req.method === 'GET') { res.writeHead(405).end(); return; }
    const remote = new Server({ name: 'owned-remote', version: '1' }, { capabilities: { tools: {} } });
    remote.setRequestHandler(ListToolsRequestSchema, () => ({ tools: [
      { name: 'koinon_search', inputSchema: { type: 'object' }, _meta: { ui: { resourceUri: 'ui://review', visibility: ['app'] } } },
      { name: 'koinon_desktop_connect', inputSchema: { type: 'object' }, description: 'Remote name collision' },
    ] }));
    remote.setRequestHandler(CallToolRequestSchema, () => {
      calls++;
      if (challenge || forbiddenChallenge) return { isError: true, content: [{ type: 'text', text: 'Denied before execution' }], _meta: { 'mcp/www_authenticate': [
        `Bearer resource_metadata="${forbiddenChallenge ? 'https://evil.example/meta' : config.url.origin + '/.well-known/oauth-protected-resource/mcp'}", error="insufficient_scope", scope="${requestedScope}"`,
      ] } };
      return { content: [{ type: 'text', text: 'Owned evidence' }], _meta: { private: 'retained-private-review' } };
    });
    const transport = new StreamableHTTPServerTransport({ sessionIdGenerator: undefined, enableJsonResponse: true });
    await remote.connect(transport);
    res.on('close', () => { void remote.close(); });
    await transport.handleRequest(req, res);
  });
  await new Promise<void>((done) => http.listen(0, '127.0.0.1', done));
  const address = http.address(); assert.ok(address && typeof address !== 'string');
  const callback = createServer();
  await new Promise<void>((done) => callback.listen(0, '127.0.0.1', done));
  const callbackAddress = callback.address(); assert.ok(callbackAddress && typeof callbackAddress !== 'string');
  await new Promise<void>((done) => callback.close(() => done()));
  const config: OAuthConfig = { mode: 'oauth', url: new URL(`http://127.0.0.1:${address.port}/mcp`), clientId: 'desktop-test', redirectUrl: new URL(`http://127.0.0.1:${callbackAddress.port}/oauth/callback`) };
  const issuer = config.url.origin + '/oauth2/mcp';
  const host = new Client({ name: 'owned-host', version: '1' }, { capabilities: {} });
  host.setNotificationHandler(ToolListChangedNotificationSchema, () => { notifications++; });
  let bridge: Server | undefined;
  let directory: string | undefined;
  let stderr = '';
  if (relocated) {
    directory = await mkdtemp(join(tmpdir(), 'koinon oauth relocated '));
    await cp(resolve('build/server'), join(directory, 'server'), { recursive: true });
    const transport = new StdioClientTransport({ command: process.execPath, args: [join(directory, 'server/index.cjs')], cwd: directory, env: {
      KOINON_MCP_URL: config.url.href, KOINON_AUTH_MODE: 'oauth', KOINON_OAUTH_CLIENT_ID: config.clientId,
      KOINON_OAUTH_CALLBACK_PORT: config.redirectUrl.port, KOINON_ALLOW_LOOPBACK_HTTP: '1',
    }, stderr: 'pipe' });
    transport.stderr?.on('data', (chunk) => { stderr += String(chunk); });
    await host.connect(transport);
  } else {
    bridge = createBridge(config, 'data:image/png;base64,', 'data:image/png;base64,');
    const [local, client] = InMemoryTransport.createLinkedPair();
    await bridge.connect(local); await host.connect(client);
  }
  t.after(async () => {
    await host.close(); await bridge?.close(); http.closeAllConnections(); await new Promise<void>((done) => http.close(() => done()));
    if (directory) await rm(directory, { recursive: true, force: true });
  });
  const tool = async (name: string, args = {}) => host.callTool({ name, arguments: args });
  const status = async () => (await tool('koinon_desktop_status')).structuredContent as Record<string, unknown>;
  const connect = async () => {
    const result = await tool('koinon_desktop_connect');
    assert.equal(result.isError, undefined, JSON.stringify(result));
    authUrl = new URL((result.structuredContent as { authorization_url: string }).authorization_url);
    return authUrl;
  };
  const complete = async (changes: Record<string, string> = {}) => {
    assert.ok(authUrl);
    const url = new URL(config.redirectUrl);
    url.search = new URLSearchParams({ state: authUrl.searchParams.get('state')!, iss: issuer, code: 'owned-one-use-code', ...changes }).toString();
    return fetch(url);
  };
  return { host, config, issuer, tool, status, connect, complete,
    counts: () => ({ calls, exchanges, discovery, notifications }),
    metadata: (value: Record<string, unknown>) => { metadataPatch = value; },
    resource: (value: Record<string, unknown>) => { resourcePatch = value; },
    token: (value: Record<string, unknown>) => { tokenPatch = value; },
    challenge: (foreign = false, scope = 'catalog:read knowledge:search') => { challenge = !foreign; forbiddenChallenge = foreign; requestedScope = scope; },
    revoke: () => { revoked = true; },
    metadataStatus: (status: number) => { metadataStatus = status; },
    localFiles: () => directory ? readdir(directory) : Promise.resolve([]),
    stderr: () => stderr,
    delayExchange: () => {
      let release!: () => void;
      exchangeGate = new Promise<void>((done) => { release = done; });
      const started = new Promise<void>((done) => { exchangeStarted = done; });
      t.after(release);
      return { started, release };
    },
  };
}

test('discovery stays local until explicit connection and OAuth callback enables remote tools without leaking tokens', async (t) => {
  const f = await oauthFixture(t);
  assert.deepEqual((await f.host.listTools()).tools.map((v) => v.name), ['koinon_desktop_connect', 'koinon_desktop_status', 'koinon_desktop_disconnect']);
  assert.equal(f.counts().discovery, 0);
  assert.deepEqual(await f.host.listResources(), { resources: [] });
  const url = await f.connect();
  assert.equal(url.origin + url.pathname, f.issuer + '/authorize');
  assert.equal(url.searchParams.get('scope'), 'catalog:read');
  assert.equal(url.searchParams.get('code_challenge_method'), 'S256');
  assert.equal(url.searchParams.has('code_verifier'), false);
  assert.equal((await f.status()).state, 'awaiting_authorization');
  assert.equal((await f.complete()).status, 200);
  assert.equal((await f.status()).state, 'connected');
  const tools = (await f.host.listTools()).tools;
  assert.equal(tools.filter((v) => v.name === 'koinon_desktop_connect').length, 1);
  assert.deepEqual(tools.find((v) => v.name === 'koinon_search')?._meta, { ui: { resourceUri: 'ui://review', visibility: ['app'] } });
  assert.deepEqual((await f.tool('koinon_search'))._meta, { private: 'retained-private-review' });
  assert.ok(f.counts().notifications > 0);
  assert.equal(JSON.stringify(await f.status()).includes('owned-access'), false);
  await f.tool('koinon_desktop_disconnect');
  assert.equal((await f.status()).state, 'disconnected');
  assert.equal((await f.host.listTools()).tools.length, 3);
});

test('wrong state, issuer and duplicate callback parameters cannot consume a pending authorization', async (t) => {
  const f = await oauthFixture(t); const url = await f.connect();
  assert.equal((await f.complete({ state: 'wrong' })).status, 400);
  assert.equal((await f.complete({ iss: 'https://evil.example' })).status, 400);
  const duplicate = new URL(f.config.redirectUrl);
  duplicate.search = `state=${url.searchParams.get('state')}&state=wrong&iss=${encodeURIComponent(f.issuer)}&code=owned-one-use-code`;
  assert.equal((await fetch(duplicate)).status, 400);
  assert.equal(f.counts().exchanges, 0);
  assert.equal((await f.complete()).status, 200);
  await assert.rejects(f.complete());
  assert.equal(f.counts().exchanges, 1);
});

test('callback rejects multibyte state, foreign Host and POST without losing the valid transaction', async (t) => {
  const f = await oauthFixture(t); const auth = await f.connect();
  assert.equal((await f.complete({ state: 'é'.repeat(43) })).status, 400);
  const url = new URL(f.config.redirectUrl);
  url.search = new URLSearchParams({ state: auth.searchParams.get('state')!, iss: f.issuer, code: 'owned-one-use-code' }).toString();
  const foreignHost = await new Promise<number | undefined>((resolve, reject) => {
    const req = request(url, { headers: { host: 'evil.example' } }, (response) => { response.resume(); response.on('end', () => resolve(response.statusCode)); });
    req.on('error', reject); req.end();
  });
  assert.equal(foreignHost, 400);
  assert.equal((await fetch(url, { method: 'POST' })).status, 400);
  assert.equal(f.counts().exchanges, 0);
  assert.equal((await f.complete()).status, 200);
});

test('denial and disconnect stop callbacks without exchanging credentials', async (t) => {
  const f = await oauthFixture(t); const auth = await f.connect();
  const denied = new URL(f.config.redirectUrl);
  denied.search = new URLSearchParams({ state: auth.searchParams.get('state')!, iss: f.issuer, error: 'access_denied' }).toString();
  assert.equal((await fetch(denied)).status, 200);
  assert.equal((await f.status()).state, 'denied');
  await f.connect(); await f.tool('koinon_desktop_disconnect');
  await assert.rejects(f.complete());
  assert.equal(f.counts().exchanges, 0);
});

test('concurrent explicit connects share one bounded callback and do not recreate transactions', async (t) => {
  const f = await oauthFixture(t);
  const [one, two] = await Promise.all([f.connect(), f.connect()]);
  assert.equal(one.href, two.href);
  assert.equal(f.counts().discovery, 1);
  assert.equal((await f.complete()).status, 200);
  assert.equal(f.counts().exchanges, 1);
});

test('an occupied callback port fails closed and remains owned by its existing listener', async (t) => {
  const f = await oauthFixture(t);
  const occupied = createServer((_req, res) => res.end('original listener'));
  await new Promise<void>((done) => occupied.listen(Number(f.config.redirectUrl.port), '127.0.0.1', done));
  t.after(() => new Promise<void>((done) => occupied.close(() => done())));
  assert.equal((await f.tool('koinon_desktop_connect')).isError, true);
  assert.equal(await (await fetch(f.config.redirectUrl)).text(), 'original listener');
  assert.equal(f.counts().exchanges, 0);
});

test('revoked upstream authorization removes remote discovery and never replays the request', async (t) => {
  const f = await oauthFixture(t); await f.connect(); await f.complete(); await f.host.listTools(); f.revoke();
  await assert.rejects(f.tool('koinon_search'), /koinon_desktop_status/);
  assert.equal((await f.status()).state, 'authorization_required');
  assert.equal((await f.host.listTools()).tools.length, 3);
  assert.equal(f.counts().calls, 0);
  assert.equal(f.counts().exchanges, 1);
});

test('expired access tokens are erased locally without an automatic refresh or browser flow', async (t) => {
  const f = await oauthFixture(t); f.token({ expires_in: 1 }); await f.connect(); await f.complete();
  await new Promise((done) => setTimeout(done, 1050));
  assert.equal((await f.status()).state, 'expired');
  assert.equal((await f.host.listTools()).tools.length, 3);
  assert.equal(f.counts().exchanges, 1);
});

for (const patch of [{ refresh_token: 'unrequested-refresh' }, { token_type: 'Other' }, { scope: 'catalog:read catalog:write' }, { expires_in: 99999999 }, { access_token: 'header\r\ninjection' }]) {
  test(`unexpected token contract cannot enable remote access: ${Object.keys(patch)[0]}`, async (t) => {
    const f = await oauthFixture(t); f.token(patch); await f.connect();
    assert.equal((await f.complete()).status, 400);
    assert.equal((await f.status()).state, 'error');
    assert.equal((await f.host.listTools()).tools.length, 3);
  });
}

for (const patch of [{ resource: 'https://evil.example/mcp' }, { authorization_servers: ['https://evil.example/oauth'] }]) {
  test(`resource discovery cannot change trust: ${Object.keys(patch)[0]}`, async (t) => {
    const f = await oauthFixture(t); f.resource(patch);
    assert.equal((await f.tool('koinon_desktop_connect')).isError, true);
    assert.equal(f.counts().exchanges, 0);
  });
}

test('metadata redirects are refused without following their target', async (t) => {
  const f = await oauthFixture(t); f.metadataStatus(302);
  assert.equal((await f.tool('koinon_desktop_connect')).isError, true);
  assert.equal(f.counts().exchanges, 0);
});

test('oversized OAuth metadata is rejected before a callback or token exchange', async (t) => {
  const f = await oauthFixture(t); f.resource({ resource_name: 'x'.repeat(70_000) });
  assert.equal((await f.tool('koinon_desktop_connect')).isError, true);
  assert.equal(f.counts().exchanges, 0);
});

test('disconnect during code exchange cannot resurrect a session when the response arrives', async (t) => {
  const f = await oauthFixture(t); await f.connect(); const gate = f.delayExchange();
  const callback = f.complete(); await gate.started;
  await f.tool('koinon_desktop_disconnect'); gate.release();
  assert.equal((await callback).status, 400);
  assert.equal((await f.status()).state, 'disconnected');
  assert.equal((await f.host.listTools()).tools.length, 3);
});

test('a delayed old-session response cannot invalidate or expose data through a replacement session', async (t) => {
  const f = await oauthFixture(t); await f.connect(); await f.complete(); await f.host.listTools();
  const originalFetch = globalThis.fetch;
  let release!: () => void;
  const gate = new Promise<void>((done) => { release = done; });
  let start!: () => void;
  const started = new Promise<void>((done) => { start = done; });
  let held = false;
  t.mock.method(globalThis, 'fetch', async (input: Parameters<typeof fetch>[0], init?: RequestInit) => {
    const response = await originalFetch(input, init);
    if (!held && String(input) === f.config.url.href && typeof init?.body === 'string' && JSON.parse(init.body).method === 'tools/call') {
      held = true; start(); await gate;
      await response.body?.cancel().catch(() => undefined);
      return new Response('old private response', { status: 401 });
    }
    return response;
  });
  const old = f.tool('koinon_search').then((result) => ({ result }), (error: Error) => ({ error }));
  await started;
  await f.tool('koinon_desktop_disconnect'); await f.connect(); await f.complete(); await f.host.listTools();
  release(); await new Promise((done) => setImmediate(done));
  const outcome = await old;
  assert.ok('error' in outcome);
  assert.equal((await f.status()).state, 'connected');
  assert.match(JSON.stringify((await f.tool('koinon_search')).content), /Owned evidence/);
});

test('a late failed initialization cannot clear a newer upstream client', async (t) => {
  const f = await oauthFixture(t); await f.connect(); await f.complete();
  const originalFetch = globalThis.fetch;
  let release!: () => void;
  const gate = new Promise<void>((done) => { release = done; });
  let start!: () => void;
  const started = new Promise<void>((done) => { start = done; });
  let initializations = 0;
  t.mock.method(globalThis, 'fetch', async (input: Parameters<typeof fetch>[0], init?: RequestInit) => {
    const initialize = String(input) === f.config.url.href && typeof init?.body === 'string' && JSON.parse(init.body).method === 'initialize';
    const index = initialize ? ++initializations : 0;
    const response = await originalFetch(input, init);
    if (index === 1) { start(); await gate; await response.body?.cancel(); throw new Error('Old connection failed.'); }
    return response;
  });
  const old = f.host.listTools().catch(() => undefined);
  await started;
  await f.tool('koinon_desktop_disconnect'); await f.connect(); await f.complete(); await f.host.listTools();
  release(); await old; await new Promise((done) => setImmediate(done));
  await f.tool('koinon_search');
  assert.equal(initializations, 2);
  assert.equal((await f.status()).state, 'connected');
});

test('pending sign-in expires and a new explicit connection uses a fresh state', async (t) => {
  const f = await oauthFixture(t); const before = await f.connect();
  t.mock.timers.enable({ apis: ['Date'], now: Date.now() });
  // The existing real timer is not mocked; advance wall time to exercise the callback expiry fence.
  t.mock.timers.setTime(Date.now() + 121_000);
  assert.equal((await f.complete()).status, 400);
  assert.equal(f.counts().exchanges, 0);
  t.mock.timers.reset();
  await f.tool('koinon_desktop_disconnect');
  const after = await f.connect();
  assert.notEqual(after.searchParams.get('state'), before.searchParams.get('state'));
  assert.equal((await f.complete()).status, 200);
});

test('relocated standalone OAuth bundle completes sign-in with no local dependencies or token files', async (t) => {
  const f = await oauthFixture(t, true);
  assert.equal((await f.host.listTools()).tools.length, 3);
  assert.equal(f.counts().discovery, 0);
  await f.connect(); assert.equal((await f.complete()).status, 200);
  assert.ok((await f.host.listTools()).tools.some((tool) => tool.name === 'koinon_search'));
  await f.tool('koinon_search');
  await f.tool('koinon_desktop_disconnect');
  assert.deepEqual(await f.localFiles(), ['server']);
  assert.doesNotMatch(f.stderr(), /owned-access|owned-one-use-code|code_verifier/);
});

test('standalone bridge exits and closes pending OAuth callback when the host closes stdin', async (t) => {
  const f = await oauthFixture(t);
  const child = spawn(process.execPath, [resolve('build/server/index.cjs')], { stdio: ['pipe', 'pipe', 'pipe'], env: {
    ...process.env, KOINON_MCP_URL: f.config.url.href, KOINON_AUTH_MODE: 'oauth', KOINON_TOKEN: '',
    KOINON_OAUTH_CLIENT_ID: f.config.clientId, KOINON_OAUTH_CALLBACK_PORT: f.config.redirectUrl.port, KOINON_ALLOW_LOOPBACK_HTTP: '1',
  } });
  t.after(() => { child.kill('SIGTERM'); });
  let output = '';
  const replies = new Map<number, (message: Record<string, unknown>) => void>();
  child.stdout.setEncoding('utf8').on('data', (chunk) => {
    output += chunk;
    let index: number;
    while ((index = output.indexOf('\n')) >= 0) {
      const message = JSON.parse(output.slice(0, index)); output = output.slice(index + 1);
      replies.get(message.id)?.(message);
    }
  });
  const send = (id: number, method: string, params: Record<string, unknown>) => new Promise<Record<string, unknown>>((done) => {
    replies.set(id, done); child.stdin.write(JSON.stringify({ jsonrpc: '2.0', id, method, params }) + '\n');
  });
  await send(1, 'initialize', { protocolVersion: '2025-11-25', capabilities: {}, clientInfo: { name: 'owned-eof-host', version: '1' } });
  child.stdin.write(JSON.stringify({ jsonrpc: '2.0', method: 'notifications/initialized' }) + '\n');
  const connected = await send(2, 'tools/call', { name: 'koinon_desktop_connect', arguments: {} });
  assert.ok(connected.result);
  const exited = new Promise<boolean>((done) => { child.once('exit', () => done(true)); setTimeout(() => done(false), 1000).unref(); });
  child.stdin.end();
  assert.equal(await exited, true, 'EOF must stop pending authentication and exit without a signal.');
  await assert.rejects(fetch(f.config.redirectUrl));
});

test('trusted scope challenge requires explicit reconsent and never retries a tool call', async (t) => {
  const f = await oauthFixture(t); await f.connect(); await f.complete(); f.challenge();
  const result = await f.tool('koinon_search');
  assert.equal(result.isError, true);
  assert.match(JSON.stringify(result.content), /koinon_desktop_connect/);
  assert.equal(f.counts().calls, 1);
  assert.deepEqual((await f.status()).required_scopes, ['catalog:read', 'knowledge:search']);
  const url = await f.connect();
  assert.equal(url.searchParams.get('scope'), 'catalog:read knowledge:search');
  assert.equal((await f.complete()).status, 200);
  assert.equal(f.counts().calls, 1);
  f.challenge(false, 'catalog:read activity:read');
  await f.tool('koinon_search');
  assert.equal((await f.connect()).searchParams.get('scope'), 'activity:read catalog:read knowledge:search');
});

test('untrusted scope metadata does not trigger authorization or widen requested scope', async (t) => {
  const f = await oauthFixture(t); await f.connect(); await f.complete(); f.challenge(true);
  await f.tool('koinon_search');
  assert.deepEqual((await f.status()).required_scopes, []);
  assert.equal(f.counts().exchanges, 1);
  f.challenge(false, 'catalog:read admin:write');
  await f.tool('koinon_search');
  assert.deepEqual((await f.status()).required_scopes, []);
});

for (const patch of [{ issuer: 'https://evil.example' }, { token_endpoint: 'https://evil.example/token' }, { authorization_endpoint: 'https://evil.example/authorize' }, { code_challenge_methods_supported: ['plain'] }]) {
  test(`discovery refuses an untrusted OAuth contract: ${Object.keys(patch)[0]}`, async (t) => {
    const f = await oauthFixture(t); f.metadata(patch);
    assert.equal((await f.tool('koinon_desktop_connect')).isError, true);
    assert.equal(f.counts().exchanges, 0);
  });
}
