// Copyright 2026 Firefly Software Foundation
// SPDX-License-Identifier: Apache-2.0
import { TestBed } from '@angular/core/testing';
import { KoinonFacade, provideKoinonClient } from '@fireflyframework/koinon-angular';
import {
  KoinonClient,
  type Configuration,
  type HttpMethod,
  type KoinonTransport,
  type RequestOptions,
} from '@fireflyframework/koinon-sdk';
import { KoinonIndexManagementPanel } from './index-management-panel';
function setup() {
  const calls: { method: HttpMethod; path: string; options?: RequestOptions }[] = [];
  const configuration = {
    providers: [
      {
        id: 'provider',
        name: 'Embedding service',
        kind: 'openai',
        revision: 1,
        enabled: true,
        model_ids: ['embed-model'],
      },
    ],
  } as Configuration;
  const transport: KoinonTransport = {
    stream: () => {
      throw Error('Unexpected stream');
    },
    request: async <T>(method: HttpMethod, path: string, options?: RequestOptions) => {
      calls.push({ method, path, options });
      if (path.endsWith('/plan'))
        return {
          tenant_id: 'north',
          workspace_id: 'space',
          domain: 'documents',
          provider_id: 'provider',
          provider_kind: 'openai',
          provider_revision: 1,
          model_id: 'embed-model',
          dimensions: 1536,
          storage_dimensions: 1536,
          qualification: 'probe_passed',
          expected_connection_revision: null,
          active_space_id: null,
          active_index_id: null,
          chunk_count: 0,
          warnings: [],
        } as T;
      return {
        items: [],
        total: 0,
        limit: path.endsWith('/knowledge-index-choices') ? 100 : 25,
        offset: 0,
      } as T;
    },
  };
  TestBed.configureTestingModule({
    imports: [KoinonIndexManagementPanel],
    providers: [KoinonFacade, ...provideKoinonClient(new KoinonClient({ transport }), transport)],
  });
  const f = TestBed.inject(KoinonFacade);
  f.tenantId.set('north');
  f.workspaceId.set('space');
  f.context.set({
    subject: 'alex',
    tenants: [
      {
        id: 'north',
        name: 'North',
        roles: ['admin'],
        permissions: ['catalog:read', 'providers:write', 'indexes:manage'],
      },
    ],
    memberships: [
      {
        id: 'grant',
        tenant_id: 'north',
        subject: 'alex',
        role: 'admin',
        workspace_id: null,
        active: true,
      },
    ],
    workspaces: [
      {
        id: 'space',
        tenant_id: 'north',
        kind: 'workspace',
        status: 'ready',
        parent_id: null,
        workspace_id: 'space',
        project_id: null,
        name: 'Company knowledge',
        description: '',
        metadata: {},
        created_at: '2026-11-01T00:00:00Z',
      },
    ],
  });
  const fixture = TestBed.createComponent(KoinonIndexManagementPanel);
  fixture.componentRef.setInput('configuration', configuration);
  fixture.detectChanges();
  return { fixture, f, calls, element: fixture.nativeElement as HTMLElement };
}
it('shows scope and empty guidance without probing a provider automatically', async () => {
  const { fixture, calls, element } = setup();
  await fixture.whenStable();
  fixture.detectChanges();
  expect(element.textContent).toContain('Knowledge indexes');
  expect(element.textContent).toContain('No managed indexes');
  expect(calls.every((call) => call.method === 'GET')).toBe(true);
  expect(element.querySelector<HTMLSelectElement>('[aria-label="Index workspace"]')?.value).toBe(
    'space',
  );
});
it('shows the charged model check separately from the explicit build review', async () => {
  const { fixture, calls, element } = setup();
  await fixture.whenStable();
  fixture.detectChanges();
  [...element.querySelectorAll('button')]
    .find((button) => button.textContent?.includes('Plan a new index'))!
    .click();
  fixture.detectChanges();
  await fixture.whenStable();
  const provider = element.querySelector<HTMLSelectElement>('[aria-label="Embedding provider"]')!;
  provider.value = 'provider';
  provider.dispatchEvent(new Event('change'));
  fixture.detectChanges();
  await fixture.whenStable();
  fixture.detectChanges();
  const model = element.querySelector<HTMLSelectElement>('[aria-label="Embedding model"]')!;
  model.value = 'embed-model';
  model.dispatchEvent(new Event('change'));
  fixture.detectChanges();
  await fixture.whenStable();
  fixture.detectChanges();
  expect(element.textContent).toContain('may incur provider usage');
  expect(calls.some((call) => call.method === 'POST')).toBe(false);
  element
    .querySelector<HTMLFormElement>('.plan-form')!
    .dispatchEvent(new Event('submit', { bubbles: true, cancelable: true }));
  await fixture.whenStable();
  fixture.detectChanges();
  expect(element.textContent).toContain('Build this index');
  expect(element.textContent).toContain('1,536');
  expect(element.textContent).toContain('Embedding service');
  expect(element.querySelector('.plan-form')).toBeNull();
  [...element.querySelectorAll('button')]
    .find((button) => button.textContent?.includes('Change model'))!
    .click();
  fixture.detectChanges();
  expect(element.querySelector('.plan-form')).not.toBeNull();
  expect(element.querySelector('.plan-review')).toBeNull();
  expect(calls.filter((call) => call.method === 'POST').map((call) => call.path)).toEqual([
    '/tenants/north/knowledge-indexes/plan',
  ]);
});
it('removes the management controls and data after membership revocation', async () => {
  const { fixture, f, element } = setup();
  await fixture.whenStable();
  f.context.update((value) => ({ ...value!, memberships: [] }));
  fixture.detectChanges();
  await fixture.whenStable();
  fixture.detectChanges();
  expect(element.textContent).not.toContain('Plan a new index');
  expect(element.textContent).toContain('Current workspace access is required');
});

it('reevaluates separate membership expirations without retaining expired controls', () => {
  vi.useFakeTimers();
  try {
    const { fixture, f } = setup();
    const start = Date.now();
    f.context.update((value) => ({
      ...value!,
      memberships: [
        { ...value!.memberships[0], id: 'early', expires_at: new Date(start + 100).toISOString() },
        { ...value!.memberships[0], id: 'later', expires_at: new Date(start + 300).toISOString() },
      ],
    }));
    TestBed.tick();
    expect(fixture.componentInstance.canManage()).toBe(true);
    vi.advanceTimersByTime(101);
    TestBed.tick();
    expect(fixture.componentInstance.canManage()).toBe(true);
    vi.advanceTimersByTime(201);
    TestBed.tick();
    expect(fixture.componentInstance.canManage()).toBe(false);
    fixture.destroy();
  } finally {
    vi.useRealTimers();
  }
});
