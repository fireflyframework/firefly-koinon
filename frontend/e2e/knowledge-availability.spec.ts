// Copyright 2026 Firefly Software Foundation
// SPDX-License-Identifier: Apache-2.0
// Compiled-host qualification uses controlled observations, never live processing claims.
import { expect, test, type Page } from '@playwright/test';
import { mkdir } from 'node:fs/promises';
import { resolve } from 'node:path';
import { mockService } from './fixtures';

const observation = {
  phase: 'failed',
  read: { state: 'ready', reason: 'CURRENT_TEXT_RECORDED' },
  search: { state: 'pending', reason: 'ACTIVE_INDEX_INCOMPLETE' },
  query: { state: 'not_applicable', reason: 'DOCUMENT' },
  revision: { source_version_id: 'observed-serving-v1', extraction_id: 'extraction-v1' },
  latest_attempt: { id: 'replacement-v2', operation: 'document.replace', state: 'failed' },
};
async function capture(page: Page, name: string) {
  const directory = process.env['KOINON_AVAILABILITY_CAPTURES'];
  if (!directory) return;
  await mkdir(directory, { recursive: true });
  await page.evaluate(() => document.fonts.ready);
  await page.screenshot({ path: resolve(directory, name + '.png'), animations: 'disabled' });
}
for (const width of [1440, 390]) {
  test(`current native observations and recorded failure stay distinct at ${width}px`, async ({
    page,
  }) => {
    await page.setViewportSize({ width, height: width === 390 ? 844 : 1000 });
    const service = await mockService(page);
    service.rows.find((row) => row.id === 'dataset-one')!.metadata = {
      status: 'ready',
      indexed: true,
    };
    const requests: { asset_ids: string[]; workspace_id?: string }[] = [];
    await page.route('**/catalog/availability', async (route) => {
      const body = route.request().postDataJSON() as { asset_ids: string[]; workspace_id?: string };
      requests.push(body);
      await route.fulfill({
        json: {
          observed_at: '2026-11-01T09:00:00Z',
          items: Object.fromEntries(
            body.asset_ids.map((id) => [
              id,
              id === 'document-one' ? observation : { phase: 'unknown' },
            ]),
          ),
        },
      });
    });
    await page.goto('/library');
    for (const name of ['Research operations', 'Operations intelligence', 'Reference library'])
      await page.getByRole('button', { name, exact: true }).click();
    const documentRow = page.getByRole('row').filter({ hasText: 'Service operating policy.pdf' });
    await expect(documentRow.getByText('Needs attention', { exact: true })).toBeVisible();
    await expect(
      documentRow.getByText('Observed version remains available', { exact: true }),
    ).toBeVisible();
    const dataset = page.getByRole('row').filter({ hasText: 'Quarterly service activity' });
    await expect(dataset.getByText('Availability not checked', { exact: true })).toBeVisible();
    await expect(dataset.getByText('Ready', { exact: true })).toHaveCount(0);
    expect(
      requests.some(
        (input) =>
          input.asset_ids.includes('document-one') && input.workspace_id === 'workspace-one',
      ),
    ).toBe(true);
    expect(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth)).toBe(
      true,
    );
    await capture(page, `library-availability-${width}`);
    await page
      .getByRole('button', { name: 'Details for Service operating policy.pdf', exact: true })
      .click();
    await expect(
      page.getByText('Observed serving version: observed-serving-v1', { exact: false }),
    ).toBeVisible();
    await capture(page, `library-serving-version-${width}`);
  });
  test(`administrator processing shows recorded attempts and avoids generic bulk cancellation at ${width}px`, async ({
    page,
  }) => {
    await page.setViewportSize({ width, height: width === 390 ? 844 : 1000 });
    await mockService(page);
    await page.route('**/knowledge-processing', (route) =>
      route.fulfill({
        json: {
          observed_at: '2026-11-01T09:00:00Z',
          next_page: null,
          items: [
            {
              id: 'replacement-v2',
              resource_id: 'document-one',
              operation: 'document.replace',
              state: 'failed',
              updated_at: '2026-11-01T08:59:00Z',
              availability: observation,
            },
          ],
        },
      }),
    );
    await page.route('**/tenants/*/jobs', (route) =>
      route.fulfill({
        json: {
          items: [
            {
              id: 'bulk-job',
              tenant_id: 'tenant-one',
              resource_id: 'source-one',
              kind: 'knowledge.bulk.intake',
              status: 'queued',
              attempts: 0,
              max_attempts: 3,
              progress: null,
              error: null,
              created_at: '2026-11-01T08:59:00Z',
              updated_at: '2026-11-01T08:59:00Z',
              result: null,
            },
          ],
        },
      }),
    );
    await page.goto('/activity');
    const processing = page.getByRole('region', { name: 'Current knowledge processing' });
    await expect(processing.getByText('Needs attention', { exact: true })).toBeVisible();
    await expect(
      processing.getByText('Text remains available from the observed version', { exact: true }),
    ).toBeVisible();
    await expect(page.getByRole('button', { name: 'Cancel', exact: true })).toHaveCount(0);
    expect(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth)).toBe(
      true,
    );
    await processing.scrollIntoViewIfNeeded();
    await capture(page, `processing-history-${width}`);
  });
}
