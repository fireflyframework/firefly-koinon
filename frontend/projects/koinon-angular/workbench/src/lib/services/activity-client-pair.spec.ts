// Copyright 2026 Firefly Software Foundation SPDX-License-Identifier: Apache-2.0
import { signal } from '@angular/core';
import { TestBed } from '@angular/core/testing';
import {
  KoinonClient,
  type KoinonTransport,
  type HttpMethod,
  type RequestOptions,
  type ActivitySummary,
  type Membership,
} from '@fireflyframework/koinon-sdk';
import {
  KoinonClientContext,
  KoinonFacade,
  provideKoinonClient,
} from '@fireflyframework/koinon-angular';
import { KoinonActivityPanel } from '../../../../activity/activity-panel';
function summary(count: number): ActivitySummary {
  const observed = { value: count, status: 'observed' as const };
  return {
    tenant_id: 'same',
    audience: 'personal',
    window: { start_at: '2026-10-01T00:00:00Z', end_at: '2026-10-02T00:00:00Z', time_zone: 'UTC' },
    coverage: { observed_since: null, complete_window: true },
    knowledge: { created: observed, updated: observed, consulted: observed },
    mcp: {
      requests: observed,
      tool_calls: observed,
      succeeded: observed,
      failed: observed,
      rejected: observed,
      average_duration_ms: observed,
      p95_duration_ms: observed,
    },
    models: {
      input_tokens: observed,
      output_tokens: observed,
      embedding_tokens: observed,
      cost: { amount: null, status: 'unavailable' },
    },
  };
}
function setup(a: KoinonTransport) {
  const facade = {
    context: signal<{ subject: string; memberships: Membership[] }>({
      subject: 'Alice',
      memberships: [],
    }),
    tenantId: signal('same'),
    workspaceId: signal(''),
    tenant: signal({ roles: ['viewer'] }),
    tenantPermissions: signal(new Set<string>()),
    authRequired: signal(false),
  };
  const client = new KoinonClient({ transport: a });
  TestBed.configureTestingModule({
    providers: [
      ...provideKoinonClient(client, a),
      KoinonClientContext,
      { provide: KoinonFacade, useValue: facade },
    ],
  });
  return {
    fixture: TestBed.createComponent(KoinonActivityPanel),
    context: TestBed.inject(KoinonClientContext),
    facade,
  };
}
it('immediately hides activity on client-only actor switch and resumes only with the explicit matching transport pair', async () => {
  const calls: string[] = [];
  const transport = (owner: string): KoinonTransport => ({
    request: async <T>(_method: HttpMethod, path: string) => {
      calls.push(owner + path);
      return summary(owner === 'A' ? 9 : 2) as T;
    },
    stream: async function* () {
      yield* [];
    },
  });
  const a = transport('A'),
    b = transport('B'),
    { fixture, context, facade } = setup(a);
  fixture.detectChanges();
  await fixture.whenStable();
  expect(fixture.componentInstance.summary()?.knowledge.created.value).toBe(9);
  const before = calls.length;
  const clientB = new KoinonClient({ transport: b });
  context.bind(clientB);
  facade.context.set({ subject: 'Bob', memberships: [] });
  expect(fixture.componentInstance.summary()).toBeNull();
  fixture.detectChanges();
  await fixture.whenStable();
  expect(calls).toHaveLength(before);
  expect(fixture.componentInstance.error()).toContain('not connected');
  context.bind(clientB, b);
  fixture.detectChanges();
  await fixture.whenStable();
  expect(fixture.componentInstance.summary()?.knowledge.created.value).toBe(2);
  expect(calls.slice(before).every((value) => value.startsWith('B'))).toBe(true);
});
it('aborts and discards a previous actor response and rejects an invalid window without using the default', async () => {
  let resolve: (value: ActivitySummary) => void = () => {
    throw Error('not registered');
  };
  let signal: AbortSignal | undefined;
  let calls = 0;
  const a: KoinonTransport = {
    request: <T>(_method: HttpMethod, _path: string, options?: RequestOptions) => {
      calls++;
      signal = options?.signal;
      return new Promise<T>((done) => (resolve = (value) => done(value as T)));
    },
    stream: async function* () {
      yield* [];
    },
  };
  const { fixture, context } = setup(a);
  fixture.detectChanges();
  await vi.waitFor(() => expect(signal).toBeInstanceOf(AbortSignal));
  const b: KoinonTransport = {
    request: async <T>() => summary(2) as T,
    stream: async function* () {
      yield* [];
    },
  };
  context.bind(new KoinonClient({ transport: b }));
  TestBed.tick();
  expect(signal?.aborted).toBe(true);
  resolve(summary(9));
  await fixture.whenStable();
  expect(fixture.componentInstance.summary()).toBeNull();
  context.bind(new KoinonClient({ transport: a }), a);
  fixture.componentInstance.window = null;
  await fixture.componentInstance.load();
  expect(calls).toBe(1);
});

it('offers the organization audience only for a current organization administrator with both required permissions', () => {
  const a: KoinonTransport = {
    request: async <T>() => summary(1) as T,
    stream: async function* () {
      yield* [];
    },
  };
  const { fixture, facade } = setup(a);
  facade.tenant.set({ roles: ['admin'] });
  facade.tenantPermissions.set(new Set(['audit:read', 'activity:read']));
  facade.context.set({
    subject: 'Alice',
    memberships: [
      {
        id: 'm',
        tenant_id: 'same',
        subject: 'Alice',
        role: 'admin',
        active: true,
        workspace_id: 'workspace',
      },
    ],
  });
  expect(fixture.componentInstance.canAdmin()).toBe(false);
  facade.context.set({
    subject: 'Alice',
    memberships: [
      {
        id: 'm',
        tenant_id: 'same',
        subject: 'Alice',
        role: 'admin',
        active: true,
        workspace_id: null,
      },
    ],
  });
  expect(fixture.componentInstance.canAdmin()).toBe(true);
  facade.tenantPermissions.set(new Set(['audit:read']));
  expect(fixture.componentInstance.canAdmin()).toBe(false);
});

it('locks a personal view to the owner audience even for administrators with job permissions', async () => {
  const paths:string[]=[];
  const transport:KoinonTransport={request:async<T>(_method:HttpMethod,path:string)=>{paths.push(path);return summary(3) as T;},stream:async function*(){yield*[];}};
  const {fixture,facade}=setup(transport);
  facade.tenantPermissions.set(new Set(['jobs:manage','audit:read','activity:read']));
  facade.context.set({subject:'Alice',memberships:[{id:'admin',tenant_id:'same',subject:'Alice',role:'admin',active:true,workspace_id:null}]});
  fixture.componentRef.setInput('personalOnly',true);
  fixture.detectChanges();await fixture.whenStable();
  expect(fixture.componentInstance.canAdmin()).toBe(false);
  expect(fixture.nativeElement.querySelector('select[name=activity-audience]')).toBeNull();
  expect(fixture.nativeElement.textContent).not.toContain('Processing jobs');
  fixture.componentInstance.audience='administrative';await fixture.componentInstance.load();
  expect(paths.length).toBeGreaterThan(0);expect(paths.every(path=>path.endsWith('/activity/personal'))).toBe(true);
});

it('aborts the administrative response when switching to a personal-only view', async () => {
  let finish:((value:ActivitySummary)=>void)|undefined,signal:AbortSignal|undefined;
  const transport:KoinonTransport={request:async<T>(_method:HttpMethod,path:string,options?:RequestOptions)=>{
    if(path.endsWith('/administration')){signal=options?.signal;return await new Promise<T>(resolve=>finish=value=>resolve(value as T));}return summary(2) as T;
  },stream:async function*(){yield*[];}};
  const {fixture,facade}=setup(transport);
  facade.tenantPermissions.set(new Set(['audit:read','activity:read']));
  facade.context.set({subject:'Alice',memberships:[{id:'admin',tenant_id:'same',subject:'Alice',role:'admin',active:true,workspace_id:null}]});
  fixture.detectChanges();await fixture.whenStable();fixture.componentInstance.audience='administrative';const pending=fixture.componentInstance.load();
  await vi.waitFor(()=>expect(finish).toBeTypeOf('function'));
  fixture.componentRef.setInput('personalOnly',true);fixture.detectChanges();await fixture.whenStable();
  expect(signal?.aborted).toBe(true);finish!({...summary(99),audience:'organization_administrators'});await pending;
  expect(fixture.componentInstance.summary()?.knowledge.created.value).toBe(2);
});

it('invalidates personal summaries immediately when workspace access or tenant selection changes', async () => {
  const transport:KoinonTransport={request:async<T>(_method:HttpMethod,path:string)=>({...summary(2),tenant_id:path.split('/')[2]}) as T,stream:async function*(){yield*[];}};
  const {fixture,facade}=setup(transport);fixture.componentRef.setInput('personalOnly',true);fixture.detectChanges();await fixture.whenStable();
  expect(fixture.componentInstance.summary()?.tenant_id).toBe('same');facade.workspaceId.set('new-scope');expect(fixture.componentInstance.summary()).toBeNull();fixture.detectChanges();await fixture.whenStable();
  facade.tenantId.set('second');expect(fixture.componentInstance.summary()).toBeNull();fixture.detectChanges();await fixture.whenStable();expect(fixture.componentInstance.summary()?.tenant_id).toBe('second');
});

for(const mismatch of ['tenant','audience'] as const) it(`rejects a personal summary with a mismatched ${mismatch}`,async()=>{
  const transport:KoinonTransport={request:async<T>()=>({...summary(3),...(mismatch==='tenant'?{tenant_id:'other'}:{audience:'organization_administrators' as const})}) as T,stream:async function*(){yield*[];}};
  const {fixture}=setup(transport);fixture.componentRef.setInput('personalOnly',true);fixture.detectChanges();await fixture.whenStable();
  expect(fixture.componentInstance.summary()).toBeNull();expect(fixture.componentInstance.error()).toBe('Activity could not be loaded. Try again.');
});
