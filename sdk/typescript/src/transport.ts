// Copyright 2026 Firefly Software Foundation
// SPDX-License-Identifier: Apache-2.0
export type HttpMethod = 'GET' | 'POST' | 'PUT' | 'PATCH' | 'DELETE';
export interface RequestOptions {
 body?: unknown;
 responseType?: 'json' | 'blob' | 'download';
 query?: Record<string, string | number | boolean | undefined>;
 signal?: AbortSignal | undefined;
 headers?: Record<string, string>;
}
export interface StreamEvent<T = unknown> { id: string; type: string; data: T }
export interface BinaryDownload {blob:Blob;content_type:string|null;etag:string|null;filename:string|null;not_modified:boolean}
export interface KoinonTransport {
 request<T>(method: HttpMethod, path: string, options?: RequestOptions): Promise<T>;
 stream<T = unknown>(method: HttpMethod, path: string, options?: RequestOptions): AsyncIterable<StreamEvent<T>>;
}
export interface FetchTransportOptions {
 baseUrl: string;
 accessToken?: () => string | null | Promise<string | null>;
 csrfToken?: () => string | null | Promise<string | null>;
 credentials?: RequestCredentials;
 fetch?: typeof globalThis.fetch;
}
export class KoinonError extends Error {
 constructor(public readonly status: number, public readonly code: string, message: string,
  public readonly requestId?: string, public readonly problem?: unknown) {
  super(message); this.name = 'KoinonError';
 }
}
export class FetchTransport implements KoinonTransport {
 private readonly baseUrl: string;
 private readonly fetcher: typeof globalThis.fetch;
 constructor(private readonly options: FetchTransportOptions) {
  this.baseUrl = options.baseUrl.replace(/\/$/, '');
  this.fetcher = options.fetch ?? globalThis.fetch.bind(globalThis);
 }
 private async send(method: HttpMethod, path: string, options: RequestOptions, accept: string): Promise<Response> {
  if (!path.startsWith('/') || path.startsWith('//') || path.includes('://')) {
   throw new Error('SDK paths must be relative to the configured API');
  }
  const query = new URLSearchParams();
  for (const [key, value] of Object.entries(options.query ?? {})) {
   if (value !== undefined) query.set(key, String(value));
  }
  const headers = new Headers(options.headers);
  headers.set('Accept', accept);
  const token = await this.options.accessToken?.();
  if (token) headers.set('Authorization', `Bearer ${token}`);
  else if (method !== 'GET') {
   const csrf = await this.options.csrfToken?.();
   if (csrf) headers.set('X-XSRF-TOKEN', csrf);
  }
  let body: BodyInit | undefined;
  if (options.body !== undefined) {
   if (options.body instanceof FormData || options.body instanceof Blob) body = options.body;
   else { headers.set('Content-Type', 'application/json'); body = JSON.stringify(options.body); }
  }
  const init: RequestInit = {method, headers, redirect: 'error', credentials: this.options.credentials ?? 'include'};
  if (body !== undefined) init.body = body;
  if (options.signal) init.signal = options.signal;
  const response = await this.fetcher(`${this.baseUrl}${path}${query.size ? '?' + query : ''}`, init);
  if (!response.ok && !(response.status === 304 && options.responseType === 'download')) {
   const payload: unknown = await response.json().catch(() => undefined);
   const envelope = payload && typeof payload === 'object' ? payload as Record<string, unknown> : {};
   const p = envelope['error'] && typeof envelope['error'] === 'object' ? envelope['error'] as Record<string,unknown> : envelope;
   const reference = p['request_id'] ?? p['transactionId'] ?? p['transaction_id'];
   throw new KoinonError(response.status, String(p['code'] ?? 'HTTP_ERROR'),
    String(p['detail'] ?? p['message'] ?? p['title'] ?? `Request failed (${response.status})`),
    typeof reference === 'string' ? reference : response.headers.get('X-Request-Id') ?? response.headers.get('X-Transaction-Id') ?? undefined, payload);
  }
  return response;
 }
 async request<T>(method: HttpMethod, path: string, options: RequestOptions = {}): Promise<T> {
  const response = await this.send(method, path, options, 'application/json');
  if (response.status === 204) return undefined as T;
  if (options.responseType === 'download') {
   const disposition=response.headers.get('Content-Disposition') ?? '';
   const encoded=/filename\*=UTF-8''([^;]+)/i.exec(disposition)?.[1];
   let filename:string|null=null;
   if(encoded){try{filename=decodeURIComponent(encoded);}catch{filename=encoded;}}
   else {const plain=/(?:^|;)\s*filename\s*=\s*(?:"((?:\\.|[^"\\])*)"|([^;\s]+))/i.exec(disposition);filename=plain?.[1]?.replace(/\\(.)/g,'$1')??plain?.[2]??null;}
   return {blob:await response.blob(),content_type:response.headers.get('Content-Type'),etag:response.headers.get('ETag'),filename,not_modified:response.status===304} as T;
  }
  if (options.responseType === 'blob') return await response.blob() as T;
  const text = await response.text();
  return (text ? JSON.parse(text) : undefined) as T;
 }
 async *stream<T = unknown>(method: HttpMethod, path: string, options: RequestOptions = {}): AsyncIterable<StreamEvent<T>> {
  const response = await this.send(method, path, options, 'text/event-stream');
  if (response.headers.get('Content-Type')?.split(';')[0]?.trim() !== 'text/event-stream' || !response.body) {
   throw new Error('Expected a text/event-stream response');
  }
  const reader = response.body.getReader();
  const decoder = new TextDecoder();
  const encoder = new TextEncoder();
  let buffer = '', eventType = 'message', eventId = '', data: string[] = [], frameBytes = 0;
  const consume = (line: string): StreamEvent<T> | undefined => {
   frameBytes += encoder.encode(line).byteLength;
   if (frameBytes > 1_048_576) throw new Error('Event stream frame exceeds 1 MiB');
   if (line === '') {
    const event = data.length ? {id: eventId, type: eventType, data: JSON.parse(data.join('\n')) as T} : undefined;
    data = []; eventType = 'message'; frameBytes = 0;
    return event;
   }
   if (line.startsWith(':')) return;
   const separator = line.indexOf(':');
   const field = separator < 0 ? line : line.slice(0, separator);
   const raw = separator < 0 ? '' : line.slice(separator + 1);
   const value = raw.startsWith(' ') ? raw.slice(1) : raw;
   if (field === 'data') data.push(value);
   if (field === 'event') eventType = value || 'message';
   if (field === 'id' && !value.includes('\0')) eventId = value;
  };
  try {
   for (;;) {
    const next = await reader.read();
    buffer += decoder.decode(next.value, {stream: !next.done});
    let match: RegExpExecArray | null;
    while ((match = /\r\n|\n|\r/.exec(buffer)) !== null) {
     if (!next.done && match[0] === '\r' && match.index === buffer.length - 1) break;
     const line = buffer.slice(0, match.index);
     buffer = buffer.slice(match.index + match[0].length);
     const event = consume(line);
     if (event) yield event;
    }
    if (encoder.encode(buffer).byteLength + frameBytes > 1_048_576) throw new Error('Event stream frame exceeds 1 MiB');
    if (next.done) break;
   }
  } finally { await reader.cancel().catch(() => undefined); reader.releaseLock(); }
 }
}
