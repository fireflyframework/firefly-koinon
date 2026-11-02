// Copyright 2026 Firefly Software Foundation
// SPDX-License-Identifier: Apache-2.0
import { TestBed } from '@angular/core/testing';
import { KoinonFacade, provideKoinonClient } from '@fireflyframework/koinon-angular';
import {
  KoinonClient,
  type KnowledgeRole,
  type KoinonTransport,
} from '@fireflyframework/koinon-sdk';
import { KoinonSettingsPage } from './settings-page';
import { KoinonClientContext } from '@fireflyframework/koinon-angular';
import { KoinonKnowledgeModels } from './knowledge-models';
import type { KnowledgeSectionRequest } from './knowledge-navigation';
function setup() {
  const transport: KoinonTransport = {
    request: async <T>() =>
      ({ roles: [], providers: [], model_options_schema: { properties: {} }, items: [] }) as T,
    stream: () => {
      throw Error('Unexpected stream');
    },
  };
  TestBed.configureTestingModule({
    providers: [KoinonFacade, ...provideKoinonClient(new KoinonClient({ transport }), transport)],
  });
  const f = TestBed.inject(KoinonFacade);
  f.tenantId.set('north');
  f.context.set({
    subject: 'alex',
    tenants: [
      {
        id: 'north',
        name: 'North',
        roles: ['admin'],
        permissions: ['catalog:read', 'providers:write', 'indexes:manage', 'agents:write'],
      },
    ],
    memberships: [],
    workspaces: [
      {
        id: 'workspace',
        tenant_id: 'north',
        kind: 'workspace',
        status: 'ready',
        parent_id: null,
        workspace_id: 'workspace',
        project_id: null,
        name: 'Authorized knowledge',
        description: '',
        metadata: {},
        created_at: '2026-11-01T00:00:00Z',
      },
    ],
  });
  f.capabilities.set({
    providers: [],
    features: [],
    domains: {
      canon: { installed: true, registered: true },
      structured: { installed: true, registered: true },
    },
  });
  const fixture = TestBed.createComponent(KoinonKnowledgeModels),
    model = fixture.componentInstance;
  const events: KnowledgeSectionRequest[] = [];
  model.sectionRequested.subscribe((v) => events.push(v));
  return { fixture, model, f, events };
}
const embedding: KnowledgeRole = {
  id: 'structured.embedding',
  domain: 'structured',
  kind: 'embedding',
  label: 'Structured schema embeddings',
  purposes: ['ingest'],
  supports_current_agent: false,
  compatible_index_required: true,
  assignment: null,
  status: 'needs_setup',
  runtime_qualification: 'not_run',
};
it('requires an explicit leave decision and preserves model options when continuing to edit', () => {
  const { model, events } = setup();
  model.begin(embedding);
  model.modelOptions = { temperature: '0.2' };
  model.requestSection('storage');
  expect(events).toEqual([]);
  expect(model.navigationReview()?.section).toBe('storage');
  model.keepEditing();
  expect(model.modelOptions).toEqual({ temperature: '0.2' });
  expect(model.editing()).toEqual(embedding);
  expect(model.navigationReview()).toBeNull();
});
it('carries only a selected workspace and domain after explicit editor departure', () => {
  const { model, events } = setup();
  model.service.scope.set('workspace');
  model.begin(embedding);
  model.requestSection('storage');
  model.confirmNavigation();
  expect(events).toEqual([{ section: 'storage', workspaceId: 'workspace', domain: 'structured' }]);
});
it('does not fabricate a workspace from organization-default scope', () => {
  const { model, events } = setup();
  model.begin(embedding);
  model.requestSection('storage');
  model.confirmNavigation();
  expect(events[0].workspaceId).toBeNull();
});
it('rechecks current target permissions and domain registration before leaving the editor', () => {
  const { model, f, events } = setup();
  model.begin(embedding);
  model.requestSection('storage');
  f.capabilities.set({
    providers: [],
    features: [],
    domains: { structured: { installed: true, registered: false } },
  });
  model.confirmNavigation();
  expect(events).toEqual([]);
  expect(model.editing()).toEqual(embedding);
});

it('does not navigate after the target permission is revoked', () => {
  const { model, f, events } = setup();
  model.begin(embedding);
  model.requestSection('storage');
  f.context.set({
    ...f.context()!,
    tenants: [{ ...f.context()!.tenants[0], permissions: ['providers:write'] }],
  });
  model.confirmNavigation();
  expect(events).toEqual([]);
});
it('parent preserves explicit scope, but rejects foreign workspace or unregistered domain', async () => {
  const { f } = setup();
  const fixture = TestBed.createComponent(KoinonSettingsPage),
    parent = fixture.componentInstance;
  await parent.openKnowledgeSection({
    section: 'storage',
    workspaceId: 'foreign',
    domain: 'structured',
  });
  expect(parent.section()).toBe('providers');
  await parent.openKnowledgeSection({
    section: 'storage',
    workspaceId: null,
    domain: 'structured',
  });
  expect(parent.section()).toBe('storage');
  expect(parent.knowledgeIndexSelection()).toEqual({ workspaceId: '', domain: 'structured' });
  expect(parent.knowledgeScope()).toBe('');
  parent.section.set('models');
  f.capabilities.set({
    providers: [],
    features: [],
    domains: { structured: { installed: true, registered: false } },
  });
  await parent.openKnowledgeSection({
    section: 'storage',
    workspaceId: null,
    domain: 'structured',
  });
  expect(parent.section()).toBe('models');
});
it('retained selection is not reused after credential or context owner replacement', () => {
  const { f } = setup();
  const parent = TestBed.createComponent(KoinonSettingsPage).componentInstance;
  parent.rememberKnowledgeScope('workspace');
  expect(parent.knowledgeScope()).toBe('workspace');
  const clients = TestBed.inject(KoinonClientContext);
  clients.bind(
    new KoinonClient({
      transport: {
        request: async <T>() => ({}) as T,
        stream: () => {
          throw Error('Unexpected stream');
        },
      },
    }),
  );
  expect(parent.knowledgeScope()).toBe('');
  parent.rememberKnowledgeScope('workspace');
  f.context.set({ ...f.context()!, subject: 'another-owner' });
  expect(parent.knowledgeScope()).toBe('');
});

it('does not reuse an open departure confirmation after a credential replacement', () => {
  const { model, events } = setup();
  model.begin(embedding);
  model.requestSection('storage');
  TestBed.inject(KoinonClientContext).revision.update((value) => value + 1);
  model.confirmNavigation();
  expect(events).toEqual([]);
  expect(model.editing()).toEqual(embedding);
});

it('does not retain a stale scope load after the authenticated connection changes', async () => {
  const { model } = setup();
  let finish!: () => void;
  model.service.load = () =>
    new Promise<void>((resolve) => {
      finish = resolve;
    }).then(() => true);
  const scopes: string[] = [];
  model.assignmentScopeChanged.subscribe((scope) => scopes.push(scope));
  const pending = model.scopeChanged('workspace');
  TestBed.inject(KoinonClientContext).revision.update((value) => value + 1);
  finish();
  await pending;
  expect(scopes).toEqual([]);
});
it('does not retain an assignment scope absent from the current authorized workspace list', () => {
  setup();
  const parent = TestBed.createComponent(KoinonSettingsPage).componentInstance;
  parent.rememberKnowledgeScope('foreign');
  expect(parent.knowledgeScope()).toBe('');
});

it('dismisses a previous departure confirmation when assignment scope is explicitly changed', async () => {
  const { model, events } = setup();
  model.begin(embedding);
  model.requestSection('storage');
  expect(model.navigationReview()).not.toBeNull();
  await model.scopeChanged('workspace');
  expect(model.navigationReview()).toBeNull();
  model.confirmNavigation();
  expect(events).toEqual([]);
});

it('separates answer behavior from model assignments and places source processing in Operations', () => {
  const { f } = setup();
  f.context.update((value) => ({
    ...value!,
    tenants: [
      {
        ...value!.tenants[0],
        permissions: [...value!.tenants[0].permissions, 'settings:write', 'sources:configure'],
      },
    ],
  }));
  const parent = TestBed.createComponent(KoinonSettingsPage).componentInstance;
  expect(
    parent.tabsFor(parent.groups.find((group) => group.id === 'knowledge')!).map((tab) => tab.id),
  ).toEqual(['knowledge', 'providers', 'models', 'answers', 'agents', 'storage']);
  expect(
    parent.tabsFor(parent.groups.find((group) => group.id === 'operations')!).map((tab) => tab.id),
  ).toContain('sources');
});

it('does not give a connection administrator answer-policy or assistant administration', () => {
  const { f } = setup();
  f.context.update((value) => ({
    ...value!,
    tenants: [{ ...value!.tenants[0], permissions: ['providers:write'] }],
  }));
  const parent = TestBed.createComponent(KoinonSettingsPage).componentInstance;
  expect(
    parent.tabsFor(parent.groups.find((group) => group.id === 'knowledge')!).map((tab) => tab.id),
  ).toEqual(['knowledge', 'providers', 'models']);
});

it('reviews sidebar departure and preserves the exact connection draft when editing continues', async () => {
  setup();
  const parent = TestBed.createComponent(KoinonSettingsPage).componentInstance;
  parent.editor.set('provider');
  parent.providerValues = { name: 'Unsaved connection', secret: 'fixture-only-key' };
  await parent.openSection('models');
  expect(parent.section()).toBe('providers');
  expect(parent.departureReview()?.section).toBe('models');
  parent.keepSectionEditing();
  expect(parent.editor()).toBe('provider');
  expect(parent.providerValues).toEqual({ name: 'Unsaved connection', secret: 'fixture-only-key' });
  expect(parent.departureReview()).toBeNull();
});

it('requires a fresh permitted destination after departure is explicitly confirmed', async () => {
  const { f } = setup();
  const parent = TestBed.createComponent(KoinonSettingsPage).componentInstance;
  parent.editor.set('provider');
  await parent.openSection('models');
  f.context.update((value) => ({
    ...value!,
    tenants: [{ ...value!.tenants[0], permissions: ['agents:write'] }],
  }));
  await parent.confirmSectionDeparture();
  expect(parent.section()).toBe('providers');
  expect(parent.editor()).toBe('provider');
});

it('does not carry a previous identity departure decision into a replacement credential', async () => {
  setup();
  const parent = TestBed.createComponent(KoinonSettingsPage).componentInstance;
  parent.editor.set('provider');
  await parent.openSection('models');
  TestBed.inject(KoinonClientContext).revision.update((value) => value + 1);
  await parent.confirmSectionDeparture();
  expect(parent.section()).toBe('providers');
  expect(parent.departureReview()).toBeNull();
});

it('does not open a requested agent editor after the current agent record disappears', async () => {
  setup();
  const parent = TestBed.createComponent(KoinonSettingsPage).componentInstance;
  const agent = { id: 'shared', name: 'Shared assistant', description: '', provider_id: 'provider', model_id: 'model', tools: [], scope: {}, instructions: '', enabled: true, revision: 2, status: 'ready' as const, checks: [] };
  parent.c.agents.set({ items: [agent] });
  parent.editor.set('provider');
  parent.beginAgent(agent);
  expect(parent.departureReview()?.agentId).toBe('shared');
  parent.c.agents.set({ items: [] });
  await parent.confirmSectionDeparture();
  expect(parent.agentRecord()).toBeNull();
  expect(parent.editor()).toBe('provider');
  expect(parent.formError()).toContain('no longer available');
});

it('does not carry an agent departure decision across a credential replacement', async () => {
  setup();
  const parent = TestBed.createComponent(KoinonSettingsPage).componentInstance;
  const agent = { id: 'shared', name: 'Shared assistant', description: '', provider_id: 'provider', model_id: 'model', tools: [], scope: {}, instructions: '', enabled: true, revision: 2, status: 'ready' as const, checks: [] };
  parent.c.agents.set({ items: [agent] });
  parent.editor.set('provider');
  parent.beginAgent(agent);
  TestBed.inject(KoinonClientContext).revision.update(value => value + 1);
  expect(parent.departureReview()).toBeNull();
  await parent.confirmSectionDeparture();
  expect(parent.agentRecord()).toBeNull();
  expect(parent.editor()).toBe('provider');
});
