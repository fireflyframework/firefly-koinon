// Copyright 2026 Firefly Software Foundation SPDX-License-Identifier: Apache-2.0
// Controlled HTTP fixtures qualify organization selection and wire requests, not a live model.
import { expect, test, type Page } from '@playwright/test';
import { mkdir } from 'node:fs/promises';
import { resolve } from 'node:path';
import { openAdministration, mockService } from './fixtures';
async function setup(
  page: Page,
  options: {
    defaultId?: string | null;
    disabled?: boolean;
    conflict?: boolean;
    spanish?: boolean;
    memory?: boolean;
  } = {},
) {
  await mockService(page);
  let defaultId = options.defaultId === undefined ? 'second' : options.defaultId;
  let revision = 4,
    submitted = false;
  const writes: unknown[] = [],
    submittedAgents: string[] = [];
  let memory = {
    allow_project_memory: true,
    max_history_messages: 30,
    max_history_tokens: 4096,
    max_project_memory_messages: 12,
  };
  const agent = (id: string, name: string, scope = {}) => ({
    id,
    name,
    description: 'Controlled organization configuration',
    provider_id: 'provider',
    model_id: 'fixture-model',
    tools: [],
    scope,
    instructions: '',
    enabled: !(options.disabled && id === 'second'),
    configured: true,
    can_run: !(options.disabled && id === 'second'),
    status: options.disabled && id === 'second' ? 'disabled' : 'ready',
    revision: 1,
    checks: [],
  });
  const agents = [
    agent('first', 'First available agent'),
    agent('second', 'Organization guide'),
    agent('project-only', 'Project agent', { workspace_id: 'workspace-one' }),
  ];
  const settings = () => ({
    tenant_id: 'tenant-one',
    default_agent_id: defaultId,
    revision,
    configured: !!defaultId,
    ...(options.memory ? { memory } : {}),
    can_run: !!defaultId && !(options.disabled && defaultId === 'second'),
    status: !defaultId
      ? 'unconfigured'
      : options.disabled && defaultId === 'second'
        ? 'disabled'
        : 'ready',
  });
  const thread = {
    id: 'organization-thread',
    title: 'Organization question',
    title_source: 'manual',
    revision: 1,
    folder_id: null,
    archived_at: null,
    scope: {},
    created_at: '2026-10-28T10:00:00Z',
    updated_at: '2026-10-28T10:00:00Z',
  };
  if (options.spanish)
    await page.route('**/bff/api/v1/profile', (route) =>
      route.fulfill({
        json: {
          subject: 'synthetic.reviewer',
          display_name: 'Alex Rivera',
          locale: 'es-ES',
          time_zone: 'UTC',
          response_language: 'es',
          avatar_url: null,
          avatar_version: null,
        },
      }),
    );
  await page.route('**/bff/api/v1/tenants/*/**', async (route) => {
    const request = route.request(),
      path = new URL(request.url()).pathname;
    const json = (value: unknown, status = 200) => route.fulfill({ json: value, status });
    if (path.endsWith('/chat/settings')) {
      if (request.method() === 'PUT') {
        const body = request.postDataJSON();
        writes.push(body);
        if (options.conflict || body.expected_revision !== revision)
          return json(
            {
              detail: 'Organization chat settings changed. Reload and try again.',
              code: 'ORGANIZATION_CHAT_CHANGED',
            },
            409,
          );
        defaultId = body.default_agent_id;
        if (body.memory) memory = { ...memory, ...body.memory };
        ++revision;
      }
      return json(settings());
    }
    if (path.endsWith('/agents'))
      return json({ items: agents, page: 1, pages: 1, total: agents.length });
    if (path.endsWith('/chat/threads'))
      return json(
        request.method() === 'POST' ? thread : { items: [], page: 1, pages: 0, total: 0 },
      );
    if (path.endsWith('/chat/threads/organization-thread')) return json(thread);
    if (path.endsWith('/messages'))
      return json({
        items: submitted
          ? [
              {
                id: 'answer',
                role: 'assistant',
                run_id: 'organization-run',
                text: 'Controlled answer from the organization guide.',
                status: 'completed',
                citations: [],
                artifacts: [],
                created_at: '2026-10-28T10:00:01Z',
              },
            ]
          : [],
      });
    if (path.endsWith('/runs')) {
      submitted = true;
      submittedAgents.push(request.postDataJSON().agent_id);
      return json({ run_id: 'organization-run', message_id: 'answer' });
    }
    return route.fallback();
  });
  return { writes, submittedAgents };
}
async function navigate(page: Page, label: string) {
  if (label === 'Settings' || label === 'Configuración') {
    await openAdministration(page, label);
    return;
  }
  const menu = page.getByRole('button', { name: 'Open navigation', exact: true });
  if ((page.viewportSize()?.width ?? 1440) < 700) {
    await expect(menu).toBeVisible();
    await menu.click();
  }
  await page.getByRole('button', { name: label, exact: true }).click();
}
async function openAgents(page: Page, spanish = false) {
  await page.goto('/library');
  await navigate(page, spanish ? 'Configuración' : 'Settings');
  await expect(page.locator('ffk-settings-page')).toBeVisible();
  const mobile = page.getByRole('combobox', {
    name: spanish ? 'Sección de configuración' : 'Settings section',
    exact: true,
  });
  if (await mobile.isVisible()) await mobile.selectOption('agents');
  else
    await page.getByRole('button', { name: spanish ? 'Agentes' : 'Agents', exact: true }).click();
}
for (const width of [1440, 390])
  for (const theme of ['light', 'dark'])
    test(`organization memory policy fits ${width} ${theme} and needs an explicit save`, async ({
      page,
    }) => {
      await page.setViewportSize({ width, height: 1000 });
      await page.addInitScript((theme) => localStorage.setItem('koinon-theme', theme), theme);
      const service = await setup(page, { memory: true });
      await openAgents(page);
      const editor = page.locator('ffk-organization-chat-settings');
      const permission = editor.getByRole('checkbox', { name: /Allow personal project memory/ });
      await expect(permission).toBeChecked();
      const total = editor.getByRole('spinbutton', { name: 'Total history messages', exact: true });
      await expect(total).toHaveValue('30');
      await editor
        .getByRole('spinbutton', { name: 'Messages from other project chats', exact: true })
        .fill('31');
      await expect(
        editor.getByRole('button', { name: 'Save organization chat', exact: true }),
      ).toBeDisabled();
      await expect(editor.getByRole('status')).toHaveText(
        'Project memory cannot exceed the total history limit.',
      );
      expect(service.writes).toHaveLength(0);
      await editor
        .getByRole('spinbutton', { name: 'Messages from other project chats', exact: true })
        .fill('12');
      await permission.uncheck();
      expect(service.writes).toHaveLength(0);
      const output = process.env['KOINON_UI_CAPTURE_DIR'] ?? 'test-results/organization-memory';
      await mkdir(output, { recursive: true });
      await editor.screenshot({
        path: resolve(output, `organization-memory-${width}-${theme}.png`),
        animations: 'disabled',
      });
      expect(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth)).toBe(
        true,
      );
      await editor.getByRole('button', { name: 'Save organization chat', exact: true }).click();
      await expect(editor.getByRole('status')).toHaveText('Organization chat saved.');
      expect(service.writes).toEqual([
        {
          default_agent_id: 'second',
          expected_revision: 4,
          memory: {
            allow_project_memory: false,
            max_history_messages: 30,
            max_history_tokens: 4096,
            max_project_memory_messages: 12,
          },
        },
      ]);
    });
for (const width of [1440, 390])
  test(`organization agent is configured once and a fresh standard chat uses it at ${width}px`, async ({
    page,
  }) => {
    await page.setViewportSize({ width, height: 1000 });
    const service = await setup(page, { defaultId: null });
    await openAgents(page);
    const editor = page.locator('ffk-organization-chat-settings');
    await expect(
      editor.getByRole('combobox', { name: 'Organization chat agent', exact: true }),
    ).toHaveValue('');
    await expect(editor.locator('option')).toHaveCount(3);
    await editor
      .getByRole('combobox', { name: 'Organization chat agent', exact: true })
      .selectOption('second');
    await editor.getByRole('button', { name: 'Save organization chat', exact: true }).click();
    await expect(editor.getByRole('status')).toContainText('Organization chat saved.');
    expect(service.writes).toEqual([{ default_agent_id: 'second', expected_revision: 4 }]);
    const output =
      process.env['KOINON_UI_CAPTURE_DIR'] ??
      resolve(process.cwd(), '.qualification-v23/organization-chat-captures');
    await mkdir(output, { recursive: true });
    await page.screenshot({
      path: resolve(output, `organization-agent-${width}.png`),
      animations: 'disabled',
    });
    await navigate(page, 'Chat');
    await expect(page.locator('ffk-chat-page #chat-agent')).toHaveCount(0);
    await page
      .getByRole('textbox', { name: 'Message koinon', exact: true })
      .fill('Use the organization guide.');
    await page.getByRole('button', { name: 'Send', exact: true }).click();
    await expect(
      page.getByText('Controlled answer from the organization guide.', { exact: true }),
    ).toBeVisible();
    expect(service.submittedAgents).toEqual(['second']);
    await page.screenshot({
      path: resolve(output, `organization-chat-${width}.png`),
      animations: 'disabled',
    });
  });
for (const [label, settings] of [
  ['missing', { defaultId: null }],
  ['disabled', { disabled: true }],
] as const)
  test(`standard chat remains unavailable for a ${label} organization default without selecting another agent`, async ({
    page,
  }) => {
    const service = await setup(page, settings);
    await page.goto('/library');
    await navigate(page, 'Chat');
    await expect(
      page.getByRole('heading', { name: 'koinon is unavailable right now.', exact: true }),
    ).toBeVisible();
    await page
      .getByRole('textbox', { name: 'Message koinon', exact: true })
      .fill('Do not substitute another agent.');
    await expect(page.getByRole('button', { name: 'Send', exact: true })).toBeDisabled();
    expect(service.submittedAgents).toEqual([]);
  });
test('clearing the organization setting preserves explicit Settings agent trials', async ({
  page,
}) => {
  const service = await setup(page);
  await openAgents(page);
  const editor = page.locator('ffk-organization-chat-settings');
  await editor
    .getByRole('combobox', { name: 'Organization chat agent', exact: true })
    .selectOption('');
  await editor.getByRole('button', { name: 'Save organization chat', exact: true }).click();
  await expect(editor.getByRole('status')).toContainText('Organization chat saved.');
  expect(service.writes).toEqual([{ default_agent_id: null, expected_revision: 4 }]);
  await page
    .locator('.agent-list article')
    .filter({ hasText: 'Organization guide' })
    .getByRole('button', { name: 'Open chat', exact: true })
    .click();
  await page
    .getByRole('textbox', { name: 'Message koinon', exact: true })
    .fill('Explicit operator trial.');
  await page.getByRole('button', { name: 'Send', exact: true }).click();
  await expect(
    page.getByText('Controlled answer from the organization guide.', { exact: true }),
  ).toBeVisible();
  expect(service.submittedAgents).toEqual(['second']);
});
test('organization setting conflicts require reload and Spanish labels remain localized', async ({
  page,
}) => {
  await setup(page, { conflict: true, spanish: true });
  await openAgents(page, true);
  const editor = page.locator('ffk-organization-chat-settings');
  await expect(
    editor.getByRole('heading', { name: 'Chat de la organización', exact: true }),
  ).toBeVisible();
  await editor
    .getByRole('combobox', { name: 'Agente del chat de la organización', exact: true })
    .selectOption('first');
  await editor
    .getByRole('button', { name: 'Guardar el chat de la organización', exact: true })
    .click();
  await expect(editor.getByRole('alert')).toContainText(
    'Recarga la configuración antes de volver a guardar.',
  );
  await expect(
    editor.getByRole('button', { name: 'Guardar el chat de la organización', exact: true }),
  ).toBeDisabled();
  await editor
    .getByRole('button', { name: 'Recargar el chat de la organización', exact: true })
    .click();
  await expect(
    editor.getByRole('combobox', { name: 'Agente del chat de la organización', exact: true }),
  ).toHaveValue('second');
});
