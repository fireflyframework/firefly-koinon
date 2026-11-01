// Copyright 2026 Firefly Software Foundation
// SPDX-License-Identifier: Apache-2.0
import { test, expect, type Page } from '@playwright/test';
import { mkdir } from 'node:fs/promises';
import type { KnowledgeIndexView, NativeIndexChoice } from '@fireflyframework/koinon-sdk';
import { context, mockService } from './fixtures';
const output = process.env['KOINON_INDEX_SCREENSHOTS'];
async function capture(page: Page, name: string) {
  if (output) {
    await mkdir(output, { recursive: true });
    await page.screenshot({ path: `${output}/${name}.png`, animations: 'disabled' });
  }
}
async function fixture(page: Page) {
  await mockService(page);
  const current = structuredClone(context);
  current.memberships = [
    {
      id: 'admin',
      subject: current.subject,
      tenant_id: 'tenant-one',
      workspace_id: null,
      role: 'admin',
      active: true,
    },
  ];
  const old: KnowledgeIndexView = {
    id: 'previous',
    tenant_id: 'tenant-one',
    workspace_id: 'workspace-one',
    domain: 'documents',
    native_id: 'native-previous',
    space_id: 'space-previous',
    provider_id: 'embedding-provider',
    provider_kind: 'openai',
    model_id: 'embedding-v1',
    dimensions: 1536,
    storage_dimensions: 1536,
    status: 'active',
    active: true,
    revision: 1,
    chunk_count: 24,
    vector_count: 24,
    indexed: true,
    qualification: 'coverage_and_ann_passed',
    created_at: '2026-10-30T10:00:00Z',
  };
  let target: KnowledgeIndexView | null = null,
    active = 'previous',
    connectionRevision = 4,
    unknownCreate = false,
    unknownActivation = false;
  const writes: { path: string; key: string | undefined; body: Record<string, unknown> }[] = [];
  const accepted = new Map<string, string>();
  await page.route('**/bff/api/v1/**', async (route) => {
    const request = route.request(),
      url = new URL(request.url()),
      path = url.pathname,
      method = request.method();
    const json = (value: unknown, status = 200) => route.fulfill({ status, json: value });
    if (path.endsWith('/context')) return json(current);
    if (path.endsWith('/configuration'))
      return json({
        providers: [
          {
            id: 'embedding-provider',
            name: 'Organization embeddings',
            kind: 'openai',
            api: 'chat',
            base_url: 'https://models.example.test/v1',
            revision: 1,
            validated_revision: 1,
            model_ids: ['embedding-v2'],
            enabled: true,
            secret_configured: true,
            status: 'ready',
            checks: [],
            model_capabilities: [],
          },
        ],
        provider_types: [],
        connections: [],
        checks: [],
      });
    if (path.endsWith('/knowledge-connections'))
      return json({
        items: url.searchParams.get('workspace_id')
          ? []
          : [
              {
                id: 'embedding-assignment',
                tenant_id: 'tenant-one',
                workspace_id: null,
                domain: 'documents',
                role: 'documents.embedding',
                mode: 'provider',
                provider_id: 'embedding-provider',
                model_id: active === 'previous' ? 'embedding-v1' : 'embedding-v2',
                dimensions: 1536,
                storage_dimensions: 1536,
                space_id: active === 'previous' ? 'space-previous' : 'space-target',
                revision: connectionRevision,
                enabled: true,
              },
            ],
      });
    if (!path.includes('/knowledge-index')) return route.fallback();
    const domain = url.searchParams.get('domain') ?? 'documents';
    const native = (row: KnowledgeIndexView): NativeIndexChoice => ({
      ...row,
      active: row.id === active,
      managed_id: row.id,
    });
    if (path.endsWith('/knowledge-index-choices'))
      return json({
        items: domain === 'documents' ? [native(old), ...(target ? [native(target)] : [])] : [],
        total: domain === 'documents' ? (target ? 2 : 1) : 0,
        limit: Number(url.searchParams.get('limit') ?? 100),
        offset: Number(url.searchParams.get('offset') ?? 0),
      });
    if (path.endsWith('/knowledge-indexes') && method === 'GET') {
      const status = url.searchParams.get('status'),
        rows =
          domain === 'documents'
            ? [
                {
                  ...old,
                  active: active === 'previous',
                  status: active === 'previous' ? 'active' : 'retired',
                },
                ...(target ? [target] : []),
              ].filter((row) => !status || row.status === status)
            : [];
      return json({
        items: rows,
        total: rows.length,
        limit: 25,
        offset: Number(url.searchParams.get('offset') ?? 0),
      });
    }
    if (path.endsWith('/knowledge-indexes/target') && method === 'GET') return json(target);
    if (path.endsWith('/knowledge-indexes/previous') && method === 'GET') return json(old);
    const body = request.postDataJSON() as Record<string, unknown>,
      key = request.headers()['idempotency-key'];
    writes.push({ path, key, body });
    if (path.endsWith('/plan'))
      return json({
        tenant_id: 'tenant-one',
        workspace_id: 'workspace-one',
        domain: 'documents',
        provider_id: 'embedding-provider',
        provider_kind: 'openai',
        provider_revision: 1,
        model_id: 'embedding-v2',
        dimensions: 1536,
        storage_dimensions: 1536,
        qualification: 'probe_passed',
        expected_connection_revision: connectionRevision,
        active_space_id: 'space-previous',
        active_index_id: active,
        chunk_count: 24,
        warnings: ['A separate version will be built before activation.'],
      });
    if (path.endsWith('/knowledge-indexes')) {
      if (!key) return json({ code: 'IDEMPOTENCY_REQUIRED' }, 400);
      if (accepted.has(key) && accepted.get(key) !== JSON.stringify(body))
        return json({ code: 'IDEMPOTENCY_CONFLICT' }, 409);
      accepted.set(key, JSON.stringify(body));
      target ??= {
        ...old,
        id: 'target',
        native_id: 'native-target',
        space_id: 'space-target',
        model_id: 'embedding-v2',
        status: 'queued',
        active: false,
        revision: 1,
        vector_count: 0,
        indexed: false,
        job_id: 'index-build-job',
        created_at: '2026-11-01T10:00:00Z',
      };
      if (unknownCreate) {
        unknownCreate = false;
        return route.abort('failed');
      }
      return json({ index: target, job_id: target.job_id }, 202);
    }
    if (!target) return json({ code: 'NOT_FOUND' }, 404);
    if (path.endsWith('/activate')) {
      if (body['expected_revision'] !== target.revision)
        return json({ code: 'INDEX_REVISION_CONFLICT' }, 409);
      if (unknownActivation) {
        unknownActivation = false;
        target = {
          ...target,
          status: 'activating',
          revision: target.revision + 1,
          recovery_required: true,
        };
        return route.abort('failed');
      }
      if (body['recovery'] === 'restore_previous') {
        active = 'previous';
        target = {
          ...target,
          status: 'ready',
          active: false,
          revision: target.revision + 1,
          recovery_required: false,
        };
      } else {
        active = 'target';
        connectionRevision++;
        target = {
          ...target,
          status: 'active',
          active: true,
          revision: target.revision + 1,
          recovery_required: false,
        };
      }
      return json(target);
    }
    if (path.endsWith('/cancel')) {
      target = { ...target, status: 'cancelled', revision: target.revision + 1 };
      return json(target);
    }
    if (path.endsWith('/resume')) {
      target = { ...target, status: 'queued', revision: target.revision + 1 };
      return json({ index: target, job_id: 'resumed-index-build' });
    }
    return json({ code: 'UNEXPECTED' }, 400);
  });
  return {
    writes,
    current,
    unknownCreate: () => {
      unknownCreate = true;
    },
    unknownActivation: () => {
      unknownActivation = true;
    },
    ready: () => {
      if (target)
        target = {
          ...target,
          status: 'ready',
          indexed: true,
          vector_count: target.chunk_count,
          qualification: 'coverage_and_ann_passed',
          revision: target.revision + 1,
        };
    },
    failed: () => {
      if (target)
        target = {
          ...target,
          status: 'failed',
          active: false,
          indexed: false,
          revision: target.revision + 1,
        };
    },
    target: () => target,
  };
}
async function open(page: Page, width: number) {
  await page.goto('/settings');
  if (width <= 760)
    await page.getByLabel('Settings section', { exact: true }).selectOption('storage');
  else await page.getByRole('button', { name: 'Storage & indexing', exact: true }).click();
  const panel = page.locator('ffk-index-management-panel');
  await expect(
    panel.getByRole('heading', { name: 'Knowledge indexes', exact: true }),
  ).toBeVisible();
  await panel.getByLabel('Index workspace', { exact: true }).selectOption('workspace-one');
  await expect(panel.locator('.active-target')).toContainText('embedding-v1');
  return panel;
}
async function plan(page: Page, panel: ReturnType<Page['locator']>) {
  await panel.getByRole('button', { name: 'Plan a new index', exact: true }).click();
  await panel.getByLabel('Embedding provider', { exact: true }).selectOption('embedding-provider');
  await panel.getByLabel('Embedding model', { exact: true }).selectOption('embedding-v2');
  await expect(panel).toContainText('may incur provider usage');
  await panel
    .getByRole('button', { name: 'Check embeddings and prepare plan', exact: true })
    .click();
  await expect(panel.locator('.plan-review')).toContainText('1,536');
}
for (const width of [1440, 390])
  test(`plan, build, inspect and explicitly activate an index at ${width}px`, async ({ page }) => {
    const service = await fixture(page);
    await page.setViewportSize({ width, height: 960 });
    const panel = await open(page, width);
    expect(service.writes).toHaveLength(0);
    await plan(page, panel);
    expect(service.writes.map((row) => row.path.split('/').pop())).toEqual(['plan']);
    await panel.locator('.plan-review').scrollIntoViewIfNeeded();
    await capture(page, `plan-${width}-light`);
    await panel.getByRole('button', { name: 'Build this index', exact: true }).click();
    await expect(panel.locator('.details')).toContainText('Queued');
    const create = service.writes.find((row) => row.path.endsWith('/knowledge-indexes'))!;
    expect(create.key).toBeTruthy();
    expect(create.body).toMatchObject({
      expected_active_id: 'previous',
      expected_connection_revision: 4,
      expected_dimensions: 1536,
    });
    expect(service.writes.some((row) => row.path.endsWith('/activate'))).toBe(false);
    service.ready();
    await panel.getByRole('button', { name: 'Refresh indexes', exact: true }).click();
    await expect(panel.locator('.details')).toContainText('Ready for review');
    await panel
      .locator('.details')
      .getByRole('button', { name: 'Activate index', exact: true })
      .click();
    await expect(panel.locator('.action-review')).toContainText('Assignment revision');
    expect(service.writes.some((row) => row.path.endsWith('/activate'))).toBe(false);
    await panel
      .locator('.action-review')
      .getByRole('button', { name: 'Activate index', exact: true })
      .click();
    await expect(panel.locator('.active-target')).toContainText('embedding-v2');
    await expect(panel.locator('.details ffk-badge')).toHaveText('Active');
    await panel.locator('.heading').scrollIntoViewIfNeeded();
    await capture(page, `active-${width}-light`);
    expect(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth)).toBe(
      true,
    );
    const bounds = await panel.boundingBox();
    expect(bounds!.x + bounds!.width).toBeLessThanOrEqual(width);
    await page.getByText('Deployment observations', { exact: true }).click();
    await expect(
      page.getByRole('button', { name: 'Refresh deployment observations', exact: true }),
    ).toBeVisible();
  });
test('an unknown build survives reload and repeats only the exact explicitly reviewed request', async ({
  page,
}) => {
  const service = await fixture(page);
  service.unknownCreate();
  let panel = await open(page, 1440);
  await plan(page, panel);
  await panel.getByRole('button', { name: 'Build this index', exact: true }).click();
  await expect(panel).toContainText('Index action not confirmed');
  const first = service.writes.find((row) => row.path.endsWith('/knowledge-indexes'))!;
  await page.reload();
  await page.getByRole('button', { name: 'Storage & indexing', exact: true }).click();
  panel = page.locator('ffk-index-management-panel');
  await expect(panel).toBeVisible();
  await panel.getByLabel('Index workspace', { exact: true }).selectOption('workspace-one');
  await expect(panel).toContainText('Index action not confirmed');
  expect(service.writes.filter((row) => row.path.endsWith('/knowledge-indexes'))).toHaveLength(1);
  await panel.getByRole('button', { name: 'Inspect current state', exact: true }).click();
  await expect(panel).toContainText('original request remains unconfirmed');
  await panel.getByRole('button', { name: 'Review saved request', exact: true }).click();
  await expect(panel).toContainText('original request key and preconditions');
  await panel.getByRole('button', { name: 'Submit saved request', exact: true }).click();
  await expect(panel.locator('.uncertain')).toHaveCount(0);
  const writes = service.writes.filter((row) => row.path.endsWith('/knowledge-indexes'));
  expect(writes).toHaveLength(2);
  expect(writes[1].key).toBe(first.key);
  expect(writes[1].body).toEqual(first.body);
});
test('cancel, resume and interrupted activation require separate current-state reviews on mobile', async ({
  page,
}) => {
  const service = await fixture(page);
  await page.setViewportSize({ width: 390, height: 960 });
  const panel = await open(page, 390);
  await plan(page, panel);
  await panel.getByRole('button', { name: 'Build this index', exact: true }).click();
  await expect(panel.locator('.details')).toContainText('Queued');
  await panel
    .locator('.details')
    .getByRole('button', { name: 'Cancel build', exact: true })
    .click();
  await panel
    .locator('.action-review')
    .getByRole('button', { name: 'Cancel build', exact: true })
    .click();
  await expect(panel.locator('.details')).toContainText('Cancelled');
  await panel
    .locator('.details')
    .getByRole('button', { name: 'Resume build', exact: true })
    .click();
  await panel
    .locator('.action-review')
    .getByRole('button', { name: 'Resume build', exact: true })
    .click();
  await expect(panel.locator('.details')).toContainText('Queued');
  service.ready();
  await panel.getByRole('button', { name: 'Refresh indexes', exact: true }).click();
  service.unknownActivation();
  await panel
    .locator('.details')
    .getByRole('button', { name: 'Activate index', exact: true })
    .click();
  await panel
    .locator('.action-review')
    .getByRole('button', { name: 'Activate index', exact: true })
    .click();
  await expect(panel).toContainText('Index action not confirmed');
  await panel.getByRole('button', { name: 'Inspect current state', exact: true }).click();
  await expect(panel.locator('.details')).toContainText('Activation unfinished');
  await panel
    .locator('.details')
    .getByRole('button', { name: 'Finish activation', exact: true })
    .click();
  await expect(panel.locator('.action-review')).toContainText(
    'explicitly finishes an interrupted activation',
  );
  const confirm = panel
    .locator('.action-review')
    .getByRole('button', { name: 'Finish activation', exact: true });
  await confirm.focus();
  await confirm.scrollIntoViewIfNeeded();
  await expect(confirm).toBeFocused();
  const confirmBounds = await confirm.boundingBox();
  const footerBounds = await page.locator('footer').boundingBox();
  expect(confirmBounds!.y + confirmBounds!.height).toBeLessThanOrEqual(footerBounds!.y);
  await capture(page, 'recovery-390-light');
  await panel
    .locator('.action-review')
    .getByRole('button', { name: 'Finish activation', exact: true })
    .click();
  await expect(panel.locator('.active-target')).toContainText('embedding-v2');
  expect(
    service.writes
      .filter((row) => row.path.endsWith('/activate'))
      .map((row) => row.body['recovery'] ?? 'normal'),
  ).toEqual(['normal', 'finish']);
});
test('scope and domain changes remove the reviewed plan before another operation', async ({
  page,
}) => {
  const service = await fixture(page);
  const panel = await open(page, 1440);
  await plan(page, panel);
  await panel.getByLabel('Index domain', { exact: true }).selectOption('structured');
  await expect(panel.locator('.plan-review')).toHaveCount(0);
  await expect(panel.locator('.active-target')).toContainText('No active target observed');
  expect(service.writes).toHaveLength(1);
});
test('the existing management layout remains readable in dark appearance', async ({ page }) => {
  await fixture(page);
  await page.addInitScript(() => localStorage.setItem('koinon-theme', 'dark'));
  await page.setViewportSize({ width: 1440, height: 960 });
  const panel = await open(page, 1440);
  await plan(page, panel);
  await panel.locator('.plan-review').scrollIntoViewIfNeeded();
  await capture(page, 'plan-1440-dark');
  expect(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth)).toBe(true);
});
