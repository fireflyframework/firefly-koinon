// Copyright 2026 Firefly Software Foundation
// SPDX-License-Identifier: Apache-2.0
import { TestBed } from '@angular/core/testing';
import {
  KoinonClient,
  type KoinonTransport,
  type McpConnectionDescriptor,
} from '@fireflyframework/koinon-sdk';
import { provideKoinonClient } from '../client-provider';
import { KoinonFacade } from '../koinon-facade';
import { KoinonMcpConnectionPanel } from './mcp-connection-panel';

const descriptor: McpConnectionDescriptor = {
  enabled: true,
  endpoint: 'https://knowledge.example.test/mcp',
  authentication: ['oauth'],
  clients: [],
  oauth_enabled: true,
  oauth_registration: 'pre_registered',
  supported_scopes: ['catalog:read'],
  tools: [],
  review: { supported: true },
};
function setup(request: KoinonTransport['request']) {
  const transport: KoinonTransport = {
    request,
    stream: () => {
      throw new Error('Unexpected stream');
    },
  };
  TestBed.configureTestingModule({
    providers: [KoinonFacade, ...provideKoinonClient(new KoinonClient({ transport }), transport)],
  });
  const facade = TestBed.inject(KoinonFacade);
  facade.tenantId.set('tenant-one');
  const panel = TestBed.runInInjectionContext(() => new KoinonMcpConnectionPanel());
  return { facade, panel };
}
describe('organization MCP connection details', () => {
  it('loads current organization registrations through the tenant SDK method', async () => {
    const paths: string[] = [];
    const { panel } = setup(async <T>(_method: unknown, path: string) => {
      paths.push(path);
      return descriptor as T;
    });
    await panel.load();
    expect(paths).toEqual(['/tenants/tenant-one/mcp/connection']);
    expect(panel.value()).toEqual(descriptor);
    panel.ngOnDestroy();
  });
  it('discards a delayed registration list after switching organizations', async () => {
    let finish!: (value: McpConnectionDescriptor) => void;
    const { facade, panel } = setup(
      <T>() =>
        new Promise<McpConnectionDescriptor>((resolve) => {
          finish = resolve;
        }) as Promise<T>,
    );
    const loading = panel.load();
    facade.tenantId.set('tenant-two');
    finish(descriptor);
    await loading;
    expect(panel.value()).toBeNull();
    panel.ngOnDestroy();
  });
  it('requires an organization instead of falling back to installation registrations', async () => {
    let calls = 0;
    const { facade, panel } = setup(async <T>() => {
      ++calls;
      return descriptor as T;
    });
    facade.tenantId.set('');
    await panel.load();
    expect(calls).toBe(0);
    expect(panel.value()).toBeNull();
    expect(panel.error()).toBe('Choose an organization to load its connection details.');
    panel.ngOnDestroy();
  });
});
