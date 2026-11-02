// Copyright 2026 Firefly Software Foundation
// SPDX-License-Identifier: Apache-2.0

import { randomBytes, timingSafeEqual } from 'node:crypto';
import { createServer, type Server as HttpServer } from 'node:http';
import { exchangeAuthorization, startAuthorization } from '@modelcontextprotocol/sdk/client/auth.js';
import { OAuthMetadataSchema, OAuthProtectedResourceMetadataSchema, type OAuthMetadata } from '@modelcontextprotocol/sdk/shared/auth.js';
import type { OAuthConfig } from './config.js';

const SCOPES = new Set(['catalog:read', 'catalog:write', 'ingest:write', 'knowledge:search', 'query:execute', 'chat:use', 'evidence:read', 'activity:read']);
const AUTHORIZATION_TTL = 120_000;

function scopes(value: string): string[] {
  if (value.length > 256) throw new Error('Invalid authorization scope.');
  const values = value.split(' ');
  if (!values.length || values.some((v) => !SCOPES.has(v)) || new Set(values).size !== values.length) throw new Error('Invalid authorization scope.');
  return values.sort();
}

async function boundedJson(response: Response): Promise<Response> {
  if (!response.ok || response.headers.get('content-type')?.split(';')[0].trim().toLowerCase() !== 'application/json') {
    await response.body?.cancel().catch(() => undefined);
    throw new Error('OAuth endpoint rejected the request.');
  }
  const reader = response.body?.getReader();
  if (!reader) throw new Error('OAuth response is empty.');
  const chunks: Uint8Array[] = [];
  let size = 0;
  try {
    while (true) {
      const part = await reader.read();
      if (part.done) break;
      size += part.value.length;
      if (size > 64 * 1024) throw new Error('OAuth response exceeds its size limit.');
      chunks.push(part.value);
    }
  } finally { await reader.cancel().catch(() => undefined); }
  return new Response(Buffer.concat(chunks), { status: response.status, headers: { 'content-type': 'application/json' } });
}

export class OAuthSession {
  readonly issuer: string;
  readonly resourceMetadataUrl: string;
  private state = 'disconnected';
  private accessToken?: string;
  private expiresAt = 0;
  private granted: string[] = [];
  private required: string[] = [];
  private pending?: { server: HttpServer; timer: NodeJS.Timeout; state: string; verifier: string; url: string; scopes: string[]; metadata: OAuthMetadata; generation: number; expires: number };
  private starting?: Promise<Record<string, unknown>>;
  private generation = 0;
  private abort?: AbortController;
  private expiryTimer?: NodeJS.Timeout;

  constructor(private readonly config: OAuthConfig, private readonly changed: () => void, private readonly fetchImpl: typeof fetch = fetch) {
    this.issuer = config.url.origin + '/oauth2/mcp';
    this.resourceMetadataUrl = config.url.origin + '/.well-known/oauth-protected-resource/mcp';
  }

  status(): Record<string, unknown> {
    this.token();
    return { mode: 'oauth', state: this.state, endpoint: this.config.url.href, client_id: this.config.clientId,
      callback_url: this.config.redirectUrl.href, scopes: [...this.granted], required_scopes: [...this.required],
      expires_at: this.expiresAt ? new Date(this.expiresAt).toISOString() : null,
      storage: 'memory_only', server_revocation: 'Use Authorized applications in koinon account settings to revoke the server grant.' };
  }

  token(): string | undefined {
    if (this.accessToken && Date.now() >= this.expiresAt) this.invalidate('expired');
    return this.accessToken;
  }

  invalidate(state = 'disconnected'): void {
    this.accessToken = undefined;
    this.expiresAt = 0;
    clearTimeout(this.expiryTimer);
    this.state = state;
    this.changed();
  }

  private stopPending(): void {
    if (this.pending) {
      clearTimeout(this.pending.timer);
      this.pending.server.close();
      this.pending.server.closeIdleConnections();
      this.pending = undefined;
    }
  }

  disconnect(): void {
    this.generation++;
    this.abort?.abort();
    this.stopPending();
    this.starting = undefined;
    this.granted = [];
    this.required = [];
    this.invalidate();
  }

  async connect(): Promise<Record<string, unknown>> {
    if (this.pending) return { ...this.status(), authorization_url: this.pending.url };
    if (this.token() && !this.required.length) return this.status();
    if (!this.starting) {
      const starting = this.begin();
      this.starting = starting;
      void starting.finally(() => { if (this.starting === starting) this.starting = undefined; }).catch(() => undefined);
    }
    return this.starting;
  }

  private async oauthFetch(input: string | URL | Request, init?: RequestInit): Promise<Response> {
    const url = input instanceof Request ? input.url : String(input);
    const method = init?.method || 'GET';
    const metadata = this.config.url.origin + '/.well-known/oauth-authorization-server/oauth2/mcp';
    if (!((method === 'GET' && [this.resourceMetadataUrl, metadata].includes(url)) || (method === 'POST' && url === this.issuer + '/token'))) {
      throw new Error('OAuth destination is outside the configured koinon contract.');
    }
    const headers = new Headers(init?.headers);
    if (headers.has('authorization') || headers.has('cookie')) throw new Error('OAuth discovery and public token exchange cannot carry credentials in headers.');
    const signals = [AbortSignal.timeout(10_000), ...(this.abort ? [this.abort.signal] : [])];
    if (init?.signal) signals.push(init.signal);
    const response = await this.fetchImpl(url, { ...init, method, headers, credentials: 'omit', redirect: 'error', signal: AbortSignal.any(signals) });
    return boundedJson(response);
  }

  private async begin(): Promise<Record<string, unknown>> {
    const generation = ++this.generation;
    this.abort = new AbortController();
    this.invalidate('connecting');
    let listener: HttpServer | undefined;
    try {
      const resource = OAuthProtectedResourceMetadataSchema.parse(await (await this.oauthFetch(this.resourceMetadataUrl)).json());
      if (resource.resource !== this.config.url.href || resource.authorization_servers?.length !== 1 || resource.authorization_servers[0] !== this.issuer) throw new Error('Resource metadata is not bound to this koinon endpoint.');
      const metadata = OAuthMetadataSchema.parse(await (await this.oauthFetch(this.config.url.origin + '/.well-known/oauth-authorization-server/oauth2/mcp')).json());
      if (metadata.issuer !== this.issuer || metadata.authorization_endpoint !== this.issuer + '/authorize' || metadata.token_endpoint !== this.issuer + '/token'
          || !metadata.code_challenge_methods_supported?.includes('S256') || !metadata.response_types_supported.includes('code')
          || !metadata.grant_types_supported?.includes('authorization_code') || !metadata.token_endpoint_auth_methods_supported?.includes('none')) throw new Error('OAuth metadata does not support the registered public client contract.');
      const requested = [...new Set(['catalog:read', ...this.granted, ...this.required])].sort();
      const state = randomBytes(32).toString('base64url');
      const authorization = await startAuthorization(this.issuer, { metadata, clientInformation: { client_id: this.config.clientId },
        redirectUrl: this.config.redirectUrl, scope: requested.join(' '), state, resource: this.config.url.href });
      if (generation !== this.generation) throw new Error('Connection cancelled.');
      listener = createServer({ maxHeaderSize: 8192, headersTimeout: 5000, requestTimeout: 5000 }, (req, res) => {
        res.setHeader('Cache-Control', 'no-store');
        res.setHeader('Content-Security-Policy', "default-src 'none'; frame-ancestors 'none'");
        res.setHeader('Referrer-Policy', 'no-referrer');
        res.setHeader('Content-Type', 'text/plain; charset=utf-8');
        res.setHeader('Connection', 'close');
        const pending = this.pending;
        let url: URL;
        try { url = new URL(req.url || '', this.config.redirectUrl); } catch { res.writeHead(400).end('Invalid callback.'); return; }
        const stateValue = url.searchParams.get('state') || '';
        const equalState = pending && /^[A-Za-z0-9_-]{43}$/.test(stateValue) && timingSafeEqual(Buffer.from(stateValue), Buffer.from(pending.state));
        if (!pending || this.state !== 'awaiting_authorization' || Date.now() >= pending.expires || req.method !== 'GET' || req.headers.host !== this.config.redirectUrl.host || req.headers.origin
            || url.origin !== this.config.redirectUrl.origin || url.pathname !== this.config.redirectUrl.pathname || (req.url?.length || 0) > 8192
            || [...url.searchParams.keys()].some((key) => !['state', 'iss', 'code', 'error', 'error_description'].includes(key) || url.searchParams.getAll(key).length !== 1)
            || !equalState || url.searchParams.get('iss') !== this.issuer || Boolean(url.searchParams.get('code')) === Boolean(url.searchParams.get('error'))) {
          res.writeHead(400).end('Invalid or expired callback.'); return;
        }
        if (url.searchParams.has('error')) {
          this.stopPending(); this.invalidate('denied'); res.writeHead(200).end('Authorization was cancelled. Return to your assistant to connect again.'); return;
        }
        const code = url.searchParams.get('code')!;
        if (!/^[A-Za-z0-9._~-]{1,1024}$/.test(code)) { res.writeHead(400).end('Invalid authorization code.'); return; }
        this.state = 'exchanging';
        void (async () => {
          try {
            const tokens = await exchangeAuthorization(this.issuer, { metadata: pending.metadata, clientInformation: { client_id: this.config.clientId },
              authorizationCode: code, codeVerifier: pending.verifier, redirectUri: this.config.redirectUrl, resource: this.config.url.href,
              fetchFn: (input, init) => this.oauthFetch(input, init) });
            const granted = scopes(tokens.scope || pending.scopes.join(' '));
            if (pending.generation !== this.generation || Date.now() >= pending.expires) throw new Error('Authorization expired or was cancelled.');
            if (tokens.token_type.toLowerCase() !== 'bearer' || !tokens.access_token || tokens.access_token.length > 8192 || /[\s\x00-\x1f\x7f]/.test(tokens.access_token)
                || !Number.isSafeInteger(tokens.expires_in) || !tokens.expires_in || tokens.expires_in < 1 || tokens.expires_in > 86400
                || granted.some((v) => !pending.scopes.includes(v)) || !granted.includes('catalog:read') || tokens.refresh_token) throw new Error('Unexpected token contract.');
            this.accessToken = tokens.access_token;
            this.expiresAt = Date.now() + tokens.expires_in * 1000;
            this.granted = granted;
            this.required = [];
            this.state = 'connected';
            this.expiryTimer = setTimeout(() => this.invalidate('expired'), tokens.expires_in * 1000).unref();
            this.stopPending(); this.changed();
            res.writeHead(200).end('Connected to koinon. Return to your assistant. This connection lasts for this desktop session only.');
          } catch {
            if (pending.generation === this.generation) { this.stopPending(); this.invalidate('error'); }
            res.writeHead(400).end('Authorization could not complete. Return to your assistant and connect again.');
          }
        })();
      });
      listener.maxHeadersCount = 20;
      await new Promise<void>((resolve, reject) => {
        listener!.once('error', reject);
        listener!.listen(Number(this.config.redirectUrl.port), '127.0.0.1', () => { listener!.removeListener('error', reject); resolve(); });
      });
      if (generation !== this.generation) throw new Error('Connection cancelled.');
      const timer = setTimeout(() => { this.generation++; this.abort?.abort(); this.stopPending(); this.invalidate('expired'); }, AUTHORIZATION_TTL).unref();
      this.pending = { server: listener, timer, state, verifier: authorization.codeVerifier, url: authorization.authorizationUrl.href, scopes: requested, metadata, generation, expires: Date.now() + AUTHORIZATION_TTL };
      this.state = 'awaiting_authorization';
      return { ...this.status(), authorization_url: authorization.authorizationUrl.href };
    } catch {
      listener?.close();
      if (generation === this.generation) this.invalidate('error');
      throw new Error('Unable to start OAuth. Check the public client registration, metadata, and availability of the configured callback port.');
    }
  }

  requireScopes(challenges: unknown): boolean {
    if (!this.token() || !Array.isArray(challenges) || challenges.length !== 1 || typeof challenges[0] !== 'string' || challenges[0].length > 2048) return false;
    // Accept only the bounded, quoted Bearer challenge emitted before koinon executes an operation.
    const header: string = challenges[0];
    if (!header.startsWith('Bearer ')) return false;
    const fields = new Map<string, string>();
    let remainder = header.slice(7);
    while (remainder) {
      const match = /^([a-z_]+)="([^"\\\r\n]*)"(?:, |$)/.exec(remainder);
      if (!match || fields.has(match[1])) return false;
      fields.set(match[1], match[2]); remainder = remainder.slice(match[0].length);
    }
    if (fields.get('resource_metadata') !== this.resourceMetadataUrl || fields.get('error') !== 'insufficient_scope' || [...fields.keys()].some((key) => !['resource_metadata', 'error', 'error_description', 'scope'].includes(key))) return false;
    try {
      const requested = scopes(fields.get('scope') || '');
      if (requested.every((v) => this.granted.includes(v))) return false;
      this.required = [...new Set([...this.granted, ...requested])].sort();
      return true;
    } catch { return false; }
  }
}
