// Copyright 2026 Firefly Software Foundation
// SPDX-License-Identifier: Apache-2.0
import { TestBed } from '@angular/core/testing';
import {
  KoinonClient,
  KoinonError,
  type HttpMethod,
  type RequestOptions,
  type KoinonTransport,
  type OrganizationBranding,
} from '@fireflyframework/koinon-sdk';
import { KoinonFacade, provideKoinonClient } from '@fireflyframework/koinon-angular';
import { KoinonBranding } from '@fireflyframework/koinon-angular/workbench';
import { DEFAULT_BRANDING } from './branding-values';
import { KoinonIdentityAppearance } from '../../../../settings/src/identity-appearance';
async function mount(conflict = false) {
  const writes: { method: string; path: string; body: unknown }[] = [];
  const original: OrganizationBranding = {
    tenant_id: 'tenant',
    schema_version: 1,
    revision: 4,
    origin: 'organization',
    branding: { ...DEFAULT_BRANDING, product_name: 'Team Library' },
  };
  const transport: KoinonTransport = {
    request: async <T>(method: HttpMethod, path: string, options?: RequestOptions) => {
      if (path.endsWith('/branding/defaults')) return DEFAULT_BRANDING as T;
      if (method !== 'GET') {
        writes.push({ method, path, body: options?.body });
        if (conflict) throw new KoinonError(409, 'ORGANIZATION_BRANDING_CHANGED', 'Changed');
        const body = options?.body as { branding?: typeof DEFAULT_BRANDING };
        return {
          ...original,
          revision: 5,
          origin: method === 'POST' ? 'deployment' : 'organization',
          branding: body.branding ?? DEFAULT_BRANDING,
        } as T;
      }
      return {
        ...original,
        branding: {
          product_name: original.branding.product_name,
          assistant_name: 'koinon',
          logo_light: null,
          logo_dark: null,
          symbol: null,
          favicon: null,
          palette: DEFAULT_BRANDING.palette,
          font_family: 'Manrope',
        },
      } as T;
    },
    stream: () => {
      throw new Error('Unexpected stream');
    },
  };
  TestBed.configureTestingModule({
    imports: [KoinonIdentityAppearance],
    providers: [
      KoinonBranding,
      KoinonFacade,
      ...provideKoinonClient(new KoinonClient({ transport }), transport),
    ],
  });
  const f = TestBed.inject(KoinonFacade);
  f.tenantId.set('tenant');
  f.context.set({
    subject: 'issuer|admin',
    tenants: [{ id: 'tenant', name: 'Team', roles: ['admin'], permissions: ['settings:write'] }],
    memberships: [],
    workspaces: [],
  });
  const fixture = TestBed.createComponent(KoinonIdentityAppearance);
  fixture.detectChanges();
  await fixture.whenStable();
  fixture.detectChanges();
  return {
    fixture,
    component: fixture.componentInstance,
    writes,
    brand: TestBed.inject(KoinonBranding),
    transport,
    facade: f,
  };
}
it('previews locally and saves exact revision before applying the organization identity', async () => {
  const { component, writes, brand } = await mount();
  component.name('product_name', 'Acme Library');
  expect(brand.value().product_name).toBe('Team Library');
  await component.save();
  expect(writes[0].body).toMatchObject({
    expected_revision: 4,
    branding: { product_name: 'Acme Library' },
  });
  expect(brand.value().product_name).toBe('Acme Library');
});
it('offers a bundled Inter typeface and saves it only after explicit confirmation', async () => {
  const { component, fixture, writes, brand } = await mount();
  const select = fixture.nativeElement.querySelector(
    'select[name="font-family"]',
  ) as HTMLSelectElement;
  expect(select).not.toBeNull();
  select.value = 'Inter';
  select.dispatchEvent(new Event('change'));
  fixture.detectChanges();
  expect(component.draft().font_family).toBe('Inter');
  expect(brand.value().font_family).toBe('Manrope');
  await component.save();
  expect(writes[0].body).toMatchObject({
    expected_revision: 4,
    branding: { font_family: 'Inter' },
  });
  expect(brand.value().font_family).toBe('Inter');
});
it('requires a save to restore deployment inheritance and keeps CAS conflicts visible', async () => {
  const { component, writes } = await mount(true);
  component.restore();
  expect(writes).toHaveLength(0);
  expect(component.canSave()).toBe(true);
  await component.save();
  expect(writes[0].method).toBe('POST');
  expect(component.stale()).toBe(true);
  expect(component.canSave()).toBe(false);
  expect(component.error()).toContain('Reload');
});
it('blocks an inaccessible palette and exposes identity in organization settings navigation', async () => {
  const { component, fixture, writes } = await mount();
  component.color('text', '#ffffff');
  fixture.detectChanges();
  await component.save();
  expect(writes).toHaveLength(0);
  expect(component.canSave()).toBe(false);
  expect(fixture.nativeElement.querySelector('[role=alert]').textContent).toContain('4.5:1');
});
it('does not reapply an image after the edit was discarded', async () => {
  const { component } = await mount();
  let complete: (() => void) | undefined;
  const reader = vi.spyOn(FileReader.prototype, 'readAsDataURL').mockImplementation(function (
    this: FileReader,
  ) {
    complete = () => {
      Object.defineProperty(this, 'result', {
        value: 'data:image/png;base64,iVBORw0KGgo=',
        configurable: true,
      });
      this.onload?.(new ProgressEvent('load') as ProgressEvent<FileReader>);
    };
  });
  const upload = component.upload('logo_light', {
    target: { files: [new File(['image'], 'logo.png', { type: 'image/png' })], value: '' },
  } as unknown as Event);
  expect(component.uploading()).toBe(1);
  expect(component.canSave()).toBe(false);
  component.discard();
  complete?.();
  await upload;
  expect(component.draft().logo_light).toBeNull();
  expect(component.uploading()).toBe(0);
  reader.mockRestore();
});
it('unlocks the editor after changing organization while a save is pending', async () => {
  const { component, fixture, transport, facade } = await mount();
  let finish: ((value: unknown) => void) | undefined;
  const original = transport.request;
  transport.request = async <T>(method: HttpMethod, path: string, options?: RequestOptions) =>
    method === 'PUT'
      ? ((await new Promise<unknown>((resolve) => (finish = resolve))) as T)
      : await original<T>(method, path, options);
  component.name('product_name', 'New identity');
  const save = component.save();
  expect(component.saving()).toBe(true);
  const context = facade.context()!;
  facade.context.set({
    ...context,
    tenants: [
      ...context.tenants,
      { id: 'other', name: 'Other', roles: ['admin'], permissions: ['settings:write'] },
    ],
  });
  facade.tenantId.set('other');
  fixture.detectChanges();
  await Promise.resolve();
  expect(component.saving()).toBe(false);
  finish?.({
    tenant_id: 'tenant',
    schema_version: 1,
    revision: 5,
    origin: 'organization',
    branding: { ...DEFAULT_BRANDING, product_name: 'Old tenant save' },
  });
  await save;
  expect(component.saving()).toBe(false);
  expect(component.draft().product_name).not.toBe('Old tenant save');
});

it('treats the saved identity as unchanged regardless of response property order', async () => {
  const { component } = await mount();
  expect(component.changed()).toBe(false);
  expect(component.canSave()).toBe(false);
});
it('applies an accessible brand color to both themes without saving implicitly', async () => {
  const { component, writes } = await mount();
  component.brandColor.set('#2563eb');
  component.applyColor();
  expect(writes).toHaveLength(0);
  expect(component.draft().palette.dark.action).toBe('#2563eb');
  expect(component.problems()).toEqual([]);
  expect(component.canSave()).toBe(true);
});
