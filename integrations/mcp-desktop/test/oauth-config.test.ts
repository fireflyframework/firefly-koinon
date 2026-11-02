// Copyright 2026 Firefly Software Foundation
// SPDX-License-Identifier: Apache-2.0
import assert from 'node:assert/strict';
import { test } from 'node:test';
import { parseConfig } from '../src/config.js';

const settings = { KOINON_MCP_URL: 'https://knowledge.example.com/mcp', KOINON_OAUTH_CLIENT_ID: 'desktop', KOINON_OAUTH_CALLBACK_PORT: '42839' };

test('OAuth configuration needs no credential and binds a public client to an exact loopback callback', () => {
  const config = parseConfig(settings);
  assert.equal(config.mode, 'oauth');
  assert.equal(config.mode === 'oauth' && config.redirectUrl.href, 'http://127.0.0.1:42839/oauth/callback');
});

test('explicit OAuth cannot silently consume an old token and legacy PAT configuration still starts', () => {
  assert.throws(() => parseConfig({ ...settings, KOINON_AUTH_MODE: 'oauth', KOINON_TOKEN: 'old-pat' }));
  assert.equal(parseConfig({ KOINON_MCP_URL: settings.KOINON_MCP_URL, KOINON_TOKEN: 'old-pat' }).mode, 'pat');
  const config = parseConfig({ KOINON_MCP_URL: settings.KOINON_MCP_URL, KOINON_AUTH_MODE: 'pat', KOINON_TOKEN: 'owned-pat' });
  assert.equal(config.mode, 'pat');
  for (const changes of [{ KOINON_AUTH_MODE: 'other' }, { KOINON_OAUTH_CLIENT_ID: '' }, { KOINON_OAUTH_CALLBACK_PORT: '0' }, { KOINON_OAUTH_CALLBACK_PORT: '3.4' }, { KOINON_OAUTH_CALLBACK_PORT: '65536' }, { KOINON_MCP_URL: 'https://knowledge.example.com/other' }]) {
    assert.throws(() => parseConfig({ ...settings, ...changes }));
  }
});
