// Copyright 2026 Firefly Software Foundation
// SPDX-License-Identifier: Apache-2.0
import { test, expect, type Page } from '@playwright/test';
import { resolve } from 'node:path';
import { mkdir } from 'node:fs/promises';
import { mockService } from './fixtures';
const snapshot = (id: string, recorded = true) => ({
  dataset_id: 'dataset-one',
  table_id: 'table-one',
  native_dataset_id: 'native-dataset',
  native_table_id: 'native-table',
  snapshot_id: id,
  status: recorded ? 'recorded' : 'not_recorded',
  snapshot_status: 'READY',
  level: 'file_section',
  ...(recorded
    ? {
        operation: id === 'current' ? 'replace' : 'upload',
        recorded_at: '2026-10-27T10:00:00Z',
        artifact: {
          id: 'original-' + id,
          original_filename:
            id === 'current' ? 'service-activity-october.xlsx' : 'service-activity-september.xlsx',
          sha256: 'a'.repeat(64),
          byte_size: 24318,
          file_format: 'xlsx',
          compression: 'none',
          actor: 'reviewer',
          admitted_at: '2026-10-27T09:59:00Z',
        },
        row_count: 1462,
        sheet_or_json_path: 'Activity#section[0:1463]',
        parquet_sha256: 'b'.repeat(64),
        schema_sha256: 'c'.repeat(64),
        actor: 'reviewer',
      }
    : {}),
});
async function fixture(page: Page) {
  await mockService(page);
  const reads: URL[] = [];
  const cells: unknown[] = [];
  let denied = false;
  await page.route('**/bff/api/v1/**/tables/table-one/**', async (route) => {
    const url = new URL(route.request().url());
    reads.push(url);
    const respond = (body: unknown, status = 200) =>
      route.fulfill({ status, contentType: 'application/json', body: JSON.stringify(body) });
    if (denied)
      return respond(
        { code: 'ACCESS_DENIED', message: 'This table is no longer shared with you.' },
        403,
      );
    if (url.pathname.includes('/coordinates')) {
      const body = route.request().method() === 'POST' ? route.request().postDataJSON() : null;
      const snapshotId = body?.snapshot_id ?? url.searchParams.get('snapshot_id');
      const identity = {
        dataset_id: 'dataset-one',
        table_id: 'table-one',
        native_dataset_id: 'native-dataset',
        native_table_id: 'native-table',
        snapshot_id: snapshotId,
        index_base: 0,
      };
      const manifest =
        snapshotId === 'legacy' || snapshotId === 'earliest'
          ? { ...identity, status: 'not_recorded' }
          : {
              ...identity,
              status: 'complete',
              row_count: 1462,
              column_count: 2,
              artifact_id: 'original-' + snapshotId,
              run_id: 'recorded-run',
              input_sha256: 'a'.repeat(64),
              mapping_sha256: 'd'.repeat(64),
              source_format: 'excel',
              source_variant: 'xlsx',
              row_kind: 'sheet_row',
              source_sheet: 'Activity',
              source_path: [],
              parser_decisions: [{ name: 'header', value: true }],
              dependencies: [{ name: 'python-calamine', version: '0.9.0' }],
              rejected_source_rows: [],
            };
      if (url.pathname.endsWith('/cells')) {
        cells.push(body);
        return respond({
          manifest,
          items: [
            {
              output_row: 0,
              output_column: 1,
              source_row: 4,
              source_column: 6,
              source_path: [],
              header_cells: [{ row: 3, column: 6 }],
              source_type: null,
            },
          ],
        });
      }
      if (url.pathname.endsWith('/rows')) {
        const current = Number(url.searchParams.get('page') ?? 1),
          start = (current - 1) * 25;
        return respond({
          manifest,
          items: Array.from({ length: current === 1 ? 25 : 1 }, (_, offset) => ({
            output_start: (start + offset) * 50,
            count: current === 1 ? 50 : 212,
            source_start: 4 + (start + offset) * 50,
            source_stride: 1,
          })),
          total: 26,
          page: current,
          page_size: 25,
          pages: 2,
          has_next: current === 1,
          has_previous: current === 2,
        });
      }
      if (url.pathname.endsWith('/columns'))
        return respond({
          manifest,
          items: [
            {
              output_position: 0,
              source_field_index: 3,
              source_path: [],
              source_type: 'string',
              header_cells: [{ row: 3, column: 3 }],
            },
            {
              output_position: 1,
              source_field_index: 6,
              source_path: [],
              source_type: 'integer',
              header_cells: [{ row: 3, column: 6 }],
            },
          ],
          total: 2,
          page: 1,
          page_size: 25,
          pages: 1,
          has_next: false,
          has_previous: false,
        });
      return respond(manifest);
    }
    if (url.pathname.endsWith('/snapshots')) {
      const current = Number(url.searchParams.get('page') ?? 1);
      return respond({
        items:
          current === 1
            ? [
                snapshot('current'),
                snapshot('previous'),
                snapshot('legacy', false),
                ...Array.from({ length: 22 }, (_, index) => snapshot('legacy-' + index, false)),
              ]
            : [snapshot('earliest', false)],
        total: 26,
        page: current,
        page_size: 25,
        pages: 2,
        has_next: current === 1,
        has_previous: current === 2,
        current_snapshot_id: 'current',
      });
    }
    const id = url.searchParams.get('snapshot_id')!;
    return respond({
      ...snapshot(id, id !== 'legacy' && id !== 'earliest'),
      ...(id === 'legacy' || id === 'earliest'
        ? {}
        : {
            run_id: 'recorded-run',
            steps: [
              {
                id: 'read',
                ordinal: 1,
                kind: 'materialize',
                implementation: 'ExcelReader',
                implementation_sha256: 'd'.repeat(64),
                input_sha256: 'a'.repeat(64),
                output_sha256: 'e'.repeat(64),
                parameters: {},
                actor: 'reviewer',
                recorded_at: '2026-10-27T09:59:20Z',
              },
              {
                id: 'describe',
                ordinal: 2,
                kind: 'model_input',
                implementation: 'column-descriptions',
                input_sha256: 'f'.repeat(64),
                parameters: {
                  role: 'structured.describe',
                  selected_model_id: 'configured-model',
                  provider_revision: 3,
                  instructions_sha256: '1'.repeat(64),
                },
                actor: 'reviewer',
                recorded_at: '2026-10-27T09:59:30Z',
              },
              {
                id: 'save',
                ordinal: 3,
                kind: 'finalize_parquet',
                implementation: 'save-processed-data',
                output_sha256: 'b'.repeat(64),
                parameters: {},
                actor: 'reviewer',
                recorded_at: '2026-10-27T09:59:40Z',
              },
            ],
          }),
    });
  });
  return {
    reads,
    cells,
    deny: () => {
      denied = true;
    },
  };
}
async function open(page: Page) {
  await page.goto('/library');
  for (const name of ['Research operations', 'Operations intelligence', 'Reference library'])
    await page.getByRole('button', { name, exact: true }).click();
  await page.getByRole('button', { name: 'Quarterly service activity', exact: true }).click();
  await page
    .getByRole('button', { name: 'History & lineage, service_activity', exact: true })
    .click();
  return page.getByRole('dialog', { name: 'History & lineage' });
}
async function capture(page: Page, name: string) {
  await page.evaluate(() => {
    const dialog = document
      .querySelector('ffk-workbench')
      ?.shadowRoot?.querySelector('ffk-table-lineage-panel dialog');
    if (!dialog) return;
    dialog.querySelector('[data-qualification]')?.remove();
    const note = document.createElement('div');
    note.textContent = 'Controlled API fixtures, Table history & lineage';
    note.setAttribute('data-qualification', 'controlled');
    note.style.cssText =
      'font:10px/24px Manrope,sans-serif;text-align:center;background:#10110f;color:#fff;flex:0 0 24px';
    dialog.append(note);
  });
  await mkdir(resolve('../../../outputs'), { recursive: true });
  await page.screenshot({ path: resolve('../../../outputs', name), animations: 'disabled' });
}
for (const width of [1440, 390]) {
  test(`table history shows exact historical originals and processing at ${width}px`, async ({
    page,
  }) => {
    await page.setViewportSize({ width, height: 1000 });
    const service = await fixture(page),
      panel = await open(page);
    await expect(panel.getByText('1–25 of 26 items')).toBeInViewport();
    await expect(panel.getByRole('button', { name: 'Next versions page' })).toBeInViewport();
    await capture(page, `koinon-table-history-v13-${width}.png`);
    await panel.getByRole('button').filter({ hasText: 'service-activity-september.xlsx' }).click();
    await expect(panel.getByText('Original file', { exact: true })).toBeVisible();
    await expect(panel.getByText('service-activity-september.xlsx', { exact: true })).toBeVisible();
    await expect(panel.getByText('Current', { exact: true })).toHaveCount(0);
    expect(service.reads.at(-1)?.searchParams.get('snapshot_id')).toBe('previous');
    await expect(panel.getByText('any row and column positions', { exact: false })).toBeVisible();
    await capture(page, `koinon-table-origin-v13-${width}.png`);
    expect(await panel.evaluate((node) => node.scrollWidth <= node.clientWidth)).toBe(true);
    await panel.getByText('Recorded identifiers & hashes', { exact: true }).click();
    await expect(panel.getByText('a'.repeat(64), { exact: true }).first()).toBeVisible();
    await page.keyboard.press('Escape');
    await expect(panel).not.toBeVisible();
    await expect(
      page.getByRole('button', { name: 'History & lineage, service_activity', exact: true }),
    ).toBeFocused();
  });
}
test('history uses real pages, preserves unknown origins and handles permission loss without fallback', async ({
  page,
}) => {
  const service = await fixture(page),
    panel = await open(page);
  await panel.getByRole('button', { name: 'Next versions page' }).click();
  await expect(panel.getByText('26–26 of 26 items')).toBeVisible();
  expect(service.reads.at(-1)?.searchParams.get('page')).toBe('2');
  await panel.getByRole('button').filter({ hasText: 'Original not recorded' }).click();
  await expect(panel.getByText('Its origin cannot be inferred', { exact: false })).toBeVisible();
  await expect(panel.getByText('Original file', { exact: true })).toHaveCount(0);
  await panel.getByRole('button', { name: 'All versions', exact: true }).click();
  service.deny();
  await panel.getByRole('button', { name: 'Refresh versions' }).click();
  await expect(panel.getByRole('alert')).toContainText('no longer shared');
  await expect(panel.locator('.versions')).toHaveCount(0);
  expect(service.reads.every((url) => /snapshots|provenance/.test(url.pathname))).toBe(true);
});

for (const width of [1440, 390]) {
  test(`source coordinates keep exact version, server pages and readable cells at ${width}px`, async ({
    page,
  }) => {
    await page.setViewportSize({ width, height: 1000 });
    const service = await fixture(page),
      panel = await open(page);
    await panel.getByRole('button').filter({ hasText: 'service-activity-september.xlsx' }).click();
    const toggle = panel.getByRole('button', { name: 'Source coordinates', exact: true });
    await expect(toggle).toHaveAttribute('aria-expanded', 'false');
    expect(service.reads.filter((url) => url.pathname.includes('/coordinates'))).toHaveLength(0);
    await toggle.click();
    const coordinates = panel.locator('ffk-table-coordinates');
    await expect(coordinates.getByText('Complete map', { exact: true })).toBeVisible();
    await expect(coordinates.getByText('Excel workbook', { exact: true })).toBeVisible();
    await expect(coordinates.locator('details')).not.toHaveAttribute('open', '');
    await coordinates.getByRole('button', { name: 'Rows', exact: true }).click();
    await expect(coordinates.locator('tbody tr').first()).toContainText('1–50');
    await coordinates.getByRole('button', { name: 'Next rows page' }).click();
    await expect(coordinates.getByText('26–26 of 26 items')).toBeVisible();
    expect(service.reads.at(-1)?.searchParams.get('page')).toBe('2');
    expect(service.reads.at(-1)?.searchParams.get('snapshot_id')).toBe('previous');
    await coordinates.getByRole('button', { name: 'Columns', exact: true }).click();
    await expect(coordinates.locator('tbody')).toContainText('G4');
    await coordinates.getByRole('button', { name: 'Locate a cell', exact: true }).click();
    await coordinates.getByRole('spinbutton', { name: /Processed column/ }).fill('2');
    await coordinates.getByRole('button', { name: 'Show original location', exact: true }).click();
    await expect(coordinates.locator('.location strong')).toHaveText('G5');
    expect(service.cells).toEqual([{ snapshot_id: 'previous', cells: [{ row: 0, column: 1 }] }]);
    await panel.locator('.coordinates').evaluate(section => {
      const body = section.closest('dialog')!.querySelector<HTMLElement>('.body')!;
      body.scrollTop += section.getBoundingClientRect().top - body.getBoundingClientRect().top - 24;
    });
    expect(await panel.evaluate((node) => node.scrollWidth <= node.clientWidth)).toBe(true);
    await capture(page, `koinon-source-coordinates-v15-${width}.png`);
    service.deny();
    await coordinates.getByRole('button', { name: 'Rows', exact: true }).click();
    await expect(coordinates.getByRole('alert')).toContainText('no longer shared');
    await expect(coordinates.getByText('Complete map', { exact: true })).toHaveCount(0);
    await page.keyboard.press('Escape');
    await expect(panel).not.toBeVisible();
  });
}

test('a delayed coordinates download shows loading and preserves the selected version', async ({ page }) => {
  await fixture(page);
  let resume!: () => void;
  const held = new Promise<void>(resolve => { resume = resolve; });
  await page.route('**/chunk-*.js', async route => {
    const response = await route.fetch(), body = await response.text();
    if (body.includes('selectors:[[`ffk-table-coordinates`]]')) await held;
    await route.fulfill({ response, body });
  });
  const panel = await open(page);
  await panel.getByRole('button').filter({ hasText: 'service-activity-september.xlsx' }).click();
  await panel.getByRole('button', { name: 'Source coordinates', exact: true }).click();
  await expect(panel.getByLabel('Opening source coordinates')).toBeVisible();
  resume();
  await expect(panel.locator('ffk-table-coordinates').getByText('Complete map', { exact: true })).toBeVisible();
  await expect(panel.getByText('service-activity-september.xlsx', { exact: true })).toBeVisible();
});

test('a failed coordinates download leaves version history usable', async ({ page }) => {
  await fixture(page);
  await page.route('**/chunk-*.js', async route => {
    const response = await route.fetch(), body = await response.text();
    if (body.includes('selectors:[[`ffk-table-coordinates`]]')) return route.abort('failed');
    await route.fulfill({ response, body });
  });
  const panel = await open(page);
  await panel.getByRole('button').filter({ hasText: 'service-activity-september.xlsx' }).click();
  await panel.getByRole('button', { name: 'Source coordinates', exact: true }).click();
  await expect(panel.getByRole('alert')).toContainText('Source coordinates could not be opened');
  await panel.getByRole('button', { name: 'All versions', exact: true }).click();
  await expect(panel.getByRole('list', { name: 'Table versions' })).toBeVisible();
});
