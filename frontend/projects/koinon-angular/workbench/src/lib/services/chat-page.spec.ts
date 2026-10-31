// Copyright 2026 Firefly Software Foundation SPDX-License-Identifier: Apache-2.0
import { TestBed } from '@angular/core/testing';
import {
  KoinonAssistant,
  KoinonFacade,
  KoinonI18n,
  provideKoinonClient,
} from '@fireflyframework/koinon-angular';
import {
  KoinonClient,
  type AgentConfiguration,
  type KoinonTransport,
} from '@fireflyframework/koinon-sdk';
import { KoinonChatPage } from '../../../../chat/page/src/pages/chat-page';
const agent = (id: string, changes: Partial<AgentConfiguration> = {}): AgentConfiguration => ({
  id,
  name: id,
  description: 'Operator configuration',
  provider_id: 'provider',
  model_id: 'model',
  tools: [],
  scope: {},
  instructions: '',
  enabled: true,
  revision: 1,
  status: 'ready',
  checks: [],
  ...changes,
});
async function mount(
  agents: AgentConfiguration[],
  options: {
    override?: string;
    configure?: boolean;
    spanish?: boolean;
    action?: boolean;
    output?: boolean;
    defaultId?: string | null;
  } = {},
) {
  const transport: KoinonTransport = {
    request: async <T>(_method: unknown, path: string) =>
      (path.endsWith('/chat/settings')
        ? {
            tenant_id: 'tenant',
            default_agent_id:
              options.defaultId === undefined ? (agents[0]?.id ?? null) : options.defaultId,
            revision: 1,
            configured: options.defaultId !== null,
            can_run: options.defaultId !== null,
            status: 'ready',
          }
        : path.endsWith('/agents')
          ? { items: agents }
          : { items: [] }) as T,
    stream: () => {
      throw new Error('Unexpected stream');
    },
  };
  TestBed.configureTestingModule({
    imports: [KoinonChatPage],
    providers: [
      KoinonAssistant,
      KoinonFacade,
      ...provideKoinonClient(new KoinonClient({ transport }), transport),
    ],
  });
  const facade = TestBed.inject(KoinonFacade);
  facade.tenantId.set('tenant');
  facade.context.set({
    subject: 'reader',
    tenants: [
      {
        id: 'tenant',
        name: 'Team',
        roles: [],
        permissions: options.configure ? ['agents:write'] : [],
      },
    ],
    memberships: [],
    workspaces: [],
  });
  if (options.spanish)
    TestBed.inject(KoinonI18n).apply({
      locale: 'es-ES',
      response_language: 'es',
      time_zone: 'UTC',
    });
  const fixture = TestBed.createComponent(KoinonChatPage);
  const setup = vi.fn();
  if (options.output) fixture.componentInstance.setupRequested.subscribe(setup);
  if (options.override || options.action)
    fixture.componentRef.setInput('actions', {
      agentId: () => options.override ?? '',
      setup,
      citation: () => undefined,
      resource: () => undefined,
    });
  fixture.detectChanges();
  await fixture.whenStable();
  fixture.detectChanges();
  return { fixture, assistant: TestBed.inject(KoinonAssistant), setup };
}
it('speaks to koinon without an agent picker and uses the configured organization default', async () => {
  const { fixture, assistant } = await mount(
    [
      agent('disabled', { enabled: false, status: 'disabled', can_run: false }),
      agent('first-runnable', { status: 'unverified', can_run: true }),
      agent('other-ready'),
    ],
    { defaultId: 'first-runnable' },
  );
  expect(assistant.agentId()).toBe('first-runnable');
  expect(fixture.nativeElement.querySelector('#chat-agent')).toBeNull();
  expect(fixture.nativeElement.querySelector('.trial-notice')).toBeNull();
  expect(fixture.nativeElement.querySelector('.send-button').getAttribute('aria-label')).toBe(
    'Send',
  );
  expect(fixture.nativeElement.querySelector('textarea').placeholder).toBe('Ask koinon…');
});
it('preserves an explicit host operator agent override without adding a picker', async () => {
  const { fixture, assistant } = await mount([agent('first'), agent('operator-choice')], {
    override: 'operator-choice',
    defaultId: null,
  });
  expect(assistant.agentId()).toBe('operator-choice');
  expect(fixture.nativeElement.querySelector('#chat-agent')).toBeNull();
});
it('waits for the conversation context before accepting a draft and enables Send afterward', async () => {
  const { fixture, assistant } = await mount([agent('organization-default')]);
  let input = fixture.nativeElement.querySelector('textarea') as HTMLTextAreaElement;
  let send = fixture.nativeElement.querySelector('.send-button') as HTMLButtonElement;
  assistant.pending.set(true);
  fixture.detectChanges();
  await fixture.whenStable();
  fixture.detectChanges();
  expect(input.disabled).toBe(true);
  expect(send.disabled).toBe(true);
  assistant.contextVersion.update((version) => version + 1);
  fixture.detectChanges();
  assistant.pending.set(false);
  fixture.detectChanges();
  await fixture.whenStable();
  input = fixture.nativeElement.querySelector('textarea') as HTMLTextAreaElement;
  send = fixture.nativeElement.querySelector('.send-button') as HTMLButtonElement;
  input.value = 'Who owns the review?';
  input.dispatchEvent(new Event('input', { bubbles: true }));
  fixture.detectChanges();
  await fixture.whenStable();
  expect(input.disabled).toBe(false);
  expect(fixture.componentInstance.draft).toBe('Who owns the review?');
  expect(send.disabled).toBe(false);
});
it('clears both the visible editor and its draft when the knowledge context changes', async () => {
  const { fixture, assistant } = await mount([agent('organization-default')]);
  const input = fixture.nativeElement.querySelector('textarea') as HTMLTextAreaElement;
  input.value = 'Question for the previous space';
  input.dispatchEvent(new Event('input', { bubbles: true }));
  fixture.detectChanges();
  await fixture.whenStable();
  expect(fixture.componentInstance.draft).toBe(input.value);
  assistant.contextVersion.update((version) => version + 1);
  fixture.detectChanges();
  await fixture.whenStable();
  fixture.detectChanges();
  expect(fixture.componentInstance.draft).toBe('');
  expect(fixture.nativeElement.querySelector('textarea').value).toBe('');
});
it('clears visible input when typing and a context change occur before the same render', async () => {
  const { fixture, assistant } = await mount([agent('organization-default')]);
  const input = fixture.nativeElement.querySelector('textarea') as HTMLTextAreaElement;
  input.value = 'Question for the previous space';
  input.dispatchEvent(new Event('input', { bubbles: true }));
  assistant.contextVersion.update((version) => version + 1);
  fixture.detectChanges();
  await fixture.whenStable();
  fixture.detectChanges();
  expect(fixture.componentInstance.draft).toBe('');
  expect(fixture.nativeElement.querySelector('textarea').value).toBe('');
  expect(fixture.nativeElement.querySelector('.send-button').disabled).toBe(true);
});
it('keeps the same draft and editor while the current conversation status changes', async () => {
  const { fixture, assistant } = await mount([agent('organization-default')]);
  const input = fixture.nativeElement.querySelector('textarea') as HTMLTextAreaElement;
  input.value = 'A follow-up for this space';
  input.dispatchEvent(new Event('input', { bubbles: true }));
  fixture.detectChanges();
  await fixture.whenStable();
  assistant.pending.set(true);
  fixture.detectChanges();
  await fixture.whenStable();
  assistant.pending.set(false);
  fixture.detectChanges();
  await fixture.whenStable();
  expect(fixture.nativeElement.querySelector('textarea')).toBe(input);
  expect(input.value).toBe('A follow-up for this space');
  expect(fixture.nativeElement.querySelector('.send-button').disabled).toBe(false);
});
it('explains unavailable chat in Spanish without exposing readiness or provider checks to readers', async () => {
  const { fixture } = await mount(
    [
      agent('disabled', {
        enabled: false,
        can_run: false,
        status: 'disabled',
        checks: [
          { id: 'provider', status: 'failed', message: 'Technical provider dependency failure' },
        ],
      }),
    ],
    { spanish: true, action: true },
  );
  expect(fixture.nativeElement.textContent).toContain('koinon no está disponible en este momento');
  expect(fixture.nativeElement.textContent).not.toContain('Technical provider');
  expect(fixture.nativeElement.textContent).not.toContain('Configurar koinon');
});
it('offers configuration only to authorized operators with a working setup action', async () => {
  const { fixture, setup } = await mount([], { configure: true, action: true });
  const button = [...fixture.nativeElement.querySelectorAll('button')].find((item) =>
    (item as HTMLButtonElement).textContent?.includes('Configure koinon'),
  ) as HTMLButtonElement;
  expect(button).toBeDefined();
  button.click();
  expect(setup).toHaveBeenCalledTimes(1);
});
it('does not offer a configuration action without a host handler', async () => {
  const { fixture } = await mount([], { configure: true });
  expect(fixture.nativeElement.textContent).not.toContain('Configure koinon');
});

it('preserves the setup output for authorized embedded hosts', async () => {
  const { fixture, setup } = await mount([], { configure: true, output: true });
  const button = [...fixture.nativeElement.querySelectorAll('button')].find((item) =>
    (item as HTMLButtonElement).textContent?.includes('Configure koinon'),
  ) as HTMLButtonElement;
  expect(button).toBeDefined();
  button.click();
  expect(setup).toHaveBeenCalledTimes(1);
});

it('offers a reviewed knowledge action for one completed assistant reply to an authorized author', async () => {
  const { fixture, assistant } = await mount([agent('ready')]);
  const facade = TestBed.inject(KoinonFacade);
  facade.context.update((context) => context && ({
    ...context,
    tenants: context.tenants.map((tenant) => ({
      ...tenant,
      permissions: ['chat:use', 'catalog:read', 'catalog:write', 'ingest:write'],
    })),
  }));
  await fixture.whenStable();
  assistant.threadId.set('selected-thread');
  assistant.messages.set([{
    id: 'selected-answer', role: 'assistant', text: 'The reviewed threshold is 47.',
    status: 'completed', citations: [], artifacts: [], created_at: '2026-10-31T00:00:00Z',
  }]);
  fixture.detectChanges();
  expect([...fixture.nativeElement.querySelectorAll('button')].some((button) =>
    (button as HTMLButtonElement).textContent?.trim() === 'Save as knowledge',
  )).toBe(true);
});

it('offers curation to a workspace-scoped author in the active chat without tenant write permissions', async () => {
  const { fixture, assistant } = await mount([agent('ready')]);
  const facade = TestBed.inject(KoinonFacade);
  facade.context.update((context) => context && ({
    ...context,
    tenants: context.tenants.map((tenant) => ({ ...tenant, permissions: ['chat:use', 'catalog:read'] })),
    workspaces: [{ id: 'w', tenant_id: 'tenant', kind: 'workspace', parent_id: null, workspace_id: 'w', project_id: null, name: 'Owned space', status: 'ready', description: '', metadata: {}, created_at: '2026-10-31T00:00:00Z' }],
    workspace_permissions: { w: ['chat:use', 'catalog:read', 'catalog:write', 'ingest:write'] },
  }));
  await fixture.whenStable();
  await assistant.selectThread('thread', { id: 'thread', title: 'Owned conversation', title_source: 'manual', revision: 1, folder_id: null, archived_at: null, scope: { workspace_id: 'w' }, created_at: '2026-10-31T00:00:00Z', updated_at: '2026-10-31T00:00:00Z' });
  assistant.messages.set([{ id: 'reply', role: 'assistant', text: 'Reviewed fact.', status: 'completed', citations: [], artifacts: [], created_at: '2026-10-31T00:00:00Z' }]);
  fixture.detectChanges();
  expect(facade.tenantPermissions().has('catalog:write')).toBe(false);
  expect(fixture.componentInstance.canArtifact('knowledge')).toBe(true);
});
