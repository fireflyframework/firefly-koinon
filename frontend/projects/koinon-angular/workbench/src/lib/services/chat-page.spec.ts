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
