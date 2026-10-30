// Copyright 2026 Firefly Software Foundation SPDX-License-Identifier: Apache-2.0
import { TestBed, DeferBlockState } from '@angular/core/testing';
import {
  KoinonClient,
  type KoinonTransport,
  type HttpMethod,
  type RequestOptions,
} from '@fireflyframework/koinon-sdk';
import { KoinonFacade } from '../koinon-facade';
import { provideKoinonClient } from '../client-provider';
import { KoinonI18n } from '../foundations/i18n';
import { KoinonOrganizationInformation } from './organization-information';
async function mount(shared = false, locale = 'en-US') {
  const calls: { path: string; options: RequestOptions | undefined }[] = [];
  const transport: KoinonTransport = {
    request: async <T>(_method: HttpMethod, path: string, options?: RequestOptions) => {
      calls.push({ path, options });
      return (
        path.endsWith('/me')
          ? {
              id: 'person1',
              display_name: 'Alex',
              job_title: 'Engineer',
              source: 'manual',
              revision: 1,
            }
          : path.endsWith('directory-settings')
            ? {
                tenant_id: 'north',
                visibility: shared ? 'shared_workspaces' : 'administrators',
                revision: 1,
              }
            : { items: [], page: 1, page_size: 25, total: 0, pages: 0 }
      ) as T;
    },
    stream: () => {
      throw new Error('Unexpected stream');
    },
  };
  TestBed.configureTestingModule({
    providers: [KoinonFacade, ...provideKoinonClient(new KoinonClient({ transport }), transport)],
  });
  const facade = TestBed.inject(KoinonFacade);
  facade.tenantId.set('north');
  facade.workspaceId.set('workspace1');
  facade.context.set({
    subject: 'alex',
    tenants: [{ id: 'north', name: 'North', roles: ['viewer'], permissions: ['catalog:read'] }],
    memberships: [],
    workspaces: [],
    workspace_permissions: {},
  });
  TestBed.inject(KoinonI18n).apply({ locale, time_zone: 'UTC', response_language: 'auto' });
  const fixture = TestBed.createComponent(KoinonOrganizationInformation);
  fixture.detectChanges();
  await fixture.whenStable();
  fixture.detectChanges();
  return { fixture, calls };
}
describe('read-only account organization information', () => {
  it('shows personal organization metadata without requesting a private colleague directory', async () => {
    const { fixture, calls } = await mount();
    expect(fixture.nativeElement.textContent).toContain('Engineer');
    expect(fixture.nativeElement.textContent).toContain('Not provided');
    expect(fixture.nativeElement.querySelector('input,select')).toBeNull();
    expect(calls.some((call) => call.path.endsWith('/organization/people'))).toBe(false);
    expect(fixture.componentInstance.canBrowse()).toBe(false);
  });
  it('opens the shared directory with a workspace bound and readable Spanish labels', async () => {
    const { fixture, calls } = await mount(true, 'es-ES');
    expect(fixture.nativeElement.textContent).toContain('Tu información en la organización');
    fixture.componentInstance.browsing.set(true);
    fixture.detectChanges();
    for (const block of await fixture.getDeferBlocks())
      await block.render(DeferBlockState.Complete);
    await fixture.whenStable();
    const request = calls.find((call) => call.path.endsWith('/organization/people'));
    expect(request?.options?.query).toMatchObject({
      workspace_id: 'workspace1',
      page: 1,
      page_size: 25,
    });
    expect(fixture.nativeElement.textContent).not.toContain('Edit position');
  });
});
