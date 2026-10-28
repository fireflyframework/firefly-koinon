// Copyright 2026 Firefly Software Foundation
// SPDX-License-Identifier: Apache-2.0
import { test, expect, type Page } from '@playwright/test';
import { mkdir, readFile } from 'node:fs/promises';
import { resolve } from 'node:path';
import { mockService, context as baseContext } from './fixtures';
const revision = 'a'.repeat(64),
  stamp = '2026-10-27T10:00:00Z';
const source = {
  id: 'citation-one',
  asset_id: 'document-one',
  source_id: 'source-one',
  title: 'Service operating policy.pdf',
  kind: 'document',
  used_revision: revision,
  current_revision: revision,
  availability: 'available',
  quote: 'The service owner maintains the documented review.',
  page: 3,
};

const immutableIdentityAudit = {
  run_id: 'review-run',
  provenance_status: 'recorded',
  source_provenance_complete: true,
  sources: [
    {
      id: 'recorded-part',
      asset_id: 'document-one',
      source_id: 'source-one',
      kind: 'document',
      title: 'Service operating policy.pdf',
      source_version_id: 'document-version-used',
      extraction_id: 'document-view-used',
      source_part_id: 'document-part-used',
      source_part_sha256: 'a'.repeat(64),
      used_revision: 'source-part-sha256:' + 'a'.repeat(64),
      recorded_page: 7,
      page_basis: 'recorded_loader',
      page: null,
      chunk_id: null,
      quote: 'The service owner maintains the documented review.',
      availability: 'available',
    },
    {
      id: 'published-evidence',
      asset_id: 'published-item',
      knowledge_item_id: 'published-item',
      kind: 'knowledge_version',
      title: 'Published renewal policy',
      knowledge_version_id: 'published-version-used',
      knowledge_version: 3,
      used_revision: 'knowledge-content-sha256:' + 'b'.repeat(64),
      quote: 'Renewals require review by the service owner.',
      availability: 'available',
    },
  ],
  native_reads: [
    {
      result_id: 'recorded-part-read',
      stage: 'rlm.read',
      domain: 'documents',
      tenant_id: 'tenant-one',
      workspace_id: 'workspace-one',
      entity_id: 'document-one',
      read_kind: 'document_extraction',
      source_version_id: 'document-version-used',
      extraction_id: 'document-view-used',
      content_sha256: 'c'.repeat(64),
      source_ids: ['native-source'],
      snapshot_ids: [],
      origin: { original_filename: 'Service operating policy.pdf' },
    },
    {
      result_id: 'published-read',
      stage: 'model.context',
      domain: 'knowledge',
      tenant_id: 'tenant-one',
      workspace_id: 'workspace-one',
      entity_id: 'published-item',
      read_kind: 'knowledge_version',
      knowledge_item_id: 'published-item',
      knowledge_version_id: 'published-version-used',
      knowledge_version: 3,
      content_sha256: 'd'.repeat(64),
      source_ids: ['published-item'],
      snapshot_ids: [],
    },
  ],
};
async function artifactFixture(page: Page, rights = true, structuredOrigin = true) {
  await mockService(page);
  const permissions = [
    'exports:read',
    'exports:write',
    'shares:read',
    'shares:write',
    'evidence:read',
  ];
  await page.route('**/bff/api/v1/context', (route) =>
    route.fulfill({
      json: {
        ...baseContext,
        tenants: baseContext.tenants.map((tenant, index) =>
          index === 0
            ? { ...tenant, permissions: [...tenant.permissions, ...(rights ? permissions : [])] }
            : tenant,
        ),
      },
    }),
  );
  const thread = {
    id: 'review-thread',
    title: 'Reviewed conversation',
    title_source: 'manual',
    revision: 1,
    folder_id: null,
    archived_at: null,
    scope: { workspace_id: 'workspace-one', project_id: 'project-one' },
    created_at: stamp,
    updated_at: stamp,
  };
  const messages = [
    {
      id: 'first-answer',
      role: 'assistant',
      text: 'First saved answer.',
      status: 'completed',
      citations: [],
      artifacts: [],
      created_at: stamp,
    },
    {
      id: 'second-answer',
      run_id: 'review-run',
      answer_policy: {
        outcome: 'grounded',
        reason: 'The saved answer cites the recorded policy passage.',
      },
      role: 'assistant',
      text: 'Second saved answer selected for review.',
      status: 'completed',
      citations: [],
      artifacts: [],
      created_at: stamp,
    },
  ];
  const calls: {
    method: string;
    path: string;
    body: Record<string, unknown>;
    csrf: string | undefined;
  }[] = [];
  let selected = 'second-answer';
  await page.route('**/bff/api/v1/tenants/*/**', async (route) => {
    const request = route.request(),
      path = new URL(request.url()).pathname,
      method = request.method();
    const body = method === 'POST' ? (request.postDataJSON() as Record<string, unknown>) : {};
    calls.push({ method, path, body, csrf: request.headers()['x-xsrf-token'] });
    const json = (data: unknown, status = 200) =>
      route.fulfill(status === 204 ? { status } : { status, json: data });
    if (path.endsWith('/agents'))
      return json({
        items: [
          {
            id: 'agent',
            name: 'Controlled local guide',
            provider_id: 'provider',
            model_id: 'fixture',
            tools: [],
            scope: {},
            instructions: '',
            enabled: true,
            revision: 1,
            status: 'ready',
            configured: true,
            can_run: true,
            checks: [],
          },
        ],
      });
    if (path.endsWith('/chat/threads'))
      return json({ items: [thread], total: 1, page: 1, page_size: 25, pages: 1 });
    if (path.endsWith('/chat/threads/review-thread')) return json(thread);
    if (path.endsWith('/chat/runs/review-run/audit'))
      return json({
        run_id: 'review-run',
        provenance_status: 'recorded',
        source_provenance_complete: true,
        generations: [
          {
            id: 'recorded-generation',
            start_sequence: 0,
            agent_id: 'recorded-agent',
            agent_revision: 2,
            provider_id: 'recorded-provider',
            provider_revision: 3,
            provider_kind: 'ollama',
            model_id: 'recorded-model:1',
            model_class: 'OllamaModel',
            api: 'chat',
            started_at: stamp,
            finished_at: '2026-10-27T10:00:05Z',
            status: 'completed',
          },
        ],
        sources: [source],
        private_files: [
          {
            id: 'recorded-file',
            filename: 'Private planning notes.pdf',
            media_type: 'application/pdf',
            sha256: 'b'.repeat(64),
            used_revision: 2,
            availability: 'deleted',
          },
        ],
        native_reads: [
          {
            result_id: 'query-result',
            stage: 'execution',
            domain: 'structured',
            tenant_id: 'tenant-one',
            workspace_id: 'workspace-one',
            entity_id: 'dataset-one',
            content_sha256: 'c'.repeat(64),
            source_ids: ['schema-observation'],
            snapshot_ids: ['recorded-snapshot'],
            engine: 'postgresql',
            database: 'metadata_store',
            catalog: 'metadata_catalog',
            schema: 'retained_metadata',
            read_kind: 'metadata',
            origin: structuredOrigin
              ? {
                  original_filename: 'Policy import.csv',
                  connection_name: 'Recorded source connection',
                  database: 'original_warehouse',
                  schema: 'original_schema',
                  table: 'original_policy_rows',
                }
              : null,
          },
          {
            result_id: 'document-result',
            stage: 'retrieval',
            domain: 'documents',
            tenant_id: 'tenant-one',
            workspace_id: 'workspace-one',
            entity_id: 'document-one',
            content_sha256: 'f'.repeat(64),
            source_ids: ['source-one'],
            snapshot_ids: [],
            engine: 'postgresql',
            database: 'document_store',
            catalog: 'document_catalog',
            schema: 'retained_documents',
            read_kind: 'indexed_document',
            origin: { original_filename: 'Service operating policy.pdf' },
          },
        ],
        sql_attempts: [
          {
            result_id: 'query-result',
            ordinal: 1,
            stage: 'validation',
            statement_sha256: 'd'.repeat(64),
            statement: 'DELETE FROM protected_policy',
            outcome: 'blocked',
            executed: false,
            reason_code: 'READ_ONLY_POLICY',
          },
          {
            result_id: 'query-result',
            ordinal: 2,
            stage: 'execution',
            statement_sha256: 'e'.repeat(64),
            statement: 'SELECT owner FROM service_policy',
            outcome: 'succeeded',
            executed: true,
            row_count: 137,
            truncated: true,
            engine: 'duckdb',
            database: 'memory',
            catalog: 'memory',
            schema: 'main',
            execution_kind: 'imported_snapshot',
            dataset_id: 'dataset-one',
            native_dataset_id: 'native-dataset-one',
            tables: [
              {
                table_id: 'native-table',
                table_name: 'policy_rows_import',
                snapshot_id: 'recorded-snapshot',
              },
            ],
            snapshot_pins: { 'native-table': 'recorded-snapshot' },
          },
        ],
      });
    if (path.endsWith('/chat/runs/review-run/activity')) {
      const current = Number(new URL(request.url()).searchParams.get('page') ?? 1);
      return json({
        items: Array.from({ length: current === 1 ? 25 : 1 }, (_, index) => ({
          call_id: 'call-' + ((current - 1) * 25 + index),
          tool_name: 'query_dataset',
          status: 'completed',
          occurred_at: stamp,
          summary: 'Read recorded policy data',
          duration_ms: 123,
          result_id: 'query-result',
        })),
        total: 26,
        page: current,
        page_size: 25,
        pages: 2,
      });
    }
    if (path.endsWith('/chat/runs/review-run/results/query-result'))
      return json({
        id: 'query-result',
        run_id: 'review-run',
        kind: 'query',
        data: {
          query_id: 'stored-query',
          execution_status: 'OK',
          sql: 'SELECT owner FROM service_policy',
          preview: [{ owner: 'Service owner' }],
          row_count: 137,
          truncated: true,
        },
      });
    if (path.endsWith('/messages')) return json({ items: messages, next_cursor: null });
    if (path.endsWith('/attachments/capabilities'))
      return json({
        storage: {
          available: false,
          reason: 'Private uploads are outside this controlled fixture.',
        },
        database: { available: true },
        extraction: { available: null },
        limits: {
          max_file_bytes: 10485760,
          max_image_bytes: 5242880,
          max_selected: 5,
          max_thread_files: 20,
          max_thread_bytes: 104857600,
          max_model_text_chars: 50000,
          max_model_binary_bytes: 10485760,
          extraction_timeout_seconds: 60,
          ttl_seconds: 3600,
        },
        formats: [],
        promotion: {},
      });
    if (path.endsWith('/exports/reviews') || path.endsWith('/shares/reviews')) {
      selected = (body['message_ids'] as string[])[0];
      const message = messages.find((row) => row.id === selected)!;
      return json(
        {
          id: path.endsWith('/exports/reviews') ? 'export-review' : 'share-review',
          revision,
          kind: 'conversation',
          format: body['format'] ?? 'markdown',
          title: 'Reviewed answer',
          message_count: 1,
          source_count: 1,
          completeness: 'selected_messages',
          messages: [{ ...message, revision, source_ids: [source.id], private_derived: false }],
          sources: [source],
          source_manifest_complete: true,
          omissions: [],
          expires_at: '2099-01-01T00:00:00Z',
        },
        201,
      );
    }
    if (path.endsWith('/evidence/conversations'))
      return json({ revision, complete: true, sources: [source], omissions: [] });
    if (path.endsWith('/exports') && method === 'POST')
      return json(
        {
          id: 'created-export',
          kind: 'conversation',
          format: 'markdown',
          title: 'Reviewed answer',
          status: 'ready',
          revision,
          completeness: 'selected_messages',
          created_at: stamp,
          expires_at: '2099-01-01T00:00:00Z',
        },
        201,
      );
    if (path.endsWith('/exports/created-export/download'))
      return route.fulfill({
        status: 200,
        contentType: 'text/markdown',
        headers: {
          'content-disposition': 'attachment; filename="reviewed-answer.md"',
          'cache-control': 'no-store',
          etag: '"' + revision + '"',
        },
        body: '# Reviewed answer\n\n' + messages.find((row) => row.id === selected)!.text,
      });
    if (path.endsWith('/shares') && method === 'POST')
      return json(
        {
          id: 'created-share',
          title: 'Reviewed answer',
          revision,
          status: 'active',
          recipient_policy: 'organization_current_acl',
          created_at: stamp,
          expires_at: '2099-01-01T00:00:00Z',
        },
        201,
      );
    if (path.endsWith('/shares/created-share') && method === 'DELETE') return json(null, 204);
    if (path.endsWith('/shares/created-share') && method === 'GET')
      return json({
        share: {
          id: 'created-share',
          title: 'Reviewed answer',
          revision,
          status: 'active',
          recipient_policy: 'organization_current_acl',
          created_at: stamp,
          expires_at: '2099-01-01T00:00:00Z',
        },
        messages: [{ ...messages[1], revision }],
        sources: [source],
        source_manifest_complete: true,
      });
    return route.fallback();
  });
  return { calls };
}
async function openChat(page: Page) {
  await page.goto('/');
  const menu = page.getByRole('button', { name: 'Open navigation', exact: true });
  if (await menu.isVisible()) await menu.click();
  await page.getByRole('button', { name: 'Chat', exact: true }).click();
  await expect(
    page.getByText('Second saved answer selected for review.', { exact: true }),
  ).toBeVisible();
  await expect(page.locator('.chat-error')).toHaveCount(0);
}
async function capture(page: Page, name: string) {
  await page.evaluate(() => {
    (document.querySelector('ffk-workbench') as HTMLElement)?.style.setProperty(
      '--koinon-workspace-height',
      'calc(100dvh - 22px)',
    );
    const note = document.createElement('div');
    note.textContent = 'Controlled API fixtures · Export/share/source review';
    note.style.cssText =
      'position:fixed;bottom:0;left:0;right:0;height:22px;background:#10110f;color:#f3f1eb;text-align:center;font:10px/22px sans-serif;z-index:99999';
    const dialog = document
      .querySelector('ffk-workbench')
      ?.shadowRoot?.querySelector('dialog[open]');
    if (dialog) {
      (dialog as HTMLElement).style.paddingBottom = '22px';
      note.style.position = 'absolute';
      dialog.append(note);
    } else document.body.append(note);
  });
  await page
    .locator('ffk-answer-audit .audit-tab-panel:not([hidden]) .receipt-detail')
    .evaluateAll((nodes) => {
      const detail = nodes[0] as HTMLElement | undefined;
      const pane = detail?.closest('dialog')?.querySelector<HTMLElement>(':scope > .body');
      if (!detail || !pane) return;
      const tabs = pane.querySelector<HTMLElement>('.audit-tabs');
      const content = detail.firstElementChild ?? detail;
      const readingTop = tabs?.getBoundingClientRect().bottom ?? pane.getBoundingClientRect().top;
      pane.scrollTop = Math.max(
        0,
        pane.scrollTop + content.getBoundingClientRect().top - readingTop - 16,
      );
    });
  if (name.startsWith('answer-audit-document-origin-')) {
    await expect(
      page.locator(
        'ffk-answer-audit .audit-tab-panel:not([hidden]) .receipt-detail ffk-recorded-origin',
      ),
    ).toBeInViewport({ ratio: 0.98 });
  }
  const directory = resolve('../../control/frontend-captures/artifacts');
  await mkdir(directory, { recursive: true });
  await page.screenshot({ path: resolve(directory, name), fullPage: true, animations: 'disabled' });
}

for (const width of [1440, 390])
  test(`immutable document and published knowledge audit stays scoped and readable ${width}`, async ({
    page,
  }) => {
    await page.setViewportSize({ width, height: 1000 });
    const api = await artifactFixture(page);
    await page.route('**/bff/api/v1/tenants/tenant-one/chat/runs/review-run/audit', (route) =>
      route.fulfill({ json: immutableIdentityAudit }),
    );
    await openChat(page);
    const before = api.calls.length;
    await page.getByRole('button', { name: 'Audit', exact: true }).nth(1).click();
    const dialog = page.getByRole('dialog');
    await dialog.getByRole('tab', { name: 'Sources', exact: true }).click();
    await dialog.getByRole('button', { name: /Published renewal policy/ }).click();
    await expect(dialog.getByText('Knowledge version', { exact: true })).toBeVisible();
    await expect(
      dialog.getByText('Knowledge content fingerprint', { exact: true }),
    ).not.toBeVisible();
    await expect(
      dialog.getByText('Renewals require review by the service owner.', { exact: true }),
    ).toBeVisible();
    await expect(dialog.locator('.source-detail ffk-recorded-origin')).toHaveCount(0);
    await capture(page, `answer-audit-knowledge-version-${width}.png`);
    await dialog.locator('.source-detail summary').click();
    await expect(dialog.getByText('Knowledge content fingerprint', { exact: true })).toBeVisible();
    await expect(dialog.getByText('published-version-used', { exact: true })).toBeVisible();
    await dialog.getByRole('tab', { name: 'Execution', exact: true }).click();
    await dialog
      .locator('.receipt-toggle')
      .filter({ hasText: 'Service operating policy.pdf' })
      .click();
    await expect(dialog.getByText('Recorded document extraction', { exact: true })).toBeVisible();
    await dialog.locator('.receipt-detail summary').click();
    await expect(dialog.getByText('document-version-used', { exact: true })).toBeVisible();
    await expect(dialog.getByText('document-view-used', { exact: true })).toBeVisible();
    await capture(page, `answer-audit-extraction-version-${width}.png`);
    expect(api.calls.slice(before).every((call) => call.method === 'GET')).toBe(true);
    expect(api.calls.slice(before).some((call) => call.path.includes('/results/'))).toBe(false);
    expect(await page.evaluate(() => document.documentElement.scrollWidth)).toBe(width);
    await page.keyboard.press('Escape');
    await expect(dialog).not.toBeVisible();
    await expect(page.getByRole('button', { name: 'Audit', exact: true }).nth(1)).toBeFocused();
  });
test('per-answer export reviews exactly one canonical message then creates and downloads real bytes', async ({
  page,
}) => {
  const api = await artifactFixture(page);
  await openChat(page);
  await page.getByRole('button', { name: 'Export answer', exact: true }).nth(1).click();
  const dialog = page.getByRole('dialog');
  await expect(dialog).toBeVisible();
  expect(api.calls.filter((row) => row.path.endsWith('/exports/reviews'))).toHaveLength(0);
  await dialog.getByRole('button', { name: 'Review export', exact: true }).click();
  await expect(
    dialog.getByText('Second saved answer selected for review.', { exact: true }),
  ).toBeVisible();
  const review = api.calls.find((row) => row.path.endsWith('/exports/reviews'))!;
  expect(review.body).toEqual({
    kind: 'conversation',
    thread_id: 'review-thread',
    message_ids: ['second-answer'],
    format: 'markdown',
    include_evidence: true,
  });
  expect(review.csrf).toBe('synthetic-csrf+token');
  await dialog.getByRole('button', { name: 'Create export', exact: true }).click();
  await expect(dialog.getByText('Your export is ready.', { exact: true })).toBeVisible();
  expect(
    api.calls.find((row) => row.path.endsWith('/exports') && row.method === 'POST')?.body,
  ).toEqual({ review_id: 'export-review', expected_revision: revision });
  const downloaded = page.waitForEvent('download');
  await dialog.getByRole('button', { name: 'Download', exact: true }).click();
  const file = await downloaded;
  expect(file.suggestedFilename()).toBe('reviewed-answer.md');
  expect(await readFile((await file.path())!, 'utf8')).toContain(
    'Second saved answer selected for review.',
  );
});
test('artifact actions depend on authoritative permissions, not the displayed administrator role', async ({
  page,
}) => {
  const api = await artifactFixture(page, false);
  await openChat(page);
  await expect(page.getByRole('button', { name: 'Export answer', exact: true })).toHaveCount(0);
  await expect(page.getByRole('button', { name: 'Share answer', exact: true })).toHaveCount(0);
  await expect(page.getByRole('button', { name: 'Audit', exact: true })).toHaveCount(2);
  await page.getByRole('button', { name: 'Audit', exact: true }).nth(1).click();
  await expect(
    page.getByRole('dialog').getByText('recorded-model:1', { exact: true }),
  ).toBeVisible();
  expect(api.calls.some((row) => row.path.includes('/evidence/'))).toBe(false);
});
test('answer sources and reviewed sharing use canonical IDs and explicit revision mutations', async ({
  page,
}) => {
  const api = await artifactFixture(page);
  await openChat(page);
  await page.getByRole('button', { name: 'Audit', exact: true }).nth(1).click();
  await page.getByRole('tab', { name: 'Sources', exact: true }).click();
  await page
    .getByRole('dialog')
    .getByRole('button', { name: /Service operating policy.pdf/ })
    .click();
  let dialog = page.getByRole('dialog');
  await expect(dialog.getByText(source.quote, { exact: true })).toBeVisible();
  expect(api.calls.some((row) => row.path.includes('/evidence/'))).toBe(false);
  expect(api.calls.find((row) => row.path.endsWith('/chat/runs/review-run/audit'))?.method).toBe(
    'GET',
  );
  await page.keyboard.press('Escape');
  await expect(dialog).not.toBeVisible();
  await page.getByRole('button', { name: 'Share answer', exact: true }).nth(1).click();
  dialog = page.getByRole('dialog');
  await dialog.getByRole('button', { name: 'Review shared content', exact: true }).click();
  await expect(
    dialog.getByText('Second saved answer selected for review.', { exact: true }),
  ).toBeVisible();
  await dialog.getByRole('button', { name: 'Create share', exact: true }).click();
  await expect(dialog.getByText('Your reviewed share is active.', { exact: true })).toBeVisible();
  expect(
    api.calls.find((row) => row.path.endsWith('/shares') && row.method === 'POST')?.body,
  ).toEqual({
    review_id: 'share-review',
    expected_revision: revision,
    expires_in_hours: 24,
    recipient_policy: 'organization_current_acl',
  });
  await dialog.getByRole('button', { name: 'Revoke share', exact: true }).click();
  await expect(dialog.getByText('This share was revoked.', { exact: true })).toBeVisible();
  expect(
    api.calls.some((row) => row.path.endsWith('/shares/created-share') && row.method === 'DELETE'),
  ).toBe(true);
});
for (const width of [1440, 390])
  test(`artifact panels review ${width}`, async ({ page }) => {
    await page.setViewportSize({ width, height: 900 });
    await artifactFixture(page);
    await openChat(page);
    await page.getByRole('button', { name: 'Export answer', exact: true }).nth(1).click();
    let dialog = page.getByRole('dialog');
    await dialog.getByRole('button', { name: 'Review export', exact: true }).click();
    await expect(
      dialog.getByText('Second saved answer selected for review.', { exact: true }),
    ).toBeVisible();
    await capture(page, `export-review-${width}.png`);
    const rect = await dialog.boundingBox();
    expect(rect!.width).toBeLessThanOrEqual(Math.min(480, width) + 1);
    await page.keyboard.press('Escape');
    await page.getByRole('button', { name: 'Audit', exact: true }).nth(1).click();
    await page.getByRole('tab', { name: 'Sources', exact: true }).click();
    await page
      .getByRole('dialog')
      .getByRole('button', { name: /Service operating policy.pdf/ })
      .click();
    dialog = page.getByRole('dialog');
    await expect(dialog.getByText(source.quote, { exact: true })).toBeVisible();
    await capture(page, `source-review-${width}.png`);
  });
test('recipient share entry renders only the saved snapshot and can open its verified source', async ({
  page,
}) => {
  const api = await artifactFixture(page);
  await page.goto('/#share=created-share&tenant=tenant-one');
  await expect(
    page
      .locator('ffk-shared-conversation')
      .getByText('Second saved answer selected for review.', { exact: true }),
  ).toBeVisible();
  expect(page.url()).not.toContain('#share');
  expect(api.calls.some((row) => row.path.includes('/chat/runs/'))).toBe(false);
  await page.getByRole('button', { name: 'View sources', exact: true }).click();
  const dialog = page.getByRole('dialog');
  await expect(dialog.getByText(source.quote, { exact: true })).toBeVisible();
  await dialog.getByRole('button', { name: 'Open source', exact: true }).click();
  await expect(page.locator('ffk-shared-conversation')).toHaveCount(0);
  expect(api.calls.some((row) => row.path.endsWith('/catalog/document-one'))).toBe(true);
});
for (const [code, status, title] of [
  ['SHARE_EXPIRED', 410, 'This share has expired.'],
  ['SHARE_REVOKED', 410, 'This share was revoked.'],
  ['EVIDENCE_UNAVAILABLE', 403, 'Your account cannot open this share.'],
] as const)
  test('recipient entry keeps saved text hidden for ' + code, async ({ page }) => {
    await artifactFixture(page);
    await page.route('**/bff/api/v1/tenants/tenant-one/shares/created-share', (route) =>
      route.fulfill({
        status,
        json: {
          type: 'about:blank',
          status,
          code,
          detail: 'Share unavailable',
          transactionId: 'controlled-state-proof',
        },
        headers: { 'cache-control': 'private, no-store' },
      }),
    );
    await page.goto('/#share=created-share&tenant=tenant-one');
    const reader = page.locator('ffk-shared-conversation');
    await expect(reader.getByText(title, { exact: true })).toBeVisible();
    await expect(
      reader.getByText('Second saved answer selected for review.', { exact: true }),
    ).toHaveCount(0);
    await reader.getByRole('button', { name: 'Close shared messages', exact: true }).click();
    await expect(reader).toHaveCount(0);
  });
test('recipient review fits a mobile screen and closes through the explicit host event', async ({
  page,
}) => {
  await page.setViewportSize({ width: 390, height: 900 });
  await artifactFixture(page);
  await page.goto('/#share=created-share&tenant=tenant-one');
  const reader = page.locator('ffk-shared-conversation');
  await expect(
    reader.getByText('Second saved answer selected for review.', { exact: true }),
  ).toBeVisible();
  await capture(page, 'recipient-review-390.png');
  expect(await page.evaluate(() => document.documentElement.scrollWidth)).toBe(390);
  await reader.getByRole('button', { name: 'Close shared messages', exact: true }).click();
  await expect(reader).toHaveCount(0);
});
test('evidence inclusion has one aligned label and a comfortably sized checkbox hit area', async ({
  page,
}) => {
  await page.setViewportSize({ width: 390, height: 900 });
  await artifactFixture(page);
  await openChat(page);
  await page.getByRole('button', { name: 'Export answer', exact: true }).nth(1).click();
  const label = page.getByRole('dialog').locator('label.checkbox'),
    input = label.locator('input');
  const bounds = await label.boundingBox(),
    check = await input.boundingBox();
  expect(bounds!.height).toBeGreaterThanOrEqual(44);
  expect(check!.x).toBeLessThan(bounds!.x + 30);
  expect(Math.abs(check!.y + check!.height / 2 - (bounds!.y + bounds!.height / 2))).toBeLessThan(4);
});
test('Spanish mobile export labels follow the persisted interface language', async ({ page }) => {
  await page.setViewportSize({ width: 390, height: 900 });
  await artifactFixture(page);
  await page.route('**/bff/api/v1/profile', (route) =>
    route.fulfill({
      json: {
        subject: baseContext.subject,
        display_name: 'Alex Rivera',
        locale: 'es-ES',
        time_zone: 'Europe/Madrid',
        response_language: 'es',
        avatar_url: null,
        avatar_version: null,
      },
    }),
  );
  await page.goto('/');
  await page.getByRole('button', { name: 'Abrir navegación', exact: true }).click();
  await page.getByRole('button', { name: 'Chat', exact: true }).click();
  await expect(
    page.getByText('Second saved answer selected for review.', { exact: true }),
  ).toBeVisible();
  await page.getByRole('button', { name: 'Exportar respuesta', exact: true }).nth(1).click();
  const dialog = page.getByRole('dialog');
  await expect(dialog.getByText('Formato', { exact: true })).toBeVisible();
  await dialog.getByRole('button', { name: 'Revisar exportación', exact: true }).click();
  await expect(
    dialog.getByText('Second saved answer selected for review.', { exact: true }),
  ).toBeVisible();
  await expect(
    dialog.getByRole('button', { name: 'Crear exportación', exact: true }),
  ).toBeVisible();
  await capture(page, 'export-review-390-es.png');
});
for (const width of [1440, 390])
  test(`answer audit has three scoped tabs and lazy paged execution ${width}`, async ({ page }) => {
    await page.setViewportSize({ width, height: 900 });
    const api = await artifactFixture(page);
    await openChat(page);
    await expect(page.getByRole('button', { name: 'Audit', exact: true })).toHaveCount(2);
    await page.getByRole('button', { name: 'Audit', exact: true }).nth(1).click();
    const dialog = page.getByRole('dialog');
    await expect(dialog.getByRole('tab', { name: 'Overview', exact: true })).toHaveAttribute(
      'aria-selected',
      'true',
    );
    await expect(
      dialog.getByText('The saved answer cites the recorded policy passage.', { exact: true }),
    ).toBeVisible();
    expect(api.calls.some((row) => row.path.includes('/results/'))).toBe(false);
    await expect(dialog.getByText('SELECT owner FROM service_policy', { exact: true })).toHaveCount(
      0,
    );
    await expect(dialog.getByText('recorded-model:1', { exact: true })).toBeVisible();
    await capture(page, `answer-audit-overview-${width}.png`);
    const overview = dialog.getByRole('tab', { name: 'Overview', exact: true });
    await overview.focus();
    await page.keyboard.press('ArrowRight');
    await expect(dialog.getByRole('tab', { name: 'Sources', exact: true })).toBeFocused();
    await dialog.getByRole('button', { name: /Service operating policy.pdf/ }).click();
    await expect(dialog.getByText(source.quote, { exact: true })).toBeVisible();
    await capture(page, `answer-audit-sources-${width}.png`);
    await dialog.getByRole('tab', { name: 'Execution', exact: true }).click();
    await expect(dialog.getByRole('button', { name: 'View result', exact: true })).toHaveCount(25);
    expect(api.calls.some((row) => row.path.includes('/results/'))).toBe(false);
    await dialog.getByRole('button', { name: 'Next', exact: true }).click();
    await expect(dialog.getByRole('button', { name: 'View result', exact: true })).toHaveCount(1);
    await dialog.getByRole('button', { name: 'View result', exact: true }).click();
    await expect(
      dialog.getByText('SELECT owner FROM service_policy', { exact: true }),
    ).toBeVisible();
    expect(api.calls.filter((row) => row.path.includes('/results/'))).toHaveLength(1);
    await expect(dialog.getByText('137', { exact: true })).toBeVisible();
    await capture(page, `answer-audit-execution-${width}.png`);
    for (const bounds of await dialog.getByRole('tab').evaluateAll((nodes) =>
      nodes.map((node) => ({
        width: node.getBoundingClientRect().width,
        height: node.getBoundingClientRect().height,
      })),
    )) {
      expect(bounds.width).toBeGreaterThanOrEqual(44);
      expect(bounds.height).toBeGreaterThanOrEqual(44);
    }
    expect(await page.evaluate(() => document.documentElement.scrollWidth)).toBe(width);
  });
for (const width of [1440, 390])
  test(`owner audit receipts retain recorded generation, private files and SQL observations ${width}`, async ({
    page,
  }) => {
    await page.setViewportSize({ width, height: 900 });
    const api = await artifactFixture(page, false);
    await openChat(page);
    const before = api.calls.length;
    await page.getByRole('button', { name: 'Audit', exact: true }).nth(1).click();
    const dialog = page.getByRole('dialog');
    await expect(dialog.getByText('recorded-model:1', { exact: true })).toBeVisible();
    await dialog.locator('.generation-record summary').click();
    await expect(dialog.getByText('recorded-agent', { exact: true })).toBeVisible();
    await expect(dialog.getByText('recorded-provider', { exact: true })).toBeVisible();
    expect(
      api.calls
        .slice(before)
        .some((row) => row.path.includes('/configuration') || row.path.includes('/evidence/')),
    ).toBe(false);
    await dialog.getByRole('tab', { name: 'Sources', exact: true }).click();
    await dialog.getByRole('button', { name: /Private planning notes.pdf/ }).click();
    const source = dialog.locator('.source-detail');
    await expect(source.getByText('b'.repeat(64), { exact: true })).not.toBeVisible();
    await source.locator('.technical-references summary').click();
    await expect(source.getByText('b'.repeat(64), { exact: true })).toBeVisible();
    await expect(source.getByText('Deleted', { exact: true })).toBeVisible();
    await expect(source.getByText('2', { exact: true })).toBeVisible();
    await expect(dialog.getByRole('button', { name: 'Download', exact: true })).toHaveCount(0);
    expect(api.calls.some((row) => row.path.includes('/attachments/recorded-file'))).toBe(false);
    await capture(page, `answer-audit-private-${width}.png`);
    await dialog.getByRole('tab', { name: 'Execution', exact: true }).click();
    await dialog.getByRole('button', { name: /Structured data read/ }).click();
    await expect(dialog.getByText('metadata_store', { exact: true })).toBeVisible();
    await expect(dialog.getByText('original_warehouse', { exact: true })).toBeVisible();
    let technical = dialog.locator('.receipt-detail .technical-references');
    await expect(technical).toHaveJSProperty('open', false);
    await technical.locator('summary').click();
    await expect(dialog.getByText('dataset-one', { exact: true })).toBeVisible();
    await expect(dialog.getByText('c'.repeat(64), { exact: true })).toBeVisible();
    await dialog.getByRole('button', { name: /Document read/ }).click();
    await expect(dialog.getByText('document_store', { exact: true })).toBeVisible();
    await expect(dialog.getByText('Indexed document content', { exact: true })).toBeVisible();
    await expect(
      dialog
        .locator('.receipt-detail ffk-recorded-origin')
        .getByText('Service operating policy.pdf', { exact: true }),
    ).toBeVisible();
    await capture(page, `answer-audit-document-origin-${width}.png`);
    await dialog.getByRole('button', { name: /Recorded SQL.*Not executed/ }).click();
    await expect(dialog.getByText('DELETE FROM protected_policy', { exact: true })).toBeVisible();
    await expect(dialog.getByText('READ_ONLY_POLICY', { exact: true })).toBeVisible();
    await dialog.getByRole('button', { name: /Executed SQL/ }).click();
    await expect(dialog.getByText('DELETE FROM protected_policy', { exact: true })).toHaveCount(0);
    await expect(
      dialog.getByText('SELECT owner FROM service_policy', { exact: true }),
    ).toBeVisible();
    await expect(dialog.getByText('Imported snapshot execution', { exact: true })).toBeVisible();
    await expect(dialog.getByText('duckdb', { exact: true })).toBeVisible();
    await expect(
      dialog.locator('.table-snapshots').getByText('policy_rows_import', { exact: true }),
    ).toBeVisible();
    await expect(dialog.locator('.sql-lineage')).toContainText('original_warehouse');
    await expect(dialog.locator('.execution-location')).not.toContainText('original_warehouse');
    technical = dialog.locator('.receipt-detail .technical-references');
    await expect(technical).toHaveCount(1);
    await expect(technical).toHaveJSProperty('open', false);
    await expect(dialog.getByText('native-dataset-one', { exact: true })).toBeHidden();
    await capture(page, `answer-audit-receipts-${width}.png`);
    await technical.locator('summary').click();
    await expect(dialog.getByText('recorded-snapshot', { exact: true })).toBeVisible();
    expect(api.calls.some((row) => row.path.includes('/results/'))).toBe(false);
  });
test('SQL lineage remains unknown for a structured null-origin receipt without borrowing its metadata database', async ({
  page,
}) => {
  await page.setViewportSize({ width: 390, height: 900 });
  await artifactFixture(page, false, false);
  await openChat(page);
  await page.getByRole('button', { name: 'Audit', exact: true }).nth(1).click();
  const dialog = page.getByRole('dialog');
  await dialog.getByRole('tab', { name: 'Execution', exact: true }).click();
  await dialog.getByRole('button', { name: /Executed SQL/ }).click();
  await expect(dialog.locator('.sql-lineage')).toContainText(
    'Original source identity was not recorded.',
  );
  await expect(dialog.locator('.sql-lineage')).not.toContainText('metadata_store');
  await expect(dialog.locator('.sql-lineage')).not.toContainText('Service operating policy.pdf');
  await expect(dialog.locator('.execution-location')).toContainText('duckdb');
  await capture(page, 'answer-audit-origin-unknown-390.png');
});
for (const width of [1440, 390])
  test(`audit sticky tabs cover the scroll gutter ${width}`, async ({ page }) => {
    await page.setViewportSize({ width, height: 900 });
    await page.emulateMedia({ colorScheme: 'light', reducedMotion: 'reduce' });
    await artifactFixture(page, false);
    await openChat(page);
    await page.getByRole('button', { name: 'Audit', exact: true }).nth(1).click();
    const dialog = page.getByRole('dialog');
    await dialog.getByRole('tab', { name: 'Execution', exact: true }).click();
    await dialog.getByRole('button', { name: /Executed SQL/ }).click();
    const sample = await dialog.locator('.receipt-detail').evaluate((detail) => {
      const pane = detail.closest('dialog')!.querySelector<HTMLElement>(':scope > .body')!,
        tabs = pane.querySelector<HTMLElement>('.audit-tabs')!,
        probe = detail.querySelector<HTMLElement>('.execution-location dt')!;
      const gutter = () => ({
        pane: pane.getBoundingClientRect(),
        tabs: tabs.getBoundingClientRect(),
      });
      const initial = gutter();
      const target = (initial.pane.top + initial.tabs.top) / 2;
      pane.scrollTop +=
        probe.getBoundingClientRect().top + probe.getBoundingClientRect().height / 2 - target;
      const bounds = gutter();
      return {
        gap: bounds.tabs.top - bounds.pane.top,
        background: getComputedStyle(tabs).backgroundColor,
        clip: {
          x: Math.ceil(bounds.tabs.left + 2),
          y: Math.ceil(bounds.pane.top + 2),
          width: Math.floor(bounds.tabs.width - 4),
          height: Math.floor(bounds.tabs.top - bounds.pane.top - 4),
        },
      };
    });
    expect(sample.gap).toBeGreaterThanOrEqual(19);
    const png = await page.screenshot({ clip: sample.clip, animations: 'disabled' });
    const pixels = await page.evaluate(
      async ({ encoded, background }) => {
        const image = new Image();
        image.src = 'data:image/png;base64,' + encoded;
        await image.decode();
        const canvas = document.createElement('canvas');
        canvas.width = image.width;
        canvas.height = image.height;
        const context = canvas.getContext('2d')!;
        context.fillStyle = background;
        context.fillRect(0, 0, canvas.width, canvas.height);
        const expected = context.getImageData(0, 0, 1, 1).data;
        context.drawImage(image, 0, 0);
        const data = context.getImageData(0, 0, canvas.width, canvas.height).data;
        let leaked = 0;
        for (let offset = 0; offset < data.length; offset += 4)
          if (
            Math.abs(data[offset] - expected[0]) > 2 ||
            Math.abs(data[offset + 1] - expected[1]) > 2 ||
            Math.abs(data[offset + 2] - expected[2]) > 2
          )
            leaked++;
        return leaked;
      },
      { encoded: png.toString('base64'), background: sample.background },
    );
    expect(
      pixels,
      'scrolled content must not paint in the padded gutter above the sticky tabs',
    ).toBe(0);
    await dialog.getByRole('button', { name: /Document read/ }).click();
    await expect(
      dialog
        .locator('.receipt-detail ffk-recorded-origin')
        .getByText('Service operating policy.pdf', { exact: true }),
    ).toBeVisible();
    await capture(page, `answer-audit-document-origin-${width}.png`);
    await dialog.getByRole('button', { name: /Executed SQL/ }).click();
    await expect(dialog.locator('.execution-location')).toContainText('duckdb');
    await capture(page, `answer-audit-receipts-${width}.png`);
  });
