// Copyright 2026 Firefly Software Foundation
// SPDX-License-Identifier: Apache-2.0
import { signal } from '@angular/core';
import { TestBed } from '@angular/core/testing';
import {
  KoinonClient,
  KoinonError,
  type CatalogEntry,
  type CatalogProposal,
  type KoinonTransport,
  type HttpMethod,
  type RequestOptions,
} from '@fireflyframework/koinon-sdk';
import { KoinonFacade, KoinonClientContext } from '@fireflyframework/koinon-angular';
import { KoinonCatalogProposals } from '../../../../chat/evidence/src/services/catalog-proposals';
import { KoinonCatalogProposal } from '../../../../chat/evidence/src/organisms/catalog-proposal';
const proposal = (
  status: CatalogProposal['status'] = 'pending',
  revision = 1,
): CatalogProposal => ({
  id: 'result',
  run_id: 'run',
  kind: 'catalog',
  status,
  revision,
  asset_id: 'asset',
  before: { name: 'Original name', description: 'Original description' },
  changes: { name: 'Reviewed name', description: '' },
  expected_catalog_digest: 'a'.repeat(64),
  created_at: '2026-10-27T12:00:00Z',
});
const asset: CatalogEntry = {
  id: 'asset',
  tenant_id: 'north',
  workspace_id: 'space',
  project_id: 'project',
  parent_id: 'source',
  kind: 'document',
  name: 'Original name',
  description: 'Original description',
  status: 'ready',
  metadata: {},
  created_at: '2026-10-27',
};
function setup(request?: KoinonTransport['request']) {
  const calls: { method: unknown; path: string; options?: RequestOptions }[] = [];
  const facade = {
    tenantId: signal('north'),
    workspaceId: signal('space'),
    projectId: signal('project'),
    context: signal({ subject: 'issuer|owner' }),
    permissions: signal(new Set(['chat:use', 'catalog:read', 'catalog:write'])),
    authRequired: signal(false),
  };
  const transport: KoinonTransport = {
    request: async <T>(method: HttpMethod, path: string, options?: RequestOptions) => {
      calls.push({ method, path, options });
      if (request) return await request<T>(method, path, options);
      return (path.endsWith('/catalog/asset') ? asset : proposal()) as T;
    },
    stream: () => {
      throw Error('No model stream');
    },
  };
  const clients = { get: () => new KoinonClient({ transport }), revision: signal(0) };
  TestBed.configureTestingModule({
    imports: [KoinonCatalogProposal],
    providers: [
      KoinonCatalogProposals,
      { provide: KoinonFacade, useValue: facade },
      { provide: KoinonClientContext, useValue: clients },
    ],
  });
  return { state: TestBed.inject(KoinonCatalogProposals), facade, clients, calls };
}
it('loads the real SDK proposal and catalog authority before exposing a review and never auto-applies', async () => {
  const { state, calls } = setup();
  await state.load('run', 'result');
  expect(calls.map((call) => [call.method, call.path])).toEqual([
    ['GET', '/tenants/north/chat/runs/run/proposals/result'],
    ['GET', '/tenants/north/catalog/asset'],
  ]);
  expect(calls.every((call) => call.options?.signal instanceof AbortSignal)).toBe(true);
  expect(state.proposal()?.changes.description).toBe('');
  expect(state.canApply()).toBe(true);
});
it('sends only explicit confirmation and the reviewed revision, with duplicate clicks fenced', async () => {
  let resolve!: (value: unknown) => void;
  const { state, calls } = setup(<T>(method: unknown, path: string) =>
    method === 'POST'
      ? new Promise<T>((complete) => {
          resolve = complete as (value: unknown) => void;
        })
      : Promise.resolve((path.endsWith('/catalog/asset') ? asset : proposal()) as T),
  );
  await state.load('run', 'result');
  const applying = state.apply();
  await state.apply();
  expect(calls.filter((call) => call.method === 'POST')).toHaveLength(1);
  expect(calls.at(-1)?.options?.body).toEqual({ confirm: true, expected_revision: 1 });
  resolve(proposal('applied', 2));
  await applying;
  expect(state.proposal()?.status).toBe('applied');
  expect(state.canApply()).toBe(false);
});
it('cancels through the SDK without catalog mutation and keeps cancellation available to an owner without write permission', async () => {
  const { state, facade, calls } = setup(
    async <T>(method: unknown, path: string) =>
      (method === 'POST'
        ? proposal('cancelled', 2)
        : path.endsWith('/catalog/asset')
          ? asset
          : proposal()) as T,
  );
  facade.permissions.set(new Set(['chat:use', 'catalog:read']));
  await state.load('run', 'result');
  expect(state.canApply()).toBe(false);
  expect(state.canCancel()).toBe(true);
  await state.cancel();
  expect(calls.at(-1)?.path).toBe('/tenants/north/chat/runs/run/proposals/result/cancel');
  expect(calls.at(-1)?.options?.body).toEqual({ expected_revision: 1 });
  expect(calls.some((call) => call.method === 'PATCH')).toBe(false);
});
it('rejects a target outside the selected project and hides stale principal/client/context data immediately', async () => {
  const { state, facade, clients } = setup();
  await state.load('run', 'result');
  facade.context.set({ subject: 'issuer|different' });
  expect(state.proposal()).toBeNull();
  expect(state.canApply()).toBe(false);
  facade.projectId.set('foreign-project');
  await state.load('run', 'result');
  expect(state.proposal()).toBeNull();
  expect(state.error()).toContain('current scope');
  facade.projectId.set('project');
  await state.load('run', 'result');
  clients.revision.update((value) => value + 1);
  expect(state.proposal()).toBeNull();
});
it('discards a late ignored-abort response and refuses operations after permission loss', async () => {
  let resolve!: (value: unknown) => void;
  let pendingSignal!: AbortSignal;
  const { state, facade, calls } = setup(
    <T>(_method: unknown, _path: string, options?: RequestOptions) => {
      pendingSignal = options!.signal!;
      return new Promise<T>((complete) => {
        resolve = complete as (value: unknown) => void;
      });
    },
  );
  const loading = state.load('run', 'result');
  facade.tenantId.set('south');
  TestBed.tick();
  expect(pendingSignal.aborted).toBe(true);
  resolve(proposal());
  await loading;
  expect(state.proposal()).toBeNull();
  facade.permissions.set(new Set());
  await state.apply();
  await state.cancel();
  expect(calls).toHaveLength(1);
});
it('requires explicit refresh after conflict and never treats changed resources as valid after refresh', async () => {
  let mode = 'conflict';
  const { state, calls } = setup(async <T>(method: unknown, path: string) => {
    if (method === 'POST')
      throw new KoinonError(
        409,
        mode === 'conflict' ? 'PROPOSAL_REVISION_CONFLICT' : 'PROPOSAL_RESOURCE_CHANGED',
        'Refresh before continuing',
      );
    return (path.endsWith('/catalog/asset') ? asset : proposal()) as T;
  });
  await state.load('run', 'result');
  await state.apply();
  expect(state.canApply()).toBe(false);
  const count = calls.length;
  await state.apply();
  expect(calls).toHaveLength(count);
  await state.load('run', 'result');
  expect(state.canApply()).toBe(true);
  mode = 'changed';
  await state.apply();
  await state.load('run', 'result');
  expect(state.canApply()).toBe(false);
  expect(state.canCancel()).toBe(true);
  expect(state.requiresNewProposal()).toBe(true);
});
it('renders before/after as text and performs no write until the review button is clicked', async () => {
  setup(
    async <T>(method: unknown, path: string) =>
      (method === 'POST'
        ? proposal('applied', 2)
        : path.endsWith('/catalog/asset')
          ? asset
          : proposal()) as T,
  );
  const fixture = TestBed.createComponent(KoinonCatalogProposal);
  fixture.componentRef.setInput('runId', 'run');
  fixture.componentRef.setInput('resultId', 'result');
  fixture.detectChanges();
  await fixture.whenStable();
  fixture.detectChanges();
  const component = fixture.componentInstance;
  const updated = vi.fn();
  component.proposalUpdated.subscribe(updated);
  expect(fixture.nativeElement.textContent).toContain('Original name');
  expect(fixture.nativeElement.textContent).toContain('Reviewed name');
  expect(fixture.nativeElement.querySelector('[data-action="apply"] button').disabled).toBe(false);
  fixture.nativeElement.querySelector('[data-action="apply"] button').click();
  fixture.detectChanges();
  await fixture.whenStable();
  fixture.detectChanges();
  expect(updated).toHaveBeenCalledOnce();
  expect(fixture.nativeElement.textContent).toContain('Applied');
  expect(fixture.nativeElement.querySelector('[data-action="apply"] button')).toBeNull();
});
it('does not emit a previously visible asset after a scope switch or leak data on403', async () => {
  let forbidden = false;
  setup(async <T>(_method: unknown, path: string) => {
    if (forbidden) throw new KoinonError(403, 'ACCESS_DENIED', 'Unavailable');
    return (path.endsWith('/catalog/asset') ? asset : proposal()) as T;
  });
  const fixture = TestBed.createComponent(KoinonCatalogProposal);
  fixture.componentRef.setInput('runId', 'run');
  fixture.componentRef.setInput('resultId', 'result');
  fixture.detectChanges();
  await fixture.whenStable();
  fixture.detectChanges();
  const component = fixture.componentInstance,
    selected = vi.fn();
  component.resourceRequested.subscribe(selected);
  forbidden = true;
  await component.state.load('run', 'result');
  fixture.detectChanges();
  component.resource();
  expect(selected).not.toHaveBeenCalled();
  expect(fixture.nativeElement.textContent).not.toContain('Original description');
});
