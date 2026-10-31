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
import { KoinonAccount } from '../services/account';
import type { OrganizationPresentation } from '@fireflyframework/koinon-sdk';
import { KoinonOrganizationInformation } from './organization-information';
async function mount(shared = false, locale = 'en-US', presentation?: OrganizationPresentation) {
  const calls: { path: string; options: RequestOptions | undefined }[] = [];
  const transport: KoinonTransport = {
    request: async <T>(_method: HttpMethod, path: string, options?: RequestOptions) => {
      calls.push({ path, options });
      return (
        path.endsWith('/avatar')
          ? { blob: new Blob(['avatar']), not_modified: false }
          : path.endsWith('/presentation')
            ? (presentation ?? {
                tenant_id: 'north',
                status: 'not_configured',
                display_name: 'Alex',
                revision: 0,
              })
            : path.endsWith('/me')
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
    providers: [
      KoinonFacade,
      KoinonAccount,
      ...provideKoinonClient(new KoinonClient({ transport }), transport),
    ],
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

it('shows effective organization presentation separately from personal preferences', async () => {
  const { fixture } = await mount();
  expect(fixture.nativeElement.textContent).toContain('Organization presentation');
  expect(fixture.nativeElement.textContent).toContain('Refresh status');
});

it('saves allowed organization presentation with a revision without changing personal preferences', async () => {
  const { fixture, calls } = await mount(false, 'en-US', {
    tenant_id: 'north',
    status: 'current',
    display_name: 'Alex North',
    revision: 7,
    name_mode: 'organization',
    avatar_mode: 'organization',
    allow_personal_overrides: true,
  });
  const name = Array.from(
    fixture.nativeElement.querySelectorAll('label') as NodeListOf<HTMLLabelElement>,
  )
    .find((label) => label.textContent?.startsWith('Name to use'))
    ?.querySelector('select');
  expect(name).toBeInstanceOf(HTMLSelectElement);
  name!.value = 'personal';
  name!.dispatchEvent(new Event('change'));
  const button = Array.from(
    fixture.nativeElement.querySelectorAll('button') as NodeListOf<HTMLButtonElement>,
  ).find((button) => button.textContent?.includes('Save presentation'));
  button!.click();
  await fixture.whenStable();
  expect(calls.find((call) => call.options?.body)?.options?.body).toEqual({
    expected_revision: 7,
    name_mode: 'personal',
    avatar_mode: 'organization',
  });
  expect(calls.every((call) => !call.path.endsWith('/profile'))).toBe(true);
});
it('explains organization-only presentation in Spanish without rendering personal override controls', async () => {
  const { fixture } = await mount(false, 'es-ES', {
    tenant_id: 'north',
    status: 'current',
    display_name: 'Alex North',
    revision: 7,
    allow_personal_overrides: false,
  });
  expect(fixture.nativeElement.textContent).toContain('Identidad en la organización');
  expect(fixture.nativeElement.textContent).toContain(
    'Tu organización exige el uso del nombre y la foto corporativos.',
  );
  expect(fixture.nativeElement.querySelector('select')).toBeNull();
});

it('uses the current personal photo in personal presentation mode and clears it after deletion', async () => {
  const NativeURL = URL;
  vi.stubGlobal(
    'URL',
    class extends NativeURL {
      static override createObjectURL() {
        return 'blob:previous-personal';
      }
      static override revokeObjectURL() {
        return;
      }
    },
  );
  try {
    const { fixture } = await mount(false, 'en-US', {
      tenant_id: 'north',
      status: 'current',
      display_name: 'Alex',
      revision: 7,
      profile_id: 'p1',
      avatar_version: 'old',
      avatar_source: 'personal',
      allow_personal_overrides: true,
    });
    const account = TestBed.inject(KoinonAccount);
    account.avatar.set('blob:current-personal');
    fixture.detectChanges();
    expect(
      fixture.nativeElement.querySelector('ffk-corporate-presentation img')?.getAttribute('src'),
    ).toBe('blob:current-personal');
    account.avatar.set('');
    fixture.detectChanges();
    expect(fixture.nativeElement.querySelector('ffk-corporate-presentation img')).toBeNull();
  } finally {
    vi.unstubAllGlobals();
  }
});
it('directs a source conflict to administrator review instead of offering repeated sync', async () => {
  const { fixture } = await mount(false, 'en-US', {
    tenant_id: 'north',
    status: 'conflict',
    display_name: '',
    revision: 1,
    allow_personal_overrides: false,
  });
  const buttons = Array.from(
    fixture.nativeElement.querySelectorAll('button') as NodeListOf<HTMLButtonElement>,
  );
  expect(buttons.some((button) => button.textContent?.trim() === 'Sync now')).toBe(false);
  expect(buttons.some((button) => button.textContent?.trim() === 'Refresh status')).toBe(true);
  expect(fixture.nativeElement.textContent).toContain(
    'Ask your organization administrator to review the profile source, then sign in again.',
  );
});
