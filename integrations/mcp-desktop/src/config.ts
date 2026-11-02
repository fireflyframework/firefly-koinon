// Copyright 2026 Firefly Software Foundation
// SPDX-License-Identifier: Apache-2.0

export interface PatConfig { mode: 'pat'; url: URL; token: string }
export interface OAuthConfig { mode: 'oauth'; url: URL; clientId: string; redirectUrl: URL }
export type Config = PatConfig | OAuthConfig;

export function parseConfig(env: NodeJS.ProcessEnv): Config {
  if (!env.KOINON_MCP_URL) {
    throw new Error('Configure the koinon MCP endpoint.');
  }
  let url: URL;
  try { url = new URL(env.KOINON_MCP_URL); }
  catch { throw new Error('The koinon MCP endpoint must be a valid HTTPS URL.'); }
  const loopback = ['localhost', '127.0.0.1', '[::1]'].includes(url.hostname);
  const localDevelopment = env.KOINON_ALLOW_LOOPBACK_HTTP === '1' && loopback;
  if ((url.protocol !== 'https:' && !(url.protocol === 'http:' && localDevelopment)) || url.pathname !== '/mcp' || url.username || url.password || url.search || url.hash) {
    throw new Error('Use an HTTPS MCP URL without credentials, query parameters, or fragments.');
  }
  const mode = env.KOINON_AUTH_MODE || (env.KOINON_TOKEN ? 'pat' : 'oauth');
  if (mode === 'oauth') {
    if (env.KOINON_TOKEN) throw new Error('Remove the personal token for OAuth, or explicitly select pat authentication.');
    const clientId = env.KOINON_OAUTH_CLIENT_ID || '';
    const port = env.KOINON_OAUTH_CALLBACK_PORT || '42839';
    if (!/^[A-Za-z0-9._~-]{1,128}$/.test(clientId) || !/^\d{4,5}$/.test(port) || Number(port) < 1024 || Number(port) > 65535) {
      throw new Error('Configure the operator-registered public OAuth client ID and callback port (1024–65535).');
    }
    return { mode, url, clientId, redirectUrl: new URL(`http://127.0.0.1:${Number(port)}/oauth/callback`) };
  }
  if (mode !== 'pat') throw new Error('Choose oauth or pat authentication.');
  if (!env.KOINON_TOKEN?.trim() || /[\r\n\x00]/.test(env.KOINON_TOKEN)) {
    throw new Error('The koinon personal access token is invalid.');
  }
  return { mode, url, token: env.KOINON_TOKEN };
}

export function restrictedFetch(config: PatConfig, fetchImpl: typeof fetch = fetch): typeof fetch {
  return async (input, init) => {
    const requestUrl = input instanceof Request ? input.url : String(input);
    if (new URL(requestUrl).href !== config.url.href) {
      throw new Error('The bridge only sends requests to the configured koinon MCP endpoint.');
    }
    const headers = new Headers(input instanceof Request ? input.headers : undefined);
    new Headers(init?.headers).forEach((value, key) => headers.set(key, value));
    headers.set('Authorization', `Bearer ${config.token}`);
    const signal = AbortSignal.any([AbortSignal.timeout(30_000), ...(init?.signal ? [init.signal] : [])]);
    const response = await fetchImpl(input, { ...init, headers, redirect: 'error', signal });
    if (response.status >= 300 && response.status < 400) {
      throw new Error('The koinon MCP endpoint must not redirect.');
    }
    return response;
  };
}
