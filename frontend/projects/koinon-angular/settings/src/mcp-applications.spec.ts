// Copyright 2026 Firefly Software Foundation
// SPDX-License-Identifier: Apache-2.0
import { TestBed } from '@angular/core/testing';
import {
  KoinonClient,
  type KoinonTransport,
  type HttpMethod,
  type RequestOptions,
} from '@fireflyframework/koinon-sdk';
import { KoinonFacade, KoinonI18n, provideKoinonClient } from '@fireflyframework/koinon-angular';
import { registerKoinonSpanish } from '@fireflyframework/koinon-angular/workbench';
import { SPANISH } from '../../src/lib/foundations/spanish';
import { MCP_APPLICATIONS_SPANISH } from './mcp-applications-spanish';
import { KoinonMcpApplications, callbackIssue, applicationScopes } from './mcp-applications';
import { KoinonMcpApplicationsState } from './mcp-applications-state';

describe('OAuth application setup', () => {
  it('preserves the public translation vocabulary in either lazy registration order', () => {
    const i18n = TestBed.inject(KoinonI18n);
    i18n.apply({ locale: 'es-ES', time_zone: 'UTC', response_language: 'es' });
    for (const dictionaries of [
      [SPANISH, MCP_APPLICATIONS_SPANISH],
      [MCP_APPLICATIONS_SPANISH, SPANISH],
    ]) {
      for (const dictionary of dictionaries) registerKoinonSpanish(dictionary);
      for (const [key, translation] of Object.entries(SPANISH))
        expect(i18n.text(key)).toBe(translation);
    }
  });
  it('accepts exact HTTPS and loopback callbacks and rejects ambiguous callback lists', () => {
    expect(
      callbackIssue('https://desktop.example.test/callback\nhttp://127.0.0.1:4312/callback'),
    ).toBe('');
    for (const value of [
      'https://example.test/*',
      'https:desktop.example.test/callback',
      'https:///desktop.example.test/callback',
      'https://u:p@example.test/callback',
      'https://example.test/callback#fragment',
      'http://example.test/callback',
      'https://example.test/callback\nhttps://example.test/callback',
      '',
    ])
      expect(callbackIssue(value)).not.toBe('');
  });
  it('keeps scope dependencies consistent when upload access is selected or removed', () => {
    expect(applicationScopes(['catalog:read'], 'ingest:write', true)).toEqual([
      'catalog:read',
      'catalog:write',
      'ingest:write',
    ]);
    expect(
      applicationScopes(['catalog:read', 'catalog:write', 'ingest:write'], 'catalog:write', false),
    ).toEqual(['catalog:read']);
    expect(applicationScopes(['catalog:read'], 'catalog:read', false)).toEqual(['catalog:read']);
  });
  it('requires explicit review for creation and leaves an uncertain submission closed until reload', async () => {
    const requests: { method: string; body: unknown }[] = [];
    let uncertain = false;
    const transport: KoinonTransport = {
      request: async <T>(method: HttpMethod, path: string, options?: RequestOptions) => {
        requests.push({ method, body: options?.body });
        if (method === 'POST' && uncertain) throw new TypeError('Synthetic lost response');
        return (
          path.endsWith('/readiness')
            ? {
                ready: true,
                endpoint_enabled: true,
                oauth_enabled: true,
                encryption_configured: true,
                missing_configuration: [],
                static_clients_read_only: true,
              }
            : method === 'POST'
              ? {
                  client: {
                    id: 'registration-one',
                    client_id: 'koinon_org_one',
                    tenant_id: 'tenant-one',
                    name: 'Research desktop',
                    client_type: 'public',
                    enabled: true,
                    revision: 1,
                    scopes: ['catalog:read'],
                    redirect_uris: ['https://desktop.example.test/callback'],
                    created_at: '2026-10-29T00:00:00Z',
                    updated_at: '2026-10-29T00:00:00Z',
                    created_by: 'issuer|admin',
                    updated_by: 'issuer|admin',
                  },
                  client_secret: null,
                }
              : { items: [], page: 1, page_size: 25, total: 0, pages: 0 }
        ) as T;
      },
      stream: () => {
        throw new Error('Unexpected stream');
      },
    };
    TestBed.configureTestingModule({
      imports: [KoinonMcpApplications],
      providers: [KoinonFacade, ...provideKoinonClient(new KoinonClient({ transport }), transport)],
    });
    const facade = TestBed.inject(KoinonFacade);
    facade.context.set({
      subject: 'issuer|admin',
      tenants: [
        { id: 'tenant-one', name: 'Research', roles: ['admin'], permissions: ['identity:manage'] },
      ],
      memberships: [],
      workspaces: [],
    });
    facade.tenantId.set('tenant-one');
    const fixture = TestBed.createComponent(KoinonMcpApplications),
      component = fixture.componentInstance;
    fixture.detectChanges();
    await fixture.whenStable();
    component.beginCreate();
    component.name.set('Research desktop');
    component.callbacks.set('https://desktop.example.test/callback');
    await component.save();
    expect(requests.filter((request) => request.method === 'POST')).toHaveLength(0);
    component.next();
    component.next();
    expect(component.step()).toBe(3);
    await component.save();
    expect(requests.filter((request) => request.method === 'POST')).toHaveLength(0);
    component.acknowledged.set(true);
    await component.save();
    expect(requests.filter((request) => request.method === 'POST')).toHaveLength(1);
    expect(component.editor()).toBeNull();
    expect(fixture.debugElement.injector.get(KoinonMcpApplicationsState).secret()).toBeNull();
    uncertain = true;
    component.beginCreate();
    component.name.set('Another application');
    component.callbacks.set('https://desktop.example.test/another-callback');
    component.next();
    component.next();
    component.acknowledged.set(true);
    await component.save();
    expect(component.state.stale()).toBe(true);
    expect(component.editor()).toBeNull();
    expect(requests.filter((request) => request.method === 'POST')).toHaveLength(2);
  });
});
