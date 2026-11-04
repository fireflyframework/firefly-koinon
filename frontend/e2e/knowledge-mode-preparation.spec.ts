// Copyright 2026 Firefly Software Foundation SPDX-License-Identifier: Apache-2.0
// Controlled receipts qualify the browser journey, not native processing or model acceptance.
import { expect, test } from '@playwright/test';
import { mkdir } from 'node:fs/promises';
import { resolve } from 'node:path';
import { mockService, openAdministration } from './fixtures';
import { knowledgeBehaviorSettings as settings } from './knowledge-behavior-fixture';

for (const width of [1440, 390])
  test(`governed mode progress, retry and cancelled-index recovery at ${width}px`, async ({
    page,
  }) => {
    await mockService(page);
    await page.setViewportSize({ width, height: 1000 });
    let record: Record<string, unknown> | null = null;
    let targets: Record<string, unknown>[] = [];
    const writes: { path: string; body: unknown }[] = [];
    await page.route('**/bff/api/v1/tenants/*/knowledge/settings', (route) =>
      route.fulfill({ json: settings }),
    );
    await page.route('**/bff/api/v1/tenants/*/knowledge/settings/transitions**', async (route) => {
      const request = route.request(),
        path = new URL(request.url()).pathname;
      if (request.method() === 'POST') {
        const body = request.postDataJSON();
        writes.push({ path, body });
        if (path.endsWith('/transitions'))
          record = {
            id: 'mode-one',
            tenant_id: 'tenant-one',
            job_id: 'mode-job',
            revision: 1,
            base_revision: 7,
            base_digest: 'a'.repeat(64),
            active_mode: 'rag',
            requested_mode: 'rlm',
            requested_settings: body,
            status: 'queued',
            stage: 'discovery',
            counters: { catalog_scanned: 0 },
            stage_milliseconds: { discovery: 0 },
            pending_index_recoveries: 0,
            error: null,
            error_code: null,
            created_at: '2026-11-03T00:00:00Z',
            updated_at: '2026-11-03T00:00:00Z',
          };
        else if (path.endsWith('/retry'))
          record = {
            ...record,
            revision: 3,
            status: 'queued',
            stage: 'repair_views',
            error: null,
            error_code: null,
          };
        else if (path.endsWith('/cancel'))
          record = {
            ...record,
            revision: 4,
            status: 'cancelled',
            pending_index_recoveries: 1,
            error:
              'Mode change cancelled. Complete or restore the recorded index activation; the active mode is unchanged.',
            error_code: 'MODE_INDEX_RECOVERY_REQUIRED',
          };
        else throw new Error('Unexpected controlled transition mutation');
        return route.fulfill({ json: record });
      }
      return route.fulfill({
        json: path.endsWith('/current')
          ? { transition: record }
          : path.endsWith('/recoveries')
            ? {
                items: targets
                  .filter((target) => target['index_recovery'])
                  .map((target) => ({
                    ...(target['index_recovery'] as object),
                    receipt_id: 'receipt-one',
                    attempt_revision: 5,
                    resolution_revision: 1,
                    resolution: 'pending',
                    workspace_id: target['workspace_id'],
                    native_workspace_id: 'original-native-workspace',
                    native_index_id: 'recorded-set',
                    provider_id: 'provider',
                    model_id: 'embedding',
                  })),
                next_cursor: null,
              }
            : path.endsWith('/targets')
              ? { items: targets, next_cursor: null }
              : record,
      });
    });
    await page.route(
      '**/bff/api/v1/tenants/*/knowledge-indexes/controlled-index/activate',
      async (route) => {
        writes.push({
          path: new URL(route.request().url()).pathname,
          body: route.request().postDataJSON(),
        });
        record = {
          ...record,
          pending_index_recoveries: 0,
          revision: 5,
          error: null,
          error_code: null,
        };
        targets = [];
        await route.fulfill({ json: { id: 'controlled-index', status: 'active' } });
      },
    );
    await page.goto('/library');
    await openAdministration(page, 'Settings');
    await page.getByRole('button', { name: 'Configure answers', exact: true }).click();
    const panel = page.locator('ffk-knowledge-behavior');
    await panel.getByRole('radio', { name: /Analyze documents in steps/ }).check();
    await panel.getByRole('button', { name: 'Prepare mode change', exact: true }).click();
    await expect(panel).toContainText('Active mode: RAG');
    await expect(panel).toContainText('Requested mode: RLM');
    await expect(panel).toContainText('Discovering documents');
    record = {
      ...record,
      revision: 2,
      status: 'failed',
      stage: 'repair_views',
      error_code: 'SOURCE_VERSION_PREPARATION_REQUIRED',
      error:
        'This source has no committed document version. Open the document processing action, then retry.',
      counters: { catalog_scanned: 101 },
      stage_milliseconds: { repair_views: 430 },
    };
    targets = [
      {
        id: 'target',
        kind: 'document',
        catalog_id: 'controlled-source',
        workspace_id: 'workspace-one',
        status: 'failed',
        error_code: 'SOURCE_VERSION_PREPARATION_REQUIRED',
        action: 'reprocess_document',
        message: record['error'],
        job_id: 'source-job',
        job_status: 'failed',
      },
    ];
    await panel.getByRole('button', { name: 'Refresh preparation', exact: true }).click();
    await expect(panel).toContainText('no committed document version');
    await expect(
      panel.getByRole('button', { name: 'Retry preparation', exact: true }),
    ).toBeDisabled();
    const directory = process.env['KOINON_UI_CAPTURE_DIR'] ?? 'test-results/knowledge-modes';
    await mkdir(directory, { recursive: true });
    await panel.locator('.preparation').scrollIntoViewIfNeeded();
    await page.screenshot({
      path: resolve(directory, `mode-prerequisite-${width}.png`),
      animations: 'disabled',
    });
    await panel
      .getByRole('checkbox', { name: 'I reviewed the prerequisites and retry usage', exact: true })
      .check();
    await panel.getByRole('button', { name: 'Retry preparation', exact: true }).click();
    await expect(panel).toContainText('Preparing document views');
    expect(writes[1].body).toEqual({ expected_revision: 2 });
    targets = [
      {
        id: 'workspace-target',
        kind: 'workspace',
        catalog_id: 'workspace-one',
        workspace_id: 'workspace-one',
        status: 'waiting',
        index_id: 'controlled-index',
        action: 'reconcile_index',
        index_recovery: {
          index_id: 'controlled-index',
          job_id: null,
          state: 'required',
          activation_job_id: 'activation-job',
          activation_lease_until: null,
          index_status: 'activating',
          native_pointer_state: 'target',
          expected_revision: 9,
          expected_active_id: 'previous-index',
          expected_connection_revision: 4,
          actions: ['finish', 'restore_previous'],
          message: 'The native pointer is already applied. Finish or restore the recorded index.',
        },
      },
    ];
    await panel.getByRole('button', { name: 'Cancel mode change', exact: true }).click();
    await expect(panel).toContainText('Index reconciliation is still required');
    await expect(panel.getByRole('radio').first()).toBeDisabled();
    await panel
      .getByRole('button', { name: 'Review finishing the index activation', exact: true })
      .click();
    await expect(
      panel.getByRole('region', { name: 'Review index reconciliation', exact: true }),
    ).toContainText('does not activate a cancelled mode change');
    await page.screenshot({
      path: resolve(directory, `mode-recovery-${width}.png`),
      animations: 'disabled',
    });
    await panel.getByRole('button', { name: 'Confirm index reconciliation', exact: true }).click();
    await expect(panel).not.toContainText('Index reconciliation is still required');
    await expect(panel).toContainText('Active mode: RAG');
    expect(writes.at(-1)?.body).toEqual({
      expected_revision: 9,
      expected_active_id: 'previous-index',
      expected_connection_revision: 4,
      recovery: 'finish',
    });
    expect(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth)).toBe(
      true,
    );
  });
