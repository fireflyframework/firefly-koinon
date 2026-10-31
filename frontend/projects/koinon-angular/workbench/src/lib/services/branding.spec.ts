// Copyright 2026 Firefly Software Foundation
// SPDX-License-Identifier: Apache-2.0
import { DEFAULT_BRANDING, brandStyles, brandImage, validateBranding } from './branding-values';
it('resolves accessible defaults and encodes only scoped palette variables', () => {
  expect(validateBranding(DEFAULT_BRANDING)).toEqual([]);
  const style = brandStyles(DEFAULT_BRANDING, 'dark');
  expect(style['--koinon-brand-action']).toBe('#ffb34a');
  expect(style['--koinon-brand-text']).toBe('#f3f1eb');
  expect(Object.keys(style).every((key) => key.startsWith('--koinon-brand-'))).toBe(true);
});
it('rejects low contrast, CSS injection, and executable logo input', () => {
  const value = structuredClone(DEFAULT_BRANDING);
  value.palette.light.text = '#ffffff';
  value.palette.dark.action = 'red;background:url(https://example.invalid)';
  value.logo_light = 'data:image/svg+xml,<svg onload="alert(1)"/>';
  expect(validateBranding(value).length).toBeGreaterThanOrEqual(3);
});
it('uses a text identity rather than the original logo when renamed', () => {
  const value = { ...DEFAULT_BRANDING, product_name: 'Acme Knowledge' };
  expect(brandImage(value, 'light', '/assets/brand')).toBe('');
  expect(brandImage(DEFAULT_BRANDING, 'dark', '/assets/brand')).toContain('reversed.svg');
});

import { TestBed } from '@angular/core/testing';
import { KoinonBranding } from './branding';
import {
  KoinonClient,
  type HttpMethod,
  type KoinonTransport,
  type OrganizationBranding,
} from '@fireflyframework/koinon-sdk';
import { KoinonFacade } from '../koinon-facade';
import { provideKoinonClient } from '../client-provider';
it('drops a prior organization response after selection changes without styling the host document', async () => {
  let finish: ((value: OrganizationBranding) => void) | undefined;
  const transport: KoinonTransport = {
    request: async <T>(_method: HttpMethod, path: string) => {
      if (path.includes('first'))
        return (await new Promise<OrganizationBranding>((resolve) => (finish = resolve))) as T;
      return {
        tenant_id: 'second',
        schema_version: 1,
        revision: 2,
        origin: 'organization',
        branding: { ...DEFAULT_BRANDING, product_name: 'Second library' },
      } as T;
    },
    stream: () => {
      throw new Error('Unexpected stream');
    },
  };
  TestBed.configureTestingModule({
    providers: [
      KoinonBranding,
      KoinonFacade,
      ...provideKoinonClient(new KoinonClient({ transport }), transport),
    ],
  });
  const facade = TestBed.inject(KoinonFacade),
    brand = TestBed.inject(KoinonBranding);
  const title = document.title,
    styles = document.documentElement.getAttribute('style');
  facade.context.set({ subject: 'issuer|member', tenants: [], memberships: [], workspaces: [] });
  facade.tenantId.set('first');
  TestBed.tick();
  await Promise.resolve();
  facade.tenantId.set('second');
  TestBed.tick();
  await Promise.resolve();
  await Promise.resolve();
  finish?.({
    tenant_id: 'first',
    schema_version: 1,
    revision: 1,
    origin: 'organization',
    branding: { ...DEFAULT_BRANDING, product_name: 'First library' },
  });
  await Promise.resolve();
  await Promise.resolve();
  expect(brand.value().product_name).toBe('Second library');
  expect(document.title).toBe(title);
  expect(document.documentElement.getAttribute('style')).toBe(styles);
  facade.authRequired.set(true);
  TestBed.tick();
  expect(brand.value().product_name).toBe('koinon');
});
it('keeps a saved identity when an older organization read finishes afterward', async () => {
  let finish: ((value: OrganizationBranding) => void) | undefined;
  const transport: KoinonTransport = {
    request: async <T>() =>
      (await new Promise<OrganizationBranding>((resolve) => (finish = resolve))) as T,
    stream: () => {
      throw new Error('Unexpected stream');
    },
  };
  TestBed.configureTestingModule({
    providers: [
      KoinonBranding,
      KoinonFacade,
      ...provideKoinonClient(new KoinonClient({ transport }), transport),
    ],
  });
  const f = TestBed.inject(KoinonFacade),
    brand = TestBed.inject(KoinonBranding);
  f.context.set({ subject: 'issuer|admin', tenants: [], memberships: [], workspaces: [] });
  f.tenantId.set('tenant');
  TestBed.tick();
  await Promise.resolve();
  brand.accept({
    tenant_id: 'tenant',
    schema_version: 1,
    revision: 5,
    origin: 'organization',
    branding: { ...DEFAULT_BRANDING, product_name: 'Saved identity' },
  });
  finish?.({
    tenant_id: 'tenant',
    schema_version: 1,
    revision: 4,
    origin: 'organization',
    branding: { ...DEFAULT_BRANDING, product_name: 'Old identity' },
  });
  await Promise.resolve();
  await Promise.resolve();
  expect(brand.value().product_name).toBe('Saved identity');
});
it('clears organization identity when the authenticated subject changes on the same client', async () => {
  let finish: ((value: OrganizationBranding) => void) | undefined;
  const transport: KoinonTransport = {
    request: async <T>() =>
      (await new Promise<OrganizationBranding>((resolve) => (finish = resolve))) as T,
    stream: () => {
      throw new Error('Unexpected stream');
    },
  };
  TestBed.configureTestingModule({
    providers: [
      KoinonBranding,
      KoinonFacade,
      ...provideKoinonClient(new KoinonClient({ transport }), transport),
    ],
  });
  const f = TestBed.inject(KoinonFacade),
    brand = TestBed.inject(KoinonBranding);
  f.context.set({ subject: 'issuer|first', tenants: [], memberships: [], workspaces: [] });
  f.tenantId.set('tenant');
  TestBed.tick();
  await Promise.resolve();
  const first = finish;
  f.context.set({ ...f.context()!, subject: 'issuer|second' });
  TestBed.tick();
  await Promise.resolve();
  first?.({
    tenant_id: 'tenant',
    schema_version: 1,
    revision: 4,
    origin: 'organization',
    branding: { ...DEFAULT_BRANDING, product_name: 'Previous session' },
  });
  await Promise.resolve();
  await Promise.resolve();
  expect(brand.value().product_name).toBe('koinon');
  finish?.({
    tenant_id: 'tenant',
    schema_version: 1,
    revision: 4,
    origin: 'organization',
    branding: { ...DEFAULT_BRANDING, product_name: 'Current session' },
  });
  await Promise.resolve();
  await Promise.resolve();
  expect(brand.value().product_name).toBe('Current session');
});
