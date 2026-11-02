// Copyright 2026 Firefly Software Foundation
// SPDX-License-Identifier: Apache-2.0
import { expect, test, type Page } from '@playwright/test';
import { mkdir } from 'node:fs/promises';
import type { FileBatchItemView, FileBatchView } from '@fireflyframework/koinon-sdk';
import { context, mockService } from './fixtures';
async function fixture(page: Page) {
  await mockService(page);
  const owner = context.subject;
  let many = false;
  let subject = owner,
    credential = 'original',
    denyDetail = 0,
    lostOriginal = false;
  let recoveryOperation: 'retry_processing' | 'finalize_publication' | 'acknowledge_commit' | null =
    'retry_processing';
  let lostRecovery = false;
  let failedRecoveryRefresh = false,
    recoveryAcknowledged = false;
  let batch: FileBatchView = {
    id: 'retained-batch',
    tenant_id: 'tenant-one',
    destination: {
      workspace_id: 'workspace-one',
      project_id: 'project-one',
      parent_id: 'collection-one',
    },
    status: 'staging',
    revision: 1,
    total_items: 1,
    total_bytes: 2,
    counts: { awaiting_upload: 1 },
    cancellation_requested: false,
    created_at: '2026-11-01T10:00:00Z',
    expires_at: '2099-01-01T00:00:00Z',
  };
  let item: FileBatchItemView = {
    id: 'retained-item',
    client_item_id: 'client-item',
    filename: 'Operating guide.docx',
    mode: 'document',
    size_bytes: 2,
    sha256: 'a'.repeat(64),
    status: 'awaiting_upload',
    source_id: 'source-one',
    asset_id: 'document-one',
    job_id: null,
    table_ids: [],
  };
  const calls: {
    method: string;
    path: string;
    body: Record<string, unknown> | null;
    key: string | undefined;
  }[] = [];
  await page.route('**/bff/api/v1/**', async (route) => {
    const request = route.request(),
      path = new URL(request.url()).pathname,
      method = request.method();
    if (path.endsWith('/context')) {
      const current = structuredClone(context);
      current.subject = subject;
      current.memberships = [
        {
          id: 'grant',
          subject,
          tenant_id: 'tenant-one',
          workspace_id: null,
          role: 'admin',
          active: true,
        },
      ];
      return route.fulfill({ json: current });
    }
    if (!path.includes('/sources/batches')) return route.fallback();
    const body = method === 'POST' ? (request.postDataJSON() as Record<string, unknown>) : null;
    calls.push({ method, path, body, key: request.headers()['idempotency-key'] });
    const json = (value: unknown, status = 200) => route.fulfill({ status, json: value });
    if (path.endsWith('/sources/batches')) {
      const authorized = subject === owner && credential === 'original';
      const pageNumber = Number(new URL(request.url()).searchParams.get('page') ?? 1);
      const rows = many
        ? pageNumber === 1
          ? [batch, ...Array.from({ length: 24 }, (_, i) => ({ ...batch, id: 'retained-' + i }))]
          : [{ ...batch, id: 'retained-last' }]
        : [batch];
      return json({
        items: authorized ? rows : [],
        total: authorized ? (many ? 26 : 1) : 0,
        page: pageNumber,
        page_size: 25,
        pages: authorized ? (many ? 2 : 1) : 0,
      });
    }
    if (subject !== owner || credential !== 'original' || denyDetail)
      return json(
        { code: 'ACCESS_DENIED', message: 'Private original exception' },
        denyDetail || 403,
      );
    if (method === 'GET' && failedRecoveryRefresh && recoveryAcknowledged)
      return json({ code: 'STATUS_UNAVAILABLE', message: 'Private upstream failure' }, 503);
    if (path.endsWith('/items'))
      return json({ items: [item], total: 1, page: 1, page_size: 50, pages: 1 });
    if (path.endsWith('/recovery'))
      return json({
        batch_id: batch.id,
        item_id: item.id,
        batch_revision: batch.revision,
        native_state:
          recoveryOperation === 'finalize_publication'
            ? 'prepared'
            : recoveryOperation === 'acknowledge_commit'
              ? 'committed'
              : recoveryOperation
                ? 'absent'
                : 'unknown',
        operation: recoveryOperation,
        reason_code: recoveryOperation ? null : 'BULK_NATIVE_OUTCOME_UNRESOLVED',
        attempts: 1,
        max_attempts: 3,
        checked_at: '2026-11-01T10:30:00Z',
        job_status: 'failed',
        original_receipt_state: 'verified',
      });
    if (path.endsWith('/receipt'))
      return json({
        receipt_id: 'verified-receipt',
        batch_id: batch.id,
        item_id: item.id,
        size_bytes: item.size_bytes,
        sha256: item.sha256,
        status: 'staged',
      });
    if (method === 'POST') {
      if (body?.['expected_revision'] !== batch.revision)
        return json({ code: 'BULK_REVISION_CONFLICT', message: 'Changed revision' }, 409);
      if (path.endsWith('/original/reconcile')) {
        if (lostOriginal) {
          lostOriginal = false;
          return route.abort('failed');
        }
        item = { ...item, status: 'staged' };
      } else if (path.endsWith('/recover')) {
        if (lostRecovery) {
          lostRecovery = false;
          return route.abort('failed');
        }
        recoveryAcknowledged = true;
        item = {
          ...item,
          status: body?.['operation'] === 'acknowledge_commit' ? 'succeeded' : 'queued',
          source_version_id: body?.['operation'] === 'acknowledge_commit' ? 'source-version' : null,
          extraction_id: body?.['operation'] === 'acknowledge_commit' ? 'extraction' : null,
        };
        batch = { ...batch, status: item.status === 'succeeded' ? 'succeeded' : 'queued' };
      } else if (path.endsWith('/submit')) {
        item = { ...item, status: 'queued', job_id: 'native-job' };
        batch = { ...batch, status: 'queued' };
      } else if (path.endsWith('/cancel')) {
        item = { ...item, status: 'cancelled' };
        batch = { ...batch, status: 'cancelled', cancellation_requested: true };
      } else if (path.endsWith('/reconcile')) {
        item = {
          ...item,
          status: 'succeeded',
          source_version_id: 'source-version',
          extraction_id: 'extraction',
        };
        batch = { ...batch, status: 'succeeded' };
      } else throw Error('Unexpected retained upload mutation');
      batch = { ...batch, revision: batch.revision + 1, counts: { [item.status]: 1 } };
    }
    return json(batch, method === 'POST' && path.endsWith('/recover') ? 202 : 200);
  });
  return {
    calls,
    paginate: () => {
      many = true;
    },
    loseOriginal: () => {
      lostOriginal = true;
    },
    identity: (value: 'account' | 'credential') => {
      if (value === 'account') subject = 'another-person';
      else credential = 'different';
    },
    deny: (status: number) => {
      denyDetail = status;
    },
    recovery: (operation: typeof recoveryOperation = 'retry_processing') => {
      recoveryOperation = operation;
      item = {
        ...item,
        status: 'reconciling',
        job_id: 'native-job',
        error_code: 'INGEST_EXECUTION_CONTEXT_REQUIRED',
      };
      batch = { ...batch, status: 'reconciling', counts: { reconciling: 1 } };
    },
    failRecoveryRefresh: () => {
      failedRecoveryRefresh = true;
    },
    loseRecovery: () => {
      lostRecovery = true;
    },
    reconciling: () => {
      item = { ...item, status: 'reconciling', job_id: 'native-job' };
      batch = { ...batch, status: 'reconciling', counts: { reconciling: 1 } };
    },
  };
}
async function open(page: Page) {
  await page.goto('/library');
  await page.getByRole('button', { name: 'Uploads', exact: true }).click();
  const panel = page.locator('ffk-library-retained-uploads-panel');
  await expect(
    panel.getByRole('heading', { name: 'Your retained uploads', exact: true }),
  ).toBeVisible();
  return panel;
}
async function select(panel: ReturnType<Page['locator']>) {
  await panel.getByRole('button', { name: 'Inspect upload retained-batch', exact: true }).click();
  await expect(panel.getByRole('heading', { name: 'Upload details', exact: true })).toBeFocused();
}
async function capture(page: Page, name: string) {
  const output = process.env['KOINON_RETAINED_SCREENSHOTS'];
  if (output) {
    await mkdir(output, { recursive: true });
    await page.screenshot({ path: `${output}/${name}.png`, animations: 'disabled' });
  }
}
for (const width of [1440, 390])
  test(`reopens retained originals, checks them explicitly and separately submits at ${width}px`, async ({
    page,
  }) => {
    const service = await fixture(page);
    await page.setViewportSize({ width, height: 1000 });
    const panel = await open(page);
    await capture(page, `list-${width}`);
    await select(panel);
    await expect(panel).toContainText('Operating guide.docx');
    expect(service.calls.every((c) => c.method === 'GET' && !c.path.endsWith('/receipt'))).toBe(
      true,
    );
    await panel.getByRole('button', { name: 'Check retained original', exact: true }).click();
    const review = panel.getByRole('region', { name: 'Review upload action', exact: true });
    await expect(
      review.getByRole('heading', { name: 'Check retained original', exact: true }),
    ).toBeFocused();
    expect(service.calls.every((c) => c.method === 'GET')).toBe(true);
    await review.getByRole('button', { name: 'Check retained original', exact: true }).click();
    await expect(panel).toContainText('Original received');
    expect(service.calls.some((c) => c.path.endsWith('/submit'))).toBe(false);
    await panel.getByRole('button', { name: 'Verify retained original', exact: true }).click();
    await expect(panel).toContainText('Original verified at');
    expect(service.calls.filter((c) => c.path.endsWith('/receipt'))).toHaveLength(1);
    await panel.getByRole('button', { name: 'Submit for processing', exact: true }).click();
    await expect(review).toContainText('Every original must be received first');
    await capture(page, `review-${width}`);
    await review.getByRole('button', { name: 'Submit for processing', exact: true }).focus();
    await review
      .getByRole('button', { name: 'Submit for processing', exact: true })
      .scrollIntoViewIfNeeded();
    const button = await review
      .getByRole('button', { name: 'Submit for processing', exact: true })
      .boundingBox();
    const modal = await page.getByRole('dialog', { name: 'Uploads', exact: true }).boundingBox();
    expect(button!.y).toBeGreaterThanOrEqual(modal!.y);
    expect(button!.y + button!.height).toBeLessThanOrEqual(modal!.y + modal!.height);
    await review.getByRole('button', { name: 'Submit for processing', exact: true }).click();
    await expect(panel.locator('.details-heading ffk-badge')).toHaveText('Queued');
    await expect(review).toHaveCount(0);
    expect(
      service.calls.filter((c) => c.method === 'POST').map((c) => c.path.split('/').pop()),
    ).toEqual(['reconcile', 'submit']);
    expect(
      service.calls.some(
        (c) => c.method === 'PUT' || (c.method === 'POST' && c.path.endsWith('/batches')),
      ),
    ).toBe(false);
    expect(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth)).toBe(
      true,
    );
  });
test('reload restores no write and only an authorized exact saved request can be reviewed', async ({
  page,
}) => {
  const service = await fixture(page);
  service.loseOriginal();
  let panel = await open(page);
  await select(panel);
  await panel.getByRole('button', { name: 'Check retained original', exact: true }).click();
  await panel
    .getByRole('region', { name: 'Review upload action', exact: true })
    .getByRole('button', { name: 'Check retained original', exact: true })
    .click();
  await expect(panel).toContainText('Some action results are not confirmed');
  const first = service.calls.find((c) => c.method === 'POST')!;
  await page.reload();
  await page.getByRole('button', { name: 'Uploads', exact: true }).click();
  panel = page.locator('ffk-library-retained-uploads-panel');
  expect(service.calls.filter((c) => c.method === 'POST')).toHaveLength(1);
  await expect(
    panel.getByRole('region', { name: 'Unconfirmed upload actions', exact: true }),
  ).toHaveCount(0);
  await select(panel);
  await expect(panel).toContainText('Some action results are not confirmed');
  await panel.getByRole('button', { name: 'Review saved request', exact: true }).click();
  expect(service.calls.filter((c) => c.method === 'POST')).toHaveLength(1);
  await panel
    .getByRole('region', { name: 'Review upload action', exact: true })
    .getByRole('button', { name: 'Check retained original', exact: true })
    .click();
  await expect(panel).toContainText('Original received');
  const writes = service.calls.filter((c) => c.method === 'POST');
  expect(writes).toHaveLength(2);
  expect(writes[1].body).toEqual(first.body);
  expect(writes[1].key).toBe(first.key);
});
for (const changed of ['account', 'credential'] as const)
  test(`another ${changed} cannot see the original batch or restore its saved request`, async ({
    page,
  }) => {
    const service = await fixture(page);
    service.loseOriginal();
    let panel = await open(page);
    await select(panel);
    await panel.getByRole('button', { name: 'Check retained original', exact: true }).click();
    await panel
      .getByRole('region', { name: 'Review upload action', exact: true })
      .getByRole('button', { name: 'Check retained original', exact: true })
      .click();
    await expect(panel).toContainText('Some action results are not confirmed');
    service.identity(changed);
    await page.reload();
    await page.getByRole('button', { name: 'Uploads', exact: true }).click();
    panel = page.locator('ffk-library-retained-uploads-panel');
    await expect(
      panel.getByRole('heading', { name: 'No retained uploads were returned', exact: true }),
    ).toBeVisible();
    await expect(panel).not.toContainText('Operating guide.docx');
    await expect(panel).not.toContainText('retained-batch');
    await expect(
      panel.getByRole('button', { name: 'Review saved request', exact: true }),
    ).toHaveCount(0);
    expect(service.calls.filter((c) => c.method === 'POST')).toHaveLength(1);
  });
test('401 while opening details ends the session without leaking retained names', async ({
  page,
}) => {
  const service = await fixture(page);
  const panel = await open(page);
  service.deny(401);
  await panel.getByRole('button', { name: 'Inspect upload retained-batch', exact: true }).click();
  await expect(page.locator('ffk-sign-in')).toBeVisible();
  await expect(page.locator('body')).not.toContainText('Operating guide.docx');
  await expect(page.locator('body')).not.toContainText('Private original exception');
  expect(service.calls.every((c) => c.method === 'GET')).toBe(true);
});
test('native outcome reconciliation is reviewed without repeating the import', async ({ page }) => {
  const service = await fixture(page);
  service.recovery('acknowledge_commit');
  const panel = await open(page);
  await select(panel);
  await panel.getByRole('button', { name: 'Inspect recovery', exact: true }).click();
  await panel.getByRole('button', { name: 'Record completed import', exact: true }).click();
  const review = panel.getByRole('region', { name: 'Review upload action', exact: true });
  expect(service.calls.every((c) => c.method === 'GET')).toBe(true);
  await review.getByRole('button', { name: 'Record completed import', exact: true }).click();
  await expect(panel).toContainText('Processing completed');
  await panel.getByText('Source and upload references', { exact: true }).click();
  await expect(panel).toContainText('source-version');
  await expect(panel).toContainText('extraction');
  expect(service.calls.filter((c) => c.method === 'POST')).toHaveLength(1);
});

test('cancelling retained work requires a fresh separate review without resending originals', async ({
  page,
}) => {
  const service = await fixture(page);
  const panel = await open(page);
  await select(panel);
  await panel.getByRole('button', { name: 'Request cancellation', exact: true }).click();
  const review = panel.getByRole('region', { name: 'Review upload action', exact: true });
  await expect(review).toContainText(
    'Published knowledge and already committed effects can remain',
  );
  expect(service.calls.every((c) => c.method === 'GET')).toBe(true);
  await review.getByRole('button', { name: 'Request cancellation', exact: true }).click();
  await expect(panel).toContainText('Cancelled');
  expect(
    service.calls.filter((c) => c.method === 'POST').map((c) => c.path.split('/').pop()),
  ).toEqual(['cancel']);
  expect(service.calls.some((c) => c.method === 'PUT')).toBe(false);
});
test('leaving a review returns focus to the inspected batch without performing the action', async ({
  page,
}) => {
  const service = await fixture(page);
  const panel = await open(page);
  await select(panel);
  await panel.getByRole('button', { name: 'Check retained original', exact: true }).click();
  const review = panel.getByRole('region', { name: 'Review upload action', exact: true });
  await review.getByRole('button', { name: 'Keep inspecting', exact: true }).click();
  await expect(review).toHaveCount(0);
  await expect(panel.getByRole('heading', { name: 'Upload details', exact: true })).toBeFocused();
  expect(service.calls.every((c) => c.method === 'GET')).toBe(true);
});

test('retained upload pagination reads the next authorized server page', async ({ page }) => {
  const service = await fixture(page);
  service.paginate();
  const panel = await open(page);
  await expect(
    panel.getByRole('button', { name: 'Inspect upload retained-batch', exact: true }),
  ).toBeVisible();
  await panel.getByRole('button', { name: 'Next uploads page', exact: true }).click();
  await expect(
    panel.getByRole('button', { name: 'Inspect upload retained-last', exact: true }),
  ).toBeVisible();
  await expect(
    panel.getByRole('button', { name: 'Inspect upload retained-batch', exact: true }),
  ).toHaveCount(0);
  expect(service.calls.every((c) => c.method === 'GET' && !c.path.endsWith('/receipt'))).toBe(true);
});

for (const width of [1440, 390])
  test(`explains failed processing and reviews recovery of the same original at ${width}px`, async ({
    page,
  }) => {
    const service = await fixture(page);
    service.recovery();
    await page.setViewportSize({ width, height: 1000 });
    const panel = await open(page);
    await select(panel);
    await expect(panel).toContainText('An administrator must update the processing service');
    expect(service.calls.some((c) => c.path.endsWith('/recovery'))).toBe(false);
    await panel.getByRole('button', { name: 'Inspect recovery', exact: true }).click();
    const recovery = panel.getByRole('region', { name: 'Processing recovery', exact: true });
    await expect(
      recovery.getByRole('heading', { name: 'Processing recovery', exact: true }),
    ).toBeFocused();
    await expect(recovery).toContainText('Upload confirmed');
    await expect(recovery).toContainText('Processing failed');
    await expect(recovery).toContainText('The upload receipt confirms the file was saved');
    expect(service.calls.every((c) => c.method === 'GET' && !c.path.endsWith('/receipt'))).toBe(
      true,
    );
    await capture(page, `processing-recovery-${width}`);
    await recovery.getByRole('button', { name: 'Retry processing', exact: true }).click();
    const review = panel.getByRole('region', { name: 'Review upload action', exact: true });
    await expect(review).toContainText('saved file again');
    await expect(review).toContainText('configured AI services');
    await capture(page, `processing-review-${width}`);
    const confirm = review.getByRole('button', { name: 'Retry processing', exact: true });
    await confirm.focus();
    await confirm.scrollIntoViewIfNeeded();
    const box = await confirm.boundingBox(),
      dialog = await page.getByRole('dialog', { name: 'Uploads', exact: true }).boundingBox();
    expect(box!.y).toBeGreaterThanOrEqual(dialog!.y);
    expect(box!.y + box!.height).toBeLessThanOrEqual(dialog!.y + dialog!.height);
    await confirm.click();
    await expect(panel.locator('.details-heading ffk-badge')).toHaveText('Queued');
    const writes = service.calls.filter((c) => c.method === 'POST');
    expect(writes).toHaveLength(1);
    expect(writes[0].path.endsWith('/recover')).toBe(true);
    expect(writes[0].body).toEqual({ expected_revision: 1, operation: 'retry_processing' });
    expect(service.calls.some((c) => c.method === 'PUT' || c.path.endsWith('/receipt'))).toBe(
      false,
    );
    expect(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth)).toBe(
      true,
    );
  });
test('unknown recovery survives reload without automatic retry or original reupload', async ({
  page,
}) => {
  const service = await fixture(page);
  service.recovery('finalize_publication');
  service.loseRecovery();
  let panel = await open(page);
  await select(panel);
  await panel.getByRole('button', { name: 'Inspect recovery', exact: true }).click();
  await panel.getByRole('button', { name: 'Finish publication', exact: true }).click();
  await panel
    .getByRole('region', { name: 'Review upload action' })
    .getByRole('button', { name: 'Finish publication', exact: true })
    .click();
  await expect(panel).toContainText('Some action results are not confirmed');
  const first = service.calls.find((c) => c.method === 'POST')!;
  service.recovery(null);
  await page.reload();
  await page.getByRole('button', { name: 'Uploads', exact: true }).click();
  panel = page.locator('ffk-library-retained-uploads-panel');
  await select(panel);
  expect(service.calls.filter((c) => c.method === 'POST')).toHaveLength(1);
  await panel.getByRole('button', { name: 'Review saved request', exact: true }).click();
  await panel
    .getByRole('region', { name: 'Review upload action' })
    .getByRole('button', { name: 'Finish publication', exact: true })
    .click();
  await expect(panel).toContainText('Action acknowledged');
  const writes = service.calls.filter((c) => c.method === 'POST');
  expect(writes).toHaveLength(2);
  expect(writes[1].body).toEqual(first.body);
  expect(writes[1].key).toBe(first.key);
});

test('Spanish recovery separates a confirmed upload from failed processing on mobile', async ({
  page,
}) => {
  const service = await fixture(page);
  service.recovery();
  await page.setViewportSize({ width: 390, height: 1000 });
  await page.route('**/bff/api/v1/profile', (route) =>
    route.fulfill({
      json: {
        subject: context.subject,
        display_name: 'Alex Rivera',
        locale: 'es-ES',
        time_zone: 'UTC',
        response_language: 'es',
        avatar_url: null,
        avatar_version: null,
      },
    }),
  );
  await page.goto('/library');
  await page.getByRole('button', { name: 'Subidas', exact: true }).click();
  const panel = page.locator('ffk-library-retained-uploads-panel');
  await panel.getByRole('button', { name: 'Consultar subida retained-batch', exact: true }).click();
  await panel.getByRole('button', { name: 'Revisar recuperación', exact: true }).click();
  const recovery = panel.getByRole('region', {
    name: 'Recuperación del procesamiento',
    exact: true,
  });
  await expect(recovery).toContainText('Subida confirmada');
  await expect(recovery).toContainText('Procesamiento fallido');
  await expect(recovery).toContainText('No publicado');
  await capture(page, 'processing-recovery-es-390');
  expect(service.calls.every((c) => c.method === 'GET' && !c.path.endsWith('/receipt'))).toBe(true);
  expect(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth)).toBe(true);
});

for (const width of [1440, 390])
  test(`keeps an acknowledged recovery separate from status refresh failure at ${width}px`, async ({
    page,
  }) => {
    const service = await fixture(page);
    service.recovery();
    service.failRecoveryRefresh();
    await page.setViewportSize({ width, height: 1000 });
    const panel = await open(page);
    await select(panel);
    await panel.getByRole('button', { name: 'Inspect recovery', exact: true }).click();
    await panel.getByRole('button', { name: 'Retry processing', exact: true }).click();
    await panel
      .getByRole('region', { name: 'Review upload action', exact: true })
      .getByRole('button', { name: 'Retry processing', exact: true })
      .click();
    await expect(panel.getByRole('alert')).toContainText('The action was acknowledged');
    await expect(panel.getByRole('alert')).toContainText('current status could not be refreshed');
    await expect(panel.locator('p.feedback[role="status"]')).toHaveCount(0);
    await expect(panel).not.toContainText('An administrator must update the processing service');
    await expect(panel).not.toContainText('Some action results are not confirmed');
    await expect(panel).not.toContainText('Private upstream failure');
    await expect(
      panel.getByRole('button', { name: 'Review saved request', exact: true }),
    ).toHaveCount(0);
    expect(
      await page.evaluate(() => sessionStorage.getItem('koinon:retained-upload-actions:v1')),
    ).toBeNull();
    expect(service.calls.filter((call) => call.method === 'POST')).toHaveLength(1);
    expect(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth)).toBe(
      true,
    );
    await capture(page, `acknowledged-refresh-failed-${width}`);
  });
