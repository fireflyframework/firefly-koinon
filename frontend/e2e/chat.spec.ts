// Copyright 2026 Firefly Software Foundation SPDX-License-Identifier: Apache-2.0
import { test, expect, type Page } from '@playwright/test';
import { mockService, context as baseContext } from './fixtures';
import { mkdir, writeFile } from 'node:fs/promises';
import { resolve } from 'node:path';
import { createHash } from 'node:crypto';
const program =
  'root = KnowledgeAnswer([table, chart, document, schema, flow, cites])\ntable = Evidence("r-query", "table")\nchart = Evidence("r-query", "chart")\ndocument = Evidence("r-search", "document")\nschema = Evidence("r-schema", "schema")\nflow = Evidence("r-lineage", "lineage")\ncites = Evidence("r-search", "citations")';
async function assistantFixture(
  page: Page,
  options: {
    malicious?: boolean;
    denied?: boolean;
    audit?: boolean;
    multipleAgents?: boolean;
    answerActions?: boolean;
  } = {},
) {
  await mockService(page, { organizationAgent: 'agent-one' });
  if (options.audit)
    await page.route('**/bff/api/v1/context', (route) =>
      route.fulfill({
        json: {
          ...baseContext,
          tenants: baseContext.tenants.map((tenant, index) =>
            index === 0
              ? {
                  ...tenant,
                  permissions: [
                    ...tenant.permissions,
                    'evidence:read',
                    ...(options.answerActions
                      ? ['exports:read', 'exports:write', 'shares:read', 'shares:write']
                      : []),
                  ],
                }
              : tenant,
          ),
        },
      }),
    );
  let sent = false,
    completed = false;
  const resultReads: string[] = [];
  const submittedAgents: string[] = [];
  const artifact = {
    id: 'artifact',
    kind: 'openui',
    run_id: 'run-one',
    language: options.malicious
      ? 'root = KnowledgeAnswer([x])\nx = Html("<img src=x onerror=window.owned=true>")'
      : program,
    complete: true,
  };
  const citation = {
    title: 'Service operating policy.pdf',
    document_id: 'document-one',
    text: 'The service owner maintains the documented review.',
    page: 3,
  };
  const statement = 'SELECT region, COUNT(*) AS count FROM service_activity GROUP BY region';
  const fingerprint = createHash('sha256').update(citation.text).digest('hex');
  const auditSources = [
    {
      id: 'policy-passage',
      asset_id: 'document-one',
      source_id: 'source-one',
      chunk_id: 'chunk-one',
      kind: 'document',
      title: citation.title,
      page: 3,
      quote: citation.text,
      used_revision: 'chunk-sha256:' + fingerprint,
      current_revision: 'chunk-sha256:' + fingerprint,
      availability: 'available',
    },
    {
      id: 'service-table',
      asset_id: 'dataset-one',
      kind: 'dataset',
      title: 'Quarterly service activity',
      query_id: 'q',
      snapshot_id: 'snapshot-one',
      used_revision: 'snapshot-one',
      current_revision: 'snapshot-one',
      availability: 'available',
    },
  ];
  const activities = [
    {
      call_id: 'query-call',
      tool_name: 'query_dataset',
      status: 'completed',
      occurred_at: '2026-10-26T10:00:01Z',
      duration_ms: 180,
      summary: 'Read 2 returned rows',
      result_id: 'r-query',
    },
    {
      call_id: 'source-call',
      tool_name: 'search_knowledge',
      status: 'completed',
      occurred_at: '2026-10-26T10:00:01Z',
      duration_ms: 90,
      summary: 'Read an accessible policy passage',
      result_id: 'r-search',
    },
  ];
  const threadView = () => ({
    id: 'thread-one',
    title: completed ? 'Service review' : 'New conversation',
    title_source: completed ? 'ai' : 'default',
    revision: completed ? 2 : 1,
    folder_id: null,
    archived_at: null,
    scope: {},
    created_at: '2026-10-26T10:00:00Z',
    updated_at: '2026-10-26T10:00:00Z',
  });
  await page.route('**/bff/api/v1/tenants/*/**', async (route) => {
    const path = new URL(route.request().url()).pathname;
    const json = (body: unknown, status = 200) =>
      route.fulfill({ status, contentType: 'application/json', body: JSON.stringify(body) });
    if (path.endsWith('/chat/runs/run-one/audit'))
      return json({
        run_id: 'run-one',
        provenance_status: options.audit ? 'recorded' : 'not_recorded',
        source_provenance_complete: options.audit ? true : null,
        generations: options.audit
          ? [
              {
                id: 'generation-one',
                start_sequence: 0,
                agent_id: 'agent-one',
                agent_revision: 1,
                provider_id: 'provider-one',
                provider_revision: 2,
                provider_kind: 'ollama',
                model_id: 'fixture-local',
                model_class: 'OpenAIChatModel',
                api: 'chat',
                started_at: '2026-10-26T10:00:00Z',
                finished_at: '2026-10-26T10:00:02Z',
                status: 'completed',
              },
            ]
          : [],
        sources: options.audit ? auditSources : [],
        private_files: [],
        native_reads: [],
        sql_attempts: [],
      });
    if (options.audit && path.endsWith('/evidence/conversations'))
      return json({
        revision: 'a'.repeat(64),
        complete: true,
        omissions: [],
        sources: auditSources,
      });
    if (path.endsWith('/chat/runs/run-one/activity'))
      return json({
        items: activities,
        page: 1,
        page_size: 25,
        total: activities.length,
        pages: 1,
      });
    if (path.endsWith('/agents'))
      return json({
        items: [
          ...(options.multipleAgents
            ? [
                {
                  id: 'disabled-agent',
                  name: 'Disabled configuration',
                  enabled: false,
                  can_run: false,
                  status: 'disabled',
                  checks: [],
                },
                {
                  id: 'other-agent',
                  name: 'Other configuration',
                  enabled: true,
                  status: 'ready',
                  checks: [],
                },
              ]
            : []),
          {
            id: 'agent-one',
            name: 'Research assistant',
            description: 'Controlled service fixture',
            provider_id: 'provider-one',
            model_id: 'fixture-local',
            tools: ['search_knowledge', 'inspect_schema', 'query_dataset'],
            scope: {},
            instructions: '',
            enabled: true,
            revision: 1,
            status: options.multipleAgents ? 'unverified' : 'ready',
            can_run: true,
            checks: [],
          },
        ],
      });
    if (path.endsWith('/chat/threads'))
      return route.request().method() === 'POST'
        ? json(threadView())
        : json({
            items: sent ? [threadView()] : [],
            total: sent ? 1 : 0,
            page: 1,
            page_size: 25,
            pages: sent ? 1 : 0,
          });
    if (path.endsWith('/chat/threads/thread-one')) return json(threadView());
    if (path.endsWith('/messages'))
      return json({
        items: sent
          ? [
              {
                id: 'question',
                role: 'user',
                text: 'Compare service activity by region and show the policy source.',
                status: 'completed',
                citations: [],
                artifacts: [],
                created_at: '2026-10-26T10:00:00Z',
              },
              {
                id: 'answer',
                role: 'assistant',
                run_id: 'run-one',
                presentation: { locale: 'en-US', time_zone: 'UTC', response_language: 'en' },
                ...(options.audit
                  ? {
                      answer_policy: {
                        outcome: 'grounded',
                        reason:
                          'The response used a recorded policy passage and a completed query over service activity.',
                      },
                    }
                  : {}),
                tool_activities: completed ? activities : [],
                tool_activity_count: completed ? 2 : 0,
                tool_activity_has_more: false,
                text: completed
                  ? 'North has 18 service cases; South has 12. The policy assigns review to the service owner.'
                  : '',
                status: completed ? 'completed' : 'queued',
                citations: completed ? [citation] : [],
                artifacts: completed ? [artifact] : [],
                created_at: '2026-10-26T10:00:01Z',
              },
            ]
          : [],
      });
    if (path.endsWith('/runs')) {
      submittedAgents.push(route.request().postDataJSON().agent_id);
      sent = true;
      return json({ run_id: 'run-one', message_id: 'answer', event_cursor: '0' });
    }
    if (path.endsWith('/events')) {
      completed = true;
      const events = [
        ['tool_activity', { message: 'Reading selected sources' }],
        [
          'message_delta',
          {
            text: 'North has 18 service cases; South has 12. The policy assigns review to the service owner.',
          },
        ],
        ['openui_delta', { artifact }],
        ['citation', { citation }],
        ['completed', { status: 'completed' }],
      ];
      return route.fulfill({
        status: 200,
        contentType: 'text/event-stream',
        body: events
          .map(
            ([type, data], i) => `id: ${i + 1}\nevent: ${type}\ndata: ${JSON.stringify(data)}\n\n`,
          )
          .join(''),
      });
    }
    if (path.includes('/results/')) {
      const id = path.split('/').pop()!;
      resultReads.push(id);
      if (options.denied)
        return json({ code: 'FORBIDDEN', detail: 'This source is no longer accessible' }, 403);
      const result =
        id === 'r-query'
          ? {
              kind: 'query',
              data: {
                query_id: 'q',
                execution_status: 'OK',
                preview: [
                  { region: 'North', count: 18 },
                  { region: 'South', count: 12 },
                ],
                row_count: 2,
                chart_hint: 'bar',
                sql: statement,
              },
            }
          : id === 'r-schema'
            ? {
                kind: 'schema',
                data: {
                  tables: [
                    {
                      id: 't',
                      name: 'service_activity',
                      columns: [
                        {
                          id: 'c',
                          name: 'region',
                          data_type: 'VARCHAR',
                          description: 'Service region',
                        },
                      ],
                    },
                  ],
                },
              }
            : id === 'r-lineage'
              ? {
                  kind: 'lineage',
                  data: {
                    nodes: [
                      { id: 'source-one', label: 'Policy source', kind: 'source' },
                      { id: 'document-one', label: 'Service policy', kind: 'document' },
                    ],
                    edges: [{ source: 'source-one', target: 'document-one', label: 'produces' }],
                  },
                }
              : {
                  kind: 'search',
                  data: {
                    hits: [
                      {
                        id: 'hit',
                        title: 'Service operating policy.pdf',
                        text: 'The service owner maintains the documented review.',
                        asset_id: 'document-one',
                      },
                    ],
                    citations: [citation],
                  },
                };
      return json({ id, run_id: 'run-one', ...result });
    }
    return route.fallback();
  });
  return { resultReads, submittedAgents };
}
async function ask(page: Page) {
  await page.goto('/library');
  await expect(page.locator('ffk-shell .topbar')).toBeVisible();
  const menu = page.getByRole('button', { name: 'Open navigation', exact: true });
  if (await menu.isVisible()) await menu.click();
  await page.getByRole('button', { name: 'Chat', exact: true }).click();
  await page
    .getByRole('textbox', { name: 'Message koinon' })
    .fill('Compare service activity by region and show the policy source.');
  await page.getByRole('button', { name: 'Send', exact: true }).click();
  await expect(
    page.getByText(
      'North has 18 service cases; South has 12. The policy assigns review to the service owner.',
      { exact: true },
    ),
  ).toBeVisible();
  await expect(page.getByRole('heading', { name: 'Service review', exact: true })).toBeVisible();
  await expect(page.locator('.chat-error')).toHaveCount(0);
}
test('persists a question and renders registered Angular evidence from authorized result records', async ({
  page,
}) => {
  const service = await assistantFixture(page);
  await ask(page);
  await expect(page.getByRole('cell', { name: 'North', exact: true })).toBeVisible();
  await expect(page.getByRole('heading', { name: 'Query results', exact: true })).toHaveCount(1);
  await expect(page.getByRole('heading', { name: 'Source evidence', exact: true })).toHaveCount(0);
  await expect(page.getByRole('img', { name: 'count by region' })).toHaveCount(0);
  const view = page.getByRole('group', { name: 'Result view', exact: true });
  await expect(view.getByRole('button', { name: 'Table', exact: true })).toHaveAttribute(
    'aria-pressed',
    'true',
  );
  const reads = service.resultReads.length;
  await view.getByRole('button', { name: 'Chart', exact: true }).click();
  await expect(page.getByRole('img', { name: 'count by region' })).toBeVisible();
  await expect(page.getByRole('cell', { name: 'North', exact: true })).toHaveCount(0);
  await view.getByRole('button', { name: 'Table', exact: true }).click();
  await expect(page.getByRole('cell', { name: 'North', exact: true })).toBeVisible();
  expect(service.resultReads.length).toBe(reads);
  await expect(page.getByRole('heading', { name: 'Dataset schema', exact: true })).toHaveCount(0);
  await expect(page.getByRole('heading', { name: 'Knowledge lineage', exact: true })).toHaveCount(
    0,
  );
  await expect(page.getByRole('button', { name: 'Open document', exact: true })).toHaveCount(0);
  await expect(page.getByRole('button', { name: 'Audit', exact: true })).toBeVisible();
  expect(service.resultReads).toEqual(['r-query']);
});
test('rejects unregistered model components without executing or requesting evidence', async ({
  page,
}) => {
  const service = await assistantFixture(page, { malicious: true });
  await ask(page);
  await expect(page.getByText('This answer contains an unsupported evidence view.')).toBeVisible();
  expect(service.resultReads).toHaveLength(0);
  expect(await page.evaluate(() => 'owned' in window)).toBe(false);
});
test('preserves denied evidence without substituting sample rows', async ({ page }) => {
  await assistantFixture(page, { denied: true });
  await ask(page);
  await expect(page.getByText('This source is no longer accessible').first()).toBeVisible();
  await expect(page.getByRole('cell', { name: 'North', exact: true })).toHaveCount(0);
});

test('captures the current chat and OpenUI review at desktop and mobile sizes', async ({
  page,
}) => {
  await assistantFixture(page);
  await ask(page);
  await expect(page.getByRole('cell', { name: 'North', exact: true })).toBeVisible();
  const output = resolve(process.cwd(), '../../../outputs');
  await mkdir(output, { recursive: true });
  await page.addStyleTag({
    content: 'ffk-workbench{--koinon-workspace-height:calc(100dvh - 22px)}',
  });
  await page.evaluate(() => {
    const label = document.createElement('div');
    label.textContent = 'Controlled service fixtures, Chat and OpenUI review';
    Object.assign(label.style, {
      position: 'fixed',
      inset: 'auto 0 0',
      height: '22px',
      background: '#855414',
      color: '#fff',
      font: '11px/22px system-ui',
      textAlign: 'center',
      zIndex: '9999',
    });
    document.body.append(label);
  });
  for (const width of [1440, 390]) {
    await page.setViewportSize({ width, height: 1000 });
    await page.getByRole('heading', { name: 'Chat', exact: true }).scrollIntoViewIfNeeded();
    await page.locator('.conversation-scroll').evaluate((node) => {
      node.scrollTop = 0;
    });
    await page.screenshot({
      path: resolve(output, `koinon-chat-bubbles-${width}.png`),
      animations: 'disabled',
    });
    await page.locator('.conversation-scroll').evaluate((node) => {
      node.scrollTop = node.scrollHeight;
    });
    await page.screenshot({
      path: resolve(output, `koinon-openui-bubbles-${width}.png`),
      animations: 'disabled',
    });
  }
});

for (const width of [1440, 390, 720])
  test(`message sides and a pinned composer remain usable at ${width}px`, async ({ page }) => {
    await page.setViewportSize({ width, height: width === 720 ? 500 : 1000 });
    await assistantFixture(page);
    await ask(page);
    await page.getByRole('heading', { name: 'Chat', exact: true }).scrollIntoViewIfNeeded();
    const user = await page.locator('.message.user-message').boundingBox();
    const answer = await page
      .locator('.message')
      .filter({
        has: page.getByText(
          'North has 18 service cases; South has 12. The policy assigns review to the service owner.',
          { exact: true },
        ),
      })
      .boundingBox();
    expect(user).not.toBeNull();
    expect(answer).not.toBeNull();
    expect(user!.x).toBeGreaterThan(answer!.x + 24);
    const composer = await page.getByRole('textbox', { name: 'Message koinon' }).boundingBox();
    const footer = await page.locator('ffk-shell footer').boundingBox();
    expect(composer!.y).toBeGreaterThan(0);
    expect(composer!.y + composer!.height).toBeLessThan(footer!.y);
    expect(await page.evaluate(() => document.documentElement.scrollWidth)).toBeLessThanOrEqual(
      width,
    );
    await page.locator('.conversation-scroll').evaluate((node) => {
      node.scrollTop = node.scrollHeight;
    });
    const after = await page.getByRole('textbox', { name: 'Message koinon' }).boundingBox();
    expect(Math.abs(after!.y - composer!.y)).toBeLessThan(2);
  });

test('composer supports new lines and IME composition without sending prematurely', async ({
  page,
}) => {
  await assistantFixture(page);
  const sends: string[] = [];
  page.on('request', (request) => {
    if (request.url().endsWith('/runs')) sends.push(request.postData() || '');
  });
  await page.goto('/library');
  await page.getByRole('button', { name: 'Chat', exact: true }).click();
  const composer = page.getByRole('textbox', { name: 'Message koinon' });

  await composer.fill('Compare service activity by region and show the policy source.');
  await composer.dispatchEvent('keydown', { key: 'Enter', code: 'Enter', isComposing: true });
  expect(sends).toHaveLength(0);
  await composer.press('Shift+Enter');
  await expect(composer).toHaveValue(
    'Compare service activity by region and show the policy source.\n',
  );
  expect(sends).toHaveLength(0);
  await composer.press('Enter');
  await expect(
    page.getByText(
      'North has 18 service cases; South has 12. The policy assigns review to the service owner.',
      { exact: true },
    ),
  ).toBeVisible();
  expect(sends).toHaveLength(1);
});

test('mobile conversation history traps focus and restores its trigger on Escape', async ({
  page,
}) => {
  await page.setViewportSize({ width: 390, height: 844 });
  await assistantFixture(page);
  await ask(page);
  const trigger = page.getByRole('button', { name: 'Show conversations', exact: true });
  await trigger.click();
  const close = page
    .locator('.conversation-list')
    .getByRole('button', { name: 'Close conversations', exact: true });
  await expect(
    page
      .locator('.conversation-list')
      .getByRole('button', { name: 'New conversation', exact: true }),
  ).toBeFocused();
  await page.keyboard.press('Escape');
  await expect(close).not.toBeVisible();
  await expect(trigger).toBeFocused();
});
test('a new chat centers a simple koinon prompt with independent navigation controls', async ({
  page,
}) => {
  await page.setViewportSize({ width: 1440, height: 1000 });
  await assistantFixture(page);
  await page.goto('/library');
  await page.getByRole('button', { name: 'Chat', exact: true }).click();
  await expect(page.locator('.conversation.new-draft')).toBeVisible();
  const composer = page.locator('ffk-chat-composer');
  await expect(composer.getByRole('combobox')).toHaveCount(0);
  await expect(composer.locator('.knowledge-context')).toHaveCount(0);
  await expect(composer.getByRole('button', { name: 'Add context', exact: true })).toBeVisible();
  await expect(page.locator('ffk-shell .topbar').getByRole('searchbox')).toHaveCount(0);
  await expect(
    page
      .locator('ffk-conversation-sidebar')
      .getByRole('button', { name: 'New conversation', exact: true }),
  ).toBeVisible();
  await page.addStyleTag({
    content: 'ffk-workbench{--koinon-workspace-height:calc(100dvh - 22px)}',
  });
  await page.evaluate(() => {
    const note = document.createElement('div');
    note.textContent = 'Controlled service fixtures, Chat layout review';
    Object.assign(note.style, {
      position: 'fixed',
      inset: 'auto 0 0',
      height: '22px',
      background: '#855414',
      color: '#fff',
      font: '11px/22px system-ui',
      textAlign: 'center',
      zIndex: '9999',
    });
    document.body.append(note);
  });
  const output = resolve(process.cwd(), '../../../outputs');
  await page.screenshot({
    path: resolve(output, 'koinon-chat-empty-1440.png'),
    animations: 'disabled',
  });
  const box = (await composer.boundingBox())!;
  expect(box.y).toBeGreaterThan(250);
  expect(box.y + box.height).toBeLessThan(850);
  await page.getByRole('button', { name: 'Hide conversations', exact: true }).click();
  await expect(page.locator('.conversation-list')).not.toBeVisible();
  await expect(
    page.getByRole('navigation', { name: 'Main navigation', exact: true }),
  ).toBeVisible();
  await page.screenshot({
    path: resolve(output, 'koinon-chat-focused-1440.png'),
    animations: 'disabled',
  });
  await page.setViewportSize({ width: 390, height: 1000 });
  await expect(composer).toBeVisible();
  await page.screenshot({
    path: resolve(output, 'koinon-chat-empty-390.png'),
    animations: 'disabled',
  });
});

test('sidebar empty and error states keep their own layout inside the workbench', async ({
  page,
}) => {
  await assistantFixture(page);
  await page.goto('/library');
  await page.getByRole('button', { name: 'Chat', exact: true }).click();
  const sidebar = page.locator('ffk-conversation-sidebar');
  const empty = sidebar.getByText('Create a chat project to organize your conversations.', {
    exact: true,
  });
  await expect(empty).toBeVisible();
  expect(await empty.evaluate((node) => getComputedStyle(node).paddingTop)).toBe('0px');
  expect(await empty.evaluate((node) => getComputedStyle(node).textAlign)).toBe('start');
  await page.route('**/bff/api/v1/tenants/*/chat/folders**', (route) =>
    route.fulfill({
      status: 503,
      contentType: 'application/json',
      body: JSON.stringify({ detail: 'Folder service is unavailable. Try again.' }),
    }),
  );
  await sidebar.getByRole('button', { name: 'Conversation options', exact: true }).click();
  await sidebar.getByRole('menuitem', { name: 'Refresh', exact: true }).click();
  const error = sidebar.getByRole('alert');
  await expect(error).toBeVisible();
  const box = (await error.boundingBox())!;
  expect(box.width).toBeGreaterThan(180);
  expect(box.height).toBeLessThan(160);
  const text = (await error.locator('p').boundingBox())!;
  expect(text.width).toBeGreaterThan(150);
  expect(await error.evaluate((node) => getComputedStyle(node).flexDirection)).toBe('column');
});

test('shows persisted tool names and outcomes without exposing invocation arguments', async ({
  page,
}) => {
  const service = await assistantFixture(page);
  await ask(page);
  await expect(page.getByRole('cell', { name: 'North', exact: true })).toBeVisible();
  await expect(page.locator('.assistant-message ffk-tool-activity')).toHaveCount(0);
  const reads = service.resultReads.length;
  await page.getByRole('button', { name: 'Audit', exact: true }).click();
  const activity = page.getByRole('dialog', { name: 'Answer audit', exact: true });
  await activity.getByRole('tab', { name: 'Execution', exact: true }).click();
  await expect(activity.getByText('Query data', { exact: true })).toBeVisible();
  await expect(activity.getByText('Search knowledge', { exact: true })).toBeVisible();
  await expect(activity.locator('.tool-list > li')).toHaveCount(2);
  await expect(activity.getByText('Read 2 returned rows', { exact: true })).toBeVisible();
  await expect(activity.locator('pre,input,textarea')).toHaveCount(0);
  expect(service.resultReads.length).toBe(reads);
  await activity
    .locator('.tool-list > li')
    .filter({ hasText: 'Query data' })
    .getByRole('button', { name: 'View result', exact: true })
    .click();
  await expect(
    activity.getByText('SELECT region, COUNT(*) AS count FROM service_activity GROUP BY region', {
      exact: true,
    }),
  ).toBeVisible();
  await expect(activity.getByText('Executed SQL', { exact: true })).toBeVisible();
  expect(service.resultReads).toEqual(['r-query', 'r-query']);
  await page.keyboard.press('Escape');
  await expect(activity).not.toBeVisible();
  await expect(page.getByRole('button', { name: 'Audit', exact: true })).toBeFocused();
});

for (const width of [1440, 390])
  test(`answer audit keeps technical evidence in a separate responsive sidebar at ${width}px`, async ({
    page,
  }) => {
    await page.setViewportSize({ width, height: 1000 });
    await assistantFixture(page, { audit: true });
    await ask(page);
    await expect(page.locator('.assistant-message .supporting-evidence')).toHaveCount(0);
    const output = resolve(process.cwd(), '../../../outputs');
    await mkdir(output, { recursive: true });
    await page.evaluate(() => {
      (document.querySelector('ffk-workbench') as HTMLElement).style.setProperty(
        '--koinon-workspace-height',
        'calc(100dvh - 22px)',
      );
      const note = document.createElement('div');
      note.textContent = 'Controlled API fixtures, Answer audit layout review';
      note.style.cssText =
        'position:fixed;bottom:0;left:0;right:0;height:22px;background:#10110f;color:#f3f1eb;text-align:center;font:10px/22px system-ui;z-index:99999';
      document.body.append(note);
    });
    await page.screenshot({
      path: resolve(output, `koinon-chat-clean-v8-${width}.png`),
      animations: 'disabled',
    });
    await page.getByRole('button', { name: 'Audit', exact: true }).click();
    const dialog = page.getByRole('dialog', { name: 'Answer audit', exact: true });
    await dialog.getByRole('tab', { name: 'Execution', exact: true }).click();
    await dialog
      .locator('.tool-list > li')
      .filter({ hasText: 'Query data' })
      .getByRole('button', { name: 'View result', exact: true })
      .click();
    await expect(dialog.getByText('Executed SQL', { exact: true })).toBeVisible();
    await page.evaluate(() => {
      const panel = document
        .querySelector('ffk-workbench')
        ?.shadowRoot?.querySelector('dialog[open]');
      if (panel) {
        const note = document.createElement('div');
        note.textContent = 'Controlled API fixtures, Answer audit layout review';
        note.style.cssText =
          'position:absolute;bottom:0;left:0;right:0;height:22px;background:#10110f;color:#f3f1eb;text-align:center;font:10px/22px system-ui;z-index:99999';
        panel.append(note);
      }
    });
    expect((await dialog.boundingBox())!.width).toBeLessThanOrEqual(Math.min(480, width) + 1);
    expect(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth)).toBe(
      true,
    );
    await page.screenshot({
      path: resolve(output, `koinon-answer-audit-v8-${width}.png`),
      animations: 'disabled',
    });
  });

test('both message clocks use the viewer timezone while evidence keeps its response presentation', async ({
  page,
}) => {
  await assistantFixture(page);
  await page.route('**/bff/api/v1/profile', (route) =>
    route.fulfill({
      contentType: 'application/json',
      body: JSON.stringify({
        subject: 'synthetic.reviewer',
        display_name: 'Alex Rivera',
        locale: 'en-US',
        time_zone: 'America/New_York',
        response_language: 'en',
      }),
    }),
  );
  await ask(page);
  await expect(page.locator('.user-message time')).toHaveText(/6:00\s*AM/);
  await expect(page.locator('.assistant-message time')).toHaveText(/6:00\s*AM/);
});

for (const width of [1440, 390])
  test(`multiple technical agents stay out of the composer while answer audit retains provenance at ${width}px`, async ({
    page,
  }) => {
    await page.setViewportSize({ width, height: 1000 });
    const service = await assistantFixture(page, { audit: true, multipleAgents: true });
    await ask(page);
    const chat = page.locator('ffk-chat-page');
    await expect(chat.locator('#chat-agent, .agent-choice, .trial-notice')).toHaveCount(0);
    await expect(chat.getByRole('button', { name: 'Send', exact: true })).toBeVisible();
    await expect(chat.getByRole('button', { name: 'Send trial', exact: true })).toHaveCount(0);
    expect(service.submittedAgents).toEqual(['agent-one']);
    await expect(chat.locator('.assistant-message .message-heading strong')).toHaveText('koinon');
    await page.getByRole('button', { name: 'Audit', exact: true }).click();
    const audit = page.getByRole('dialog', { name: 'Answer audit', exact: true });
    await expect(audit.getByText('fixture-local', { exact: true })).toBeVisible();
    await audit.locator('.generation-record summary').click();
    await expect(audit.locator('code').filter({ hasText: /^agent-one$/ })).toBeVisible();
    await expect(audit.locator('code').filter({ hasText: /^provider-one$/ })).toBeVisible();
    await audit.getByRole('tab', { name: 'Sources', exact: true }).click();
    await expect(audit.getByText('Service operating policy.pdf', { exact: true })).toBeVisible();
    await expect(audit.getByText('Quarterly service activity', { exact: true })).toBeVisible();
    await page.keyboard.press('Escape');
    const output = resolve(process.cwd(), '.qualification-v22/chat-captures');
    await mkdir(output, { recursive: true });
    await page.screenshot({
      path: resolve(output, `chat-no-agent-picker-${width}.png`),
      animations: 'disabled',
    });
  });

for (const width of [1440, 390])
  test(`keyboard return from answer audit keeps the shared focus ring inside its scrollport at ${width}px`, async ({
    page,
  }) => {
    await page.setViewportSize({ width, height: 1000 });
    await assistantFixture(page, { audit: true, answerActions: true });
    await ask(page);
    const trigger = page.getByRole('button', { name: 'Audit', exact: true });
    await trigger.focus();
    await page.keyboard.press('Enter');
    await expect(page.getByRole('dialog', { name: 'Answer audit', exact: true })).toBeVisible();
    await page.keyboard.press('Escape');
    await expect(trigger).toBeFocused();
    const bounds = await trigger.evaluate((node) => {
      const style = getComputedStyle(node),
        box = node.getBoundingClientRect();
      const viewport = node.closest('.conversation-scroll') as HTMLElement;
      const row = node.closest('.answer-actions')!;
      const rowBox = row.getBoundingClientRect();
      const clip = viewport.getBoundingClientRect();
      const outside = Math.max(0, parseFloat(style.outlineWidth) + parseFloat(style.outlineOffset));
      return {
        row: { left: rowBox.left, top: rowBox.top, right: rowBox.right, height: rowBox.height },
        targets: [...row.querySelectorAll('button')].map((button) => {
          const target = button.getBoundingClientRect();
          return {
            left: target.left,
            top: target.top,
            right: target.right,
            width: target.width,
            height: target.height,
          };
        }),
        keyboardVisible: node.matches(':focus-visible'),
        outlineWidth: parseFloat(style.outlineWidth),
        ring: {
          left: box.left - outside,
          top: box.top - outside,
          right: box.right + outside,
          bottom: box.bottom + outside,
        },
        clip: {
          left: clip.left + viewport.clientLeft,
          top: clip.top + viewport.clientTop,
          right: clip.left + viewport.clientLeft + viewport.clientWidth,
          bottom: clip.top + viewport.clientTop + viewport.clientHeight,
        },
      };
    });
    await expect(page.getByRole('button', { name: 'Save as knowledge', exact: true })).toBeVisible();
    expect(bounds.targets).toHaveLength(4);
    expect(bounds.row.height).toBeLessThanOrEqual(width < 700 ? 44 : 32);
    for (const target of bounds.targets) {
      expect(target.height).toBe(width < 700 ? 44 : 32);
      if (width < 700) expect(target.width).toBeGreaterThanOrEqual(44);
      expect(target.left).toBeGreaterThanOrEqual(bounds.row.left);
      expect(target.right).toBeLessThanOrEqual(bounds.row.right);
      expect(Math.abs(target.top - bounds.row.top)).toBeLessThanOrEqual(0.5);
    }
    expect(bounds.keyboardVisible).toBe(true);
    expect(bounds.outlineWidth).toBeGreaterThan(0);
    expect(bounds.ring.left).toBeGreaterThanOrEqual(bounds.clip.left);
    expect(bounds.ring.top).toBeGreaterThanOrEqual(bounds.clip.top);
    expect(bounds.ring.right).toBeLessThanOrEqual(bounds.clip.right);
    expect(bounds.ring.bottom).toBeLessThanOrEqual(bounds.clip.bottom);
    const directory = resolve(process.cwd(), '.qualification-v23-followup/focus-captures');
    await mkdir(directory, { recursive: true });
    await writeFile(
      resolve(directory, `audit-keyboard-bounds-${width}.json`),
      JSON.stringify(bounds, null, 2) + '\n',
    );
    await page.screenshot({
      path: resolve(directory, `audit-keyboard-focus-${width}.png`),
      animations: 'disabled',
    });
  });
