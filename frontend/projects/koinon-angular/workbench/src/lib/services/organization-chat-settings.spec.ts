// Copyright 2026 Firefly Software Foundation SPDX-License-Identifier: Apache-2.0
import { TestBed } from '@angular/core/testing';
import { KoinonFacade, KoinonI18n, provideKoinonClient } from '@fireflyframework/koinon-angular';
import {
  KoinonClient,
  KoinonError,
  type HttpMethod,
  type KoinonTransport,
  type RequestOptions,
} from '@fireflyframework/koinon-sdk';
import { KoinonOrganizationChatSettings } from '../../../../settings/src/organization-chat-settings';
import { KoinonSettingsPage } from '../../../../settings/src/settings-page';
const organizationSettings = {
  tenant_id: 'tenant',
  default_agent_id: 'second',
  revision: 4,
  configured: true,
  can_run: true,
  status: 'ready',
};
async function mount(
  options: { denied?: boolean; conflict?: boolean; failure?: number; spanish?: boolean } = {},
) {
  const requests: { method: HttpMethod; path: string; body: unknown }[] = [];
  const transport: KoinonTransport = {
    request: async <T>(method: HttpMethod, path: string, request?: RequestOptions) => {
      requests.push({ method, path, body: request?.body });
      if (path.endsWith('/chat/settings')) {
        if (method === 'PUT' && options.failure)
          throw new KoinonError(options.failure, 'DENIED', 'Observed save failure');
        if (method === 'PUT' && options.conflict)
          throw new KoinonError(409, 'CONFLICT', 'Organization settings changed');
        return (
          method === 'PUT'
            ? {
                ...organizationSettings,
                default_agent_id: (request?.body as { default_agent_id: string | null })
                  .default_agent_id,
                revision: 5,
              }
            : organizationSettings
        ) as T;
      }
      return (
        path.endsWith('/agents')
          ? {
              items: [
                { id: 'first', name: 'First agent', enabled: true, status: 'ready', scope: {} },
                {
                  id: 'second',
                  name: 'Organization guide',
                  enabled: true,
                  status: 'ready',
                  scope: {},
                },
                {
                  id: 'scoped',
                  name: 'Private project agent',
                  enabled: true,
                  status: 'ready',
                  scope: { workspace_id: 'workspace' },
                },
              ],
              page: 1,
              pages: 1,
            }
          : { providers: [], provider_types: [], connections: [], checks: [] }
      ) as T;
    },
    stream: () => {
      throw new Error('Unexpected stream');
    },
  };
  TestBed.configureTestingModule({
    imports: [KoinonSettingsPage],
    providers: [KoinonFacade, ...provideKoinonClient(new KoinonClient({ transport }), transport)],
  });
  const facade = TestBed.inject(KoinonFacade);
  facade.tenantId.set('tenant');
  facade.context.set({
    subject: 'operator',
    tenants: [
      {
        id: 'tenant',
        name: 'Team',
        roles: [],
        permissions: options.denied ? [] : ['agents:write'],
      },
    ],
    memberships: [],
    workspaces: [],
  });
  if (options.spanish)
    TestBed.inject(KoinonI18n).apply({
      locale: 'es-ES',
      time_zone: 'UTC',
      response_language: 'es',
    });
  const fixture = TestBed.createComponent(KoinonSettingsPage);
  fixture.componentRef.setInput('actions', { section: () => 'agents', chat: () => undefined });
  fixture.detectChanges();
  await fixture.whenStable();
  fixture.detectChanges();
  return { fixture, requests, facade };
}
it('renders one organization chat choice using the saved default and excludes scoped agents', async () => {
  const { fixture, requests } = await mount();
  const select = fixture.nativeElement.querySelector(
    '#organization-chat-agent',
  ) as HTMLSelectElement;
  expect(select).not.toBeNull();
  expect(select.value).toBe('second');
  expect([...select.options].map((option) => option.value)).toEqual(['', 'first', 'second']);
  expect(
    requests.some((request) => request.path.endsWith('/chat/settings') && request.method === 'GET'),
  ).toBe(true);
});
it('saves and clears the organization default with the observed revision', async () => {
  const { fixture, requests } = await mount();
  const select = fixture.nativeElement.querySelector(
    '#organization-chat-agent',
  ) as HTMLSelectElement;
  expect(select).not.toBeNull();
  select.value = '';
  select.dispatchEvent(new Event('change'));
  fixture.detectChanges();
  await fixture.whenStable();
  fixture.detectChanges();
  const button = fixture.nativeElement.querySelector(
    'ffk-organization-chat-settings button[type=submit]',
  ) as HTMLButtonElement;
  expect(button.disabled).toBe(false);
  button.click();
  await fixture.whenStable();
  fixture.detectChanges();
  expect(requests.find((request) => request.method === 'PUT')?.body).toEqual({
    default_agent_id: null,
    expected_revision: 4,
  });
});
it('does not expose organization chat controls or read its settings for ordinary users', async () => {
  const { fixture, requests } = await mount({ denied: true });
  expect(fixture.nativeElement.querySelector('#organization-chat-agent')).toBeNull();
  expect(requests.some((request) => request.path.endsWith('/chat/settings'))).toBe(false);
});

it('requires an explicit reload after a save conflict and preserves the attempted choice', async () => {
  const { fixture, requests } = await mount({ conflict: true });
  const select = fixture.nativeElement.querySelector(
    '#organization-chat-agent',
  ) as HTMLSelectElement;
  select.value = 'first';
  select.dispatchEvent(new Event('change'));
  fixture.detectChanges();
  await fixture.whenStable();
  fixture.detectChanges();
  const button = fixture.nativeElement.querySelector(
    'ffk-organization-chat-settings button[type=submit]',
  ) as HTMLButtonElement;
  button.click();
  await fixture.whenStable();
  fixture.detectChanges();
  expect(requests.find((request) => request.method === 'PUT')?.body).toEqual({
    default_agent_id: 'first',
    expected_revision: 4,
  });
  expect(select.value).toBe('first');
  expect(fixture.nativeElement.textContent).toContain(
    'Organization chat changed. Reload the settings before saving again.',
  );
  expect(button.disabled).toBe(true);
  (
    fixture.nativeElement.querySelector(
      'button[aria-label="Reload organization chat"]',
    ) as HTMLButtonElement
  ).click();
  await fixture.whenStable();
  fixture.detectChanges();
  expect(select.value).toBe('second');
  expect(requests.filter((request) => request.method === 'PUT')).toHaveLength(1);
});
it('localizes the organization choice in the lazy settings section', async () => {
  const { fixture } = await mount({ spanish: true });
  expect(
    fixture.nativeElement.querySelector('ffk-organization-chat-settings').textContent,
  ).toContain('Chat de la organización');
  expect(
    fixture.nativeElement.querySelector('label[for=organization-chat-agent]').textContent,
  ).toContain('Agente del chat de la organización');
  expect(
    fixture.nativeElement.querySelector('ffk-organization-chat-settings button[type=submit]')
      .textContent,
  ).toContain('Guardar el chat de la organización');
});
for (const status of [401, 403])
  it(`organization default save ${status} preserves the authentication boundary`, async () => {
    const { fixture, facade } = await mount({ failure: status });
    const select = fixture.nativeElement.querySelector(
      '#organization-chat-agent',
    ) as HTMLSelectElement;
    select.value = 'first';
    select.dispatchEvent(new Event('change'));
    fixture.detectChanges();
    await fixture.whenStable();
    fixture.detectChanges();
    (
      fixture.nativeElement.querySelector(
        'ffk-organization-chat-settings button[type=submit]',
      ) as HTMLButtonElement
    ).click();
    await fixture.whenStable();
    fixture.detectChanges();
    expect(facade.authRequired()).toBe(status === 401);
    expect(fixture.nativeElement.textContent).toContain('Observed save failure');
  });

it('ignores an older organization settings response after an embedded host changes organizations', async () => {
  let release: () => void = () => {
    throw new Error('Old settings request did not start');
  };
  const transport: KoinonTransport = {
    request: async <T>(_method: HttpMethod, path: string) => {
      if (path.endsWith('/chat/settings')) {
        if (path.includes('/tenant/'))
          return await new Promise<T>((resolve) => {
            release = () => resolve({ ...organizationSettings, default_agent_id: 'first' } as T);
          });
        return { ...organizationSettings, tenant_id: 'other', revision: 7 } as T;
      }
      return {
        items: [
          { id: 'first', name: 'First agent', scope: {} },
          { id: 'second', name: 'Current organization guide', scope: {} },
        ],
      } as T;
    },
    stream: () => {
      throw new Error('Unexpected stream');
    },
  };
  TestBed.configureTestingModule({
    imports: [KoinonOrganizationChatSettings],
    providers: [KoinonFacade, ...provideKoinonClient(new KoinonClient({ transport }), transport)],
  });
  const facade = TestBed.inject(KoinonFacade);
  facade.context.set({
    subject: 'host-user',
    tenants: ['tenant', 'other'].map((id) => ({
      id,
      name: id,
      roles: [],
      permissions: ['agents:write'],
    })),
    memberships: [],
    workspaces: [],
  });
  facade.tenantId.set('tenant');
  const fixture = TestBed.createComponent(KoinonOrganizationChatSettings);
  fixture.detectChanges();
  facade.tenantId.set('other');
  fixture.detectChanges();
  release();
  await fixture.whenStable();
  fixture.detectChanges();
  expect(fixture.componentInstance.settings()?.tenant_id).toBe('other');
  expect(fixture.componentInstance.settings()?.revision).toBe(7);
  expect((fixture.nativeElement.querySelector('select') as HTMLSelectElement).value).toBe('second');
});
