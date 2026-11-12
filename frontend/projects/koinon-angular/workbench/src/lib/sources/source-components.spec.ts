// Copyright 2026 Firefly Software Foundation SPDX-License-Identifier: Apache-2.0
import type { Type } from '@angular/core';
import { TestBed } from '@angular/core/testing';
import {
  KoinonClient,
  type HttpMethod,
  type KoinonTransport,
  type RequestOptions,
} from '@fireflyframework/koinon-sdk';
import {
  KoinonFacade,
  KoinonI18n,
  provideKoinonClient,
} from '@fireflyframework/koinon-angular/workbench/core';
import { KoinonReaderSourceSelector } from './reader-source-selector';
import { KoinonConnectedSources } from './connected-sources';
import { KoinonSynchronizationPage } from './synchronization-page';
const account = {
  id: 'account',
  provider: 'google_drive',
  status: 'connected',
  revision: 1,
  account: { provider: 'google_drive', subject: 'private-subject', tenant_id: 'private-tenant' },
  display_name: 'Research account',
  display_address: 'person@example.test',
  display_address_verified: true,
};
const capabilities = {
  accounts_available: true,
  inbound_only: true,
  synchronization_available: false,
  providers: [
    {
      provider: 'google_drive',
      display_name: 'Google Drive',
      consent_available: false,
      unavailable_reason: 'not_configured',
    },
  ],
  modes: ['document'],
  formats: [{ extension: '.pdf', mode: 'document' }],
  schedule: {
    min_interval_seconds: 900,
    max_interval_seconds: 604800,
    calendar_timezones: 'iana',
    max_calendar_weekdays: 7,
  },
};
async function mount<T>(
  component: Type<T>,
  handler?: (method: HttpMethod, path: string, options?: RequestOptions) => Promise<unknown>,
) {
  const transport: KoinonTransport = {
    request: <R>(method: HttpMethod, path: string, options?: RequestOptions) =>
      (handler
        ? handler(method, path, options)
        : Promise.resolve(
            path.endsWith('reader-selection')
              ? { revision: 0, connections: [] }
              : path.endsWith('capabilities')
                ? capabilities
                : { items: [account], next_cursor: null, synchronization_available: false },
          )) as Promise<R>,
    stream: () => {
      throw Error('Unexpected stream');
    },
  };
  await TestBed.configureTestingModule({
    imports: [component],
    providers: [KoinonFacade, ...provideKoinonClient(new KoinonClient({ transport }), transport)],
  }).compileComponents();
  const f = TestBed.inject(KoinonFacade);
  f.tenantId.set('tenant');
  f.context.set({ subject: 'reader', tenants: [], workspaces: [], memberships: [] });
  const fixture = TestBed.createComponent(component);
  fixture.detectChanges();
  await fixture.whenStable();
  return { fixture, f, root: fixture.nativeElement as HTMLElement };
}
describe('source interface behavior', () => {
  it('applies local-only without saving preferences or starting a request', async () => {
    const writes: string[] = [];
    const { fixture, root } = await mount(KoinonReaderSourceSelector, async (method, path) => {
      if (method !== 'GET') writes.push(path);
      return path.endsWith('reader-selection')
        ? { revision: 1, connections: [] }
        : { items: [account], next_cursor: null };
    });
    const choices: unknown[] = [];
    fixture.componentInstance.selectionChange.subscribe((value) => choices.push(value));
    const details = root.querySelector('details')!;
    details.open = true;
    details.dispatchEvent(new Event('toggle'));
    await fixture.whenStable();
    fixture.detectChanges();
    const local = root.querySelector<HTMLInputElement>('input[value=local]')!;
    local.click();
    fixture.detectChanges();
    [...root.querySelectorAll('button')]
      .find((button) => button.textContent?.trim() === 'Apply')!
      .click();
    expect(choices).toEqual([[]]);
    expect(writes).toEqual([]);
    expect(root.textContent).not.toContain('private-subject');
  });
  it('renders authorized labels and clears account identities on permission loss', async () => {
    const { fixture, root, f } = await mount(KoinonConnectedSources);
    expect(root.textContent).toContain('Research account');
    expect(root.textContent).toContain('person@example.test');
    expect(root.textContent).not.toContain('private-subject');
    expect(root.textContent).not.toContain('private-tenant');
    f.authRequired.set(true);
    fixture.detectChanges();
    expect(root.textContent).not.toContain('Research account');
    expect(root.textContent).not.toContain('person@example.test');
  });
  it('displays server-disabled synchronization without enabling creation', async () => {
    const { root } = await mount(KoinonSynchronizationPage);
    expect(root.textContent).toContain('Synchronization is not available in this installation.');
    expect(
      [...root.querySelectorAll('button')].some(
        (button) => button.textContent?.trim() === 'New synchronization',
      ),
    ).toBe(false);
    expect(root.textContent).toContain('Connected sources');
  });
  it('does not attach a late consent response after the member cancels', async () => {
    const { fixture } = await mount(KoinonConnectedSources);
    let finish!: (value: import('./source-contracts').SourceAuthorization | null) => void;
    const begin = vi.spyOn(fixture.componentInstance.state, 'begin').mockImplementation(
      () =>
        new Promise((resolve) => {
          finish = resolve;
        }),
    );
    const replace = vi.fn(),
      close = vi.fn();
    const popup = { opener: window, location: { replace }, close };
    vi.spyOn(window, 'open').mockReturnValue(popup as unknown as Window);
    fixture.componentInstance.connect('google_drive');
    fixture.componentInstance.cancelConsent();
    finish({
      connection_id: 'account',
      challenge_id: 'challenge',
      callback_uri: window.location.origin + '/callback',
      authorization_url: window.location.origin + '/consent?state=expected',
      expires_at: '2099-01-01T00:00:00Z',
    });
    await fixture.whenStable();
    expect(begin).toHaveBeenCalledTimes(1);
    expect(replace).not.toHaveBeenCalled();
    expect(fixture.componentInstance.authorization()).toBeNull();
    expect(close).toHaveBeenCalled();
  });
  it('loads Spanish source labels with the lazy feature', async () => {
    const { fixture, root } = await mount(KoinonConnectedSources);
    TestBed.inject(KoinonI18n).apply({
      locale: 'es-ES',
      time_zone: 'UTC',
      response_language: 'es',
    });
    fixture.detectChanges();
    expect(root.textContent).toContain('Koinon no modifica tus archivos originales');
    expect(root.textContent).toContain('Desconectar cuenta');
  });
});
