// Copyright 2026 Firefly Software Foundation
// SPDX-License-Identifier: Apache-2.0
import { test, expect } from '@playwright/test';
import { mkdir } from 'node:fs/promises';
import { mockService } from './fixtures';

for (const [state, status] of [
  ['searchable', 'pending'],
  ['failed-update', 'pending'],
  ['unknown', 'pending'],
  ['searchable', 'draft'],
  ['searchable', 'disabled'],
] as const) {
  test(`Library distinguishes ${state} availability from catalog ${status}`, async ({ page }) => {
    await page.setViewportSize({ width: 1440, height: 900 });
    const service = await mockService(page);
    service.rows.find((row) => row.id === 'document-one')!.status = status;
    await page.route('**/catalog/availability', (route) =>
      route.fulfill({
        json: {
          observed_at: '2026-11-02T00:00:00Z',
          items: {
            'document-one': {
              phase:
                state === 'failed-update' ? 'failed' : state === 'unknown' ? 'unknown' : 'complete',
              read: { state: state === 'unknown' ? 'unknown' : 'ready' },
              search: { state: state === 'unknown' ? 'unknown' : 'ready' },
              query: { state: 'unknown' },
              revision: {},
              latest_attempt: state === 'failed-update' ? { state: 'failed' } : null,
            },
          },
        },
      }),
    );
    await page.goto('/library');
    for (const name of ['Research operations', 'Operations intelligence', 'Reference library'])
      await page.getByRole('button', { name, exact: true }).click();
    const row = page.getByRole('row').filter({
      has: page.getByRole('button', { name: 'Service operating policy.pdf', exact: true }),
    });
    await expect(row.locator('ffk-knowledge-availability')).toContainText(
      state === 'searchable'
        ? 'Searchable'
        : state === 'failed-update'
          ? 'Processing failed'
          : 'Availability not checked',
    );
    if (status === 'pending') await expect(row.locator('.name-wrap > ffk-badge')).toHaveCount(0);
    else
      await expect(row.locator('.name-wrap > ffk-badge')).toContainText(
        status === 'draft' ? 'Draft' : 'Disabled',
      );
    if (state === 'failed-update')
      await expect(row).toContainText('Observed version remains available');
    if (state === 'unknown') await expect(row).not.toContainText('Searchable');
    const dir = process.env['KOINON_LIBRARY_STATE_SCREENSHOTS'];
    if (dir) {
      await mkdir(dir, { recursive: true });
      await page.screenshot({
        path: `${dir}/library-${state}-${status}.png`,
        animations: 'disabled',
      });
    }
  });
}
