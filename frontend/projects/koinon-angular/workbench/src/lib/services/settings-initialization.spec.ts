// Copyright 2026 Firefly Software Foundation SPDX-License-Identifier: Apache-2.0
import { TestBed } from '@angular/core/testing';
import { KoinonFacade, provideKoinonClient } from '@fireflyframework/koinon-angular';
import {
  KoinonClient,
  KoinonError,
  type HttpMethod,
  type KoinonTransport,
  type RequestOptions,
} from '@fireflyframework/koinon-sdk';
import { KoinonSettingsPage } from '../../../../settings/src/settings-page';
async function mount(initial: 'providers' | 'agents') {
  let release!: (failed?: boolean) => void, requested!: () => void;
  const loading = new Promise<void>((resolve) => {
    requested = resolve;
  });
  const transport: KoinonTransport = {
    request: async <T>(_method: HttpMethod, path: string) => {
      if (path.endsWith('/configuration')) {
        requested();
        return await new Promise<T>((resolve, reject) => {
          release = (failed) =>
            failed
              ? reject(new KoinonError(503, 'UNAVAILABLE', 'Initial metadata unavailable'))
              : resolve({ providers: [], provider_types: [], connections: [], checks: [] } as T);
        });
      }
      return (
        path.endsWith('/chat/settings')
          ? {
              tenant_id: 'tenant',
              default_agent_id: null,
              revision: 0,
              configured: false,
              can_run: false,
              status: 'unconfigured',
            }
          : { items: [] }
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
      { id: 'tenant', name: 'Team', roles: [], permissions: ['providers:write', 'agents:write'] },
    ],
    memberships: [],
    workspaces: [],
  });
  const fixture = TestBed.createComponent(KoinonSettingsPage);
  fixture.componentRef.setInput('actions', { section: () => initial, chat: () => undefined });
  fixture.detectChanges();
  await loading;
  fixture.detectChanges();
  return { fixture, release };
}
for (const failed of [false, true]) {
  it(`keeps a later Agents choice after initial provider metadata ${failed ? 'fails' : 'completes'}`, async () => {
    const { fixture, release } = await mount('providers');
    await fixture.componentInstance.openSection('agents');
    fixture.detectChanges();
    expect(fixture.componentInstance.section()).toBe('agents');
    release(failed);
    await fixture.whenStable();
    fixture.detectChanges();
    expect(fixture.componentInstance.section()).toBe('agents');
    expect(fixture.nativeElement.querySelector('ffk-organization-chat-settings')).not.toBeNull();
    expect(fixture.componentInstance.c.error()).toBe(failed ? 'Initial metadata unavailable' : '');
  });
  it(`keeps an explicit Providers choice after an initial Agents request and metadata ${failed ? 'failure' : 'completion'}`, async () => {
    const { fixture, release } = await mount('agents');
    await fixture.componentInstance.openSection('providers');
    release(failed);
    await fixture.whenStable();
    fixture.detectChanges();
    expect(fixture.componentInstance.section()).toBe('providers');
  });
}
it('applies the requested initial section before waiting for provider metadata', async () => {
  const { fixture, release } = await mount('agents');
  expect(fixture.componentInstance.section()).toBe('agents');
  release();
  await fixture.whenStable();
});

it('keeps a deferred initial Agents failure visible after provider metadata succeeds', async () => {
  let releaseAgents!: () => void, releaseMetadata!: () => void;
  let startedAgents!: () => void, startedMetadata!: () => void;
  const agentsStarted = new Promise<void>((resolve) => {
    startedAgents = resolve;
  });
  const metadataStarted = new Promise<void>((resolve) => {
    startedMetadata = resolve;
  });
  const transport: KoinonTransport = {
    request: async <T>(_method: HttpMethod, path: string, options?: RequestOptions) => {
      if (path.endsWith('/configuration')) {
        startedMetadata();
        return await new Promise<T>((resolve) => {
          releaseMetadata = () =>
            resolve({ providers: [], provider_types: [], connections: [], checks: [] } as T);
        });
      }
      if (path.endsWith('/agents') && options?.query?.['page_size'] !== 100) {
        startedAgents();
        return await new Promise<T>((_resolve, reject) => {
          releaseAgents = () =>
            reject(new KoinonError(503, 'UNAVAILABLE', 'Agents are temporarily unavailable'));
        });
      }
      return (
        path.endsWith('/chat/settings')
          ? {
              tenant_id: 'tenant',
              default_agent_id: null,
              revision: 0,
              configured: false,
              can_run: false,
              status: 'unconfigured',
            }
          : { items: [] }
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
      { id: 'tenant', name: 'Team', roles: [], permissions: ['providers:write', 'agents:write'] },
    ],
    memberships: [],
    workspaces: [],
  });
  const fixture = TestBed.createComponent(KoinonSettingsPage);
  fixture.componentRef.setInput('actions', { section: () => 'agents', chat: () => undefined });
  fixture.detectChanges();
  await agentsStarted;
  releaseAgents();
  await metadataStarted;
  releaseMetadata();
  await fixture.whenStable();
  fixture.detectChanges();
  expect(fixture.componentInstance.section()).toBe('agents');
  expect(fixture.componentInstance.c.error()).toBe('Agents are temporarily unavailable');
  expect(fixture.nativeElement.textContent).toContain('Agents are temporarily unavailable');
  expect(fixture.nativeElement.textContent).not.toContain('No agents in this view');
});
