// Copyright 2026 Firefly Software Foundation
// SPDX-License-Identifier: Apache-2.0
import { TestBed } from '@angular/core/testing';
import {
  KoinonAssistant,
  KoinonFacade,
  provideKoinonClient,
} from '@fireflyframework/koinon-angular';
import {
  KoinonClient,
  type AgentConfiguration,
  type KoinonTransport,
} from '@fireflyframework/koinon-sdk';
import { KoinonChatPage } from '../../../../chat/page/src/pages/chat-page';

const agent = (): AgentConfiguration => ({
  id: 'organization-default',
  name: 'Configured reader',
  description: 'Inert lifecycle fixture',
  provider_id: 'provider',
  model_id: 'model',
  tools: [],
  scope: {},
  instructions: '',
  enabled: true,
  revision: 1,
  status: 'ready',
  checks: [],
});
const defaults = {
  tenant_id: 'tenant',
  default_agent_id: 'organization-default',
  revision: 1,
  configured: true,
  can_run: true,
  status: 'ready',
};
const unavailableFiles = {
  storage: { available: false },
  database: { available: false },
  extraction: { available: false },
  formats: [],
  limits: {},
};

function createFixture(transport: KoinonTransport) {
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
    tenants: [{ id: 'tenant', name: 'Team', roles: [], permissions: [] }],
    memberships: [],
    workspaces: [],
  });
  return {
    fixture: TestBed.createComponent(KoinonChatPage),
    assistant: TestBed.inject(KoinonAssistant),
  };
}

it('keeps the editor unavailable through delayed saved-history initialization, then sends the new draft', async () => {
  let resolveMessages!: (value: { items: unknown[] }) => void;
  const messages = new Promise<{ items: unknown[] }>((resolve) => {
    resolveMessages = resolve;
  });
  let historyRequested!: () => void;
  const historyStarted = new Promise<void>((resolve) => {
    historyRequested = resolve;
  });
  const thread = {
    id: 'saved-thread',
    title: 'Saved conversation',
    revision: 1,
    scope: {},
    title_source: 'manual',
    folder_id: null,
    archived_at: null,
    created_at: '2026-10-30T00:00:00Z',
    updated_at: '2026-10-30T00:00:00Z',
  };
  const transport: KoinonTransport = {
    request: async <T>(_method: unknown, path: string) => {
      if (path.endsWith('/messages')) {
        historyRequested();
        return (await messages) as T;
      }
      if (path.endsWith('/capabilities')) return unavailableFiles as T;
      if (path.endsWith('/chat/settings')) return defaults as T;
      if (path.endsWith('/agents')) return { items: [agent()] } as T;
      if (path.endsWith('/chat/threads')) return { items: [thread] } as T;
      return { items: [] } as T;
    },
    stream: () => {
      throw new Error('No stream should be opened');
    },
  };
  const { fixture, assistant } = createFixture(transport);
  fixture.detectChanges();
  await historyStarted;
  fixture.detectChanges();
  await Promise.resolve();
  fixture.detectChanges();
  try {
    expect(assistant.pending()).toBe(true);
    expect(fixture.nativeElement.querySelector('textarea').disabled).toBe(true);
    expect(fixture.nativeElement.querySelector('.send-button').disabled).toBe(true);
  } finally {
    resolveMessages({ items: [] });
  }
  await fixture.whenStable();
  fixture.detectChanges();
  const input = fixture.nativeElement.querySelector('textarea') as HTMLTextAreaElement;
  expect(assistant.pending()).toBe(false);
  expect(input.disabled).toBe(false);
  input.value = 'New question after history is ready';
  input.dispatchEvent(new Event('input', { bubbles: true }));
  fixture.detectChanges();
  await fixture.whenStable();
  expect(fixture.nativeElement.querySelector('.send-button').disabled).toBe(false);
  const send = vi.spyOn(assistant, 'send').mockResolvedValue(false);
  await fixture.componentInstance.submit();
  expect(send).toHaveBeenCalledWith('New question after history is ready', []);
});

it('preserves editor identity, focus and draft across same-context message and tool updates', async () => {
  const transport: KoinonTransport = {
    request: async <T>(_method: unknown, path: string) =>
      (path.endsWith('/chat/settings')
        ? defaults
        : path.endsWith('/agents')
          ? { items: [agent()] }
          : { items: [] }) as T,
    stream: () => {
      throw new Error('No stream should be opened');
    },
  };
  const { fixture, assistant } = createFixture(transport);
  fixture.detectChanges();
  await fixture.whenStable();
  fixture.detectChanges();
  const input = fixture.nativeElement.querySelector('textarea') as HTMLTextAreaElement;
  input.focus();
  input.value = 'Keep this same-context draft';
  input.dispatchEvent(new Event('input', { bubbles: true }));
  fixture.detectChanges();
  await fixture.whenStable();
  const version = assistant.contextVersion();
  assistant.toolActivity.set('Reading current evidence');
  assistant.messages.set([]);
  fixture.detectChanges();
  await fixture.whenStable();
  expect(assistant.contextVersion()).toBe(version);
  expect(fixture.nativeElement.querySelector('textarea')).toBe(input);
  expect(document.activeElement).toBe(input);
  expect(input.value).toBe('Keep this same-context draft');
  expect(fixture.componentInstance.draft).toBe(input.value);
});
